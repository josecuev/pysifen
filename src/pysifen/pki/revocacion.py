"""Revocación: si el certificado seguía vigente, o si el prestador lo dio de baja.

Un certificado puede ser válido en todo lo demás —bien formado, encadenado hasta
la Autoridad Certificadora Raíz, dentro de su vigencia— y aun así no servir,
porque el prestador lo revocó. Pasa cuando alguien pierde el token, deja la
empresa, o la clave se compromete.

Es la última comprobación que faltaba, y va aparte de todas las demás por una
razón: **es la única que necesita salir a la red**. Una llamada de red silenciosa
dentro de lo que parece una función local es una sorpresa desagradable, así que
esto nunca se ejecuta por omisión: hay que pedirlo.

De dónde salen las direcciones
------------------------------

Del propio certificado. Todo certificado cualificado declara sus puntos de
consulta en dos extensiones estándar:

- **AIA / OCSP** (RFC 6960): una consulta puntual por número de serie. Se
  pregunta por un certificado y se recibe una respuesta firmada.
- **CRL** (RFC 5280): la lista completa de revocados del prestador.

Se intenta OCSP primero y la CRL como respaldo. No es una preferencia estética:
la CRL de un prestador real pesa cerca de un mega y trae diecinueve mil
revocados, mientras que la respuesta OCSP para el mismo certificado son dos
kilobytes.

Que las direcciones salgan del certificado y no de una tabla tiene la misma
consecuencia buena que en :mod:`pysifen.pki.cadena`: un prestador nuevo funciona
sin tocar código.

Lo que se responde no se cree porque sí
---------------------------------------

Una respuesta OCSP sin verificar no vale nada: cualquiera que intercepte la
conexión puede contestar "vigente". Así que se comprueba la firma de la
respuesta, y que quien la firmó sea el emisor del certificado o un respondedor
que el emisor delegó explícitamente —con ``id-kp-OCSPSigning`` en su Extended
Key Usage, como manda el RFC 6960—. Lo mismo con la CRL: se verifica su firma
contra la clave del emisor antes de mirar su contenido.

Si algo de eso no cierra, el resultado es **desconocido**, nunca "vigente". No
poder comprobar no es lo mismo que comprobar que está bien.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Final

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.x509 import ocsp
from cryptography.x509.oid import (
    AuthorityInformationAccessOID,
    CRLEntryExtensionOID,
    ExtendedKeyUsageOID,
    ExtensionOID,
)

from pysifen.pki.cadena import ListaDeConfianza, _buscar_emisor, lista_de_confianza
from pysifen.pki.certificado import Certificado
from pysifen.tiempo import ahora, con_zona

__all__ = [
    "TIEMPO_LIMITE",
    "EstadoDeRevocacion",
    "ResultadoDeRevocacion",
    "consultar_revocacion",
]

#: Segundos de espera por cada consulta. Una CRL grande tarda.
TIEMPO_LIMITE: Final = 20

#: Tope de una CRL, para no descargar algo desmedido.
_LIMITE_DE_CRL: Final = 16 * 1024 * 1024

#: Cortesía y diagnóstico: algún respondedor rechaza los pedidos sin esto.
_AGENTE: Final = "pysifen/consulta-de-revocacion"


class EstadoDeRevocacion(StrEnum):
    """En qué quedó la consulta.

    Attributes:
        VIGENTE: el prestador confirma que el certificado no está revocado.
        REVOCADO: el prestador lo dio de baja.
        DESCONOCIDO: no se pudo averiguar. **No** equivale a vigente.
    """

    VIGENTE = "vigente"
    REVOCADO = "revocado"
    DESCONOCIDO = "desconocido"


@dataclass(frozen=True, slots=True)
class ResultadoDeRevocacion:
    """Lo que dijo el prestador sobre un certificado.

    Attributes:
        estado: el veredicto.
        fuente: ``OCSP`` o ``CRL``, según de dónde salió.
        consultado: la dirección que respondió.
        revocado_el: cuándo se revocó, si se revocó.
        razon: por qué lo revocó el prestador, cuando lo declara.
        motivo: por qué no se pudo averiguar, cuando no se pudo.
    """

    estado: EstadoDeRevocacion
    fuente: str | None = None
    consultado: str | None = None
    revocado_el: datetime | None = None
    razon: str | None = None
    motivo: str | None = None

    @property
    def revocado(self) -> bool:
        """``True`` sólo si el prestador confirmó la baja."""
        return self.estado is EstadoDeRevocacion.REVOCADO

    @property
    def comprobado(self) -> bool:
        """``True`` si se obtuvo una respuesta, sea cual fuere."""
        return self.estado is not EstadoDeRevocacion.DESCONOCIDO


def consultar_revocacion(
    certificado: Certificado,
    *,
    emisor: x509.Certificate | None = None,
    lista: ListaDeConfianza | None = None,
    momento: datetime | None = None,
    tiempo_limite: int = TIEMPO_LIMITE,
) -> ResultadoDeRevocacion:
    """Pregunta al prestador si el certificado sigue vigente.

    **Sale a la red.** Intenta OCSP y, si no se puede, la lista de revocados.

    Args:
        certificado: el certificado a consultar, normalmente el que viene dentro
            de un documento recibido.
        emisor: el certificado de la autoridad que lo emitió. Si no se pasa, se
            busca en la lista de confianza comprobando la firma.
        lista: las anclas donde buscar al emisor. Por omisión, la Lista de
            Confianza que trae la librería.
        momento: instante contra el que evaluar la revocación. Por omisión,
            ahora. Para un documento recibido conviene pasar la fecha de su
            firma: lo que importa es si el certificado estaba revocado **cuando
            se firmó**.
        tiempo_limite: segundos de espera por consulta.

    Returns:
        El resultado. Si no se pudo averiguar, ``DESCONOCIDO`` con el motivo, no
        una excepción: que un servidor esté caído es un caso esperado.

    Example:
        >>> resultado = consultar_revocacion(certificado)  # doctest: +SKIP
        >>> resultado.estado, resultado.fuente  # doctest: +SKIP
        (<EstadoDeRevocacion.VIGENTE: 'vigente'>, 'OCSP')
    """
    autoridad = emisor or _emisor_de(certificado, lista)
    if autoridad is None:
        return ResultadoDeRevocacion(
            EstadoDeRevocacion.DESCONOCIDO,
            motivo=(
                "no encontré el certificado de la autoridad que lo emitió, así "
                "que no hay contra qué verificar la respuesta"
            ),
        )

    instante = con_zona(momento) if momento else ahora()
    problemas: list[str] = []

    for url in _direcciones_ocsp(certificado.x509):
        resultado = _por_ocsp(certificado.x509, autoridad, url, tiempo_limite, instante)
        if resultado.comprobado:
            return resultado
        if resultado.motivo:
            problemas.append(f"OCSP {url}: {resultado.motivo}")

    for url in _direcciones_crl(certificado.x509):
        resultado = _por_crl(certificado.x509, autoridad, url, tiempo_limite, instante)
        if resultado.comprobado:
            return resultado
        if resultado.motivo:
            problemas.append(f"CRL {url}: {resultado.motivo}")

    return ResultadoDeRevocacion(
        EstadoDeRevocacion.DESCONOCIDO,
        motivo="; ".join(problemas)
        or "el certificado no declara dónde consultar su revocación",
    )


def _emisor_de(
    certificado: Certificado, lista: ListaDeConfianza | None
) -> x509.Certificate | None:
    """Busca en la lista de confianza la autoridad que firmó el certificado."""
    autoridad = _buscar_emisor(certificado.x509, lista or lista_de_confianza())
    return autoridad.certificado if autoridad else None


def _direcciones_ocsp(certificado: x509.Certificate) -> list[str]:
    """Devuelve los respondedores OCSP que el certificado declara."""
    try:
        acceso = certificado.extensions.get_extension_for_oid(
            ExtensionOID.AUTHORITY_INFORMATION_ACCESS
        ).value
    except x509.ExtensionNotFound:
        return []
    return [
        d.access_location.value
        for d in acceso  # type: ignore[attr-defined]
        if d.access_method == AuthorityInformationAccessOID.OCSP
        and isinstance(d.access_location, x509.UniformResourceIdentifier)
    ]


def _direcciones_crl(certificado: x509.Certificate) -> list[str]:
    """Devuelve los puntos de distribución de la lista de revocados."""
    try:
        puntos = certificado.extensions.get_extension_for_oid(
            ExtensionOID.CRL_DISTRIBUTION_POINTS
        ).value
    except x509.ExtensionNotFound:
        return []
    return [
        nombre.value
        for punto in puntos  # type: ignore[attr-defined]
        for nombre in (punto.full_name or [])
        if isinstance(nombre, x509.UniformResourceIdentifier)
    ]


def _pedir(
    url: str, tiempo_limite: int, datos: bytes | None = None, tipo: str | None = None
) -> bytes:
    """Hace una consulta HTTP y devuelve el cuerpo."""
    cabeceras = {"User-Agent": _AGENTE}
    if tipo:
        cabeceras["Content-Type"] = tipo
    peticion = urllib.request.Request(url, data=datos, headers=cabeceras)  # noqa: S310
    if peticion.type not in {"http", "https"}:
        raise ValueError(f"esquema no admitido: {peticion.type}")
    with urllib.request.urlopen(peticion, timeout=tiempo_limite) as respuesta:  # noqa: S310
        cuerpo: bytes = respuesta.read(_LIMITE_DE_CRL + 1)
    if len(cuerpo) > _LIMITE_DE_CRL:
        raise ValueError("la respuesta supera el tope de tamaño")
    return cuerpo


def _por_ocsp(
    certificado: x509.Certificate,
    emisor: x509.Certificate,
    url: str,
    tiempo_limite: int,
    momento: datetime,
) -> ResultadoDeRevocacion:
    """Consulta un respondedor OCSP y verifica lo que conteste."""
    try:
        pedido = (
            ocsp.OCSPRequestBuilder()
            .add_certificate(certificado, emisor, hashes.SHA1())  # noqa: S303
            .build()
        )
        cuerpo = _pedir(
            url,
            tiempo_limite,
            pedido.public_bytes(serialization.Encoding.DER),
            "application/ocsp-request",
        )
        respuesta = ocsp.load_der_ocsp_response(cuerpo)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return ResultadoDeRevocacion(EstadoDeRevocacion.DESCONOCIDO, motivo=str(exc))

    if respuesta.response_status is not ocsp.OCSPResponseStatus.SUCCESSFUL:
        return ResultadoDeRevocacion(
            EstadoDeRevocacion.DESCONOCIDO,
            motivo=f"el respondedor contestó {respuesta.response_status.name}",
        )

    if respuesta.serial_number != certificado.serial_number:
        return ResultadoDeRevocacion(
            EstadoDeRevocacion.DESCONOCIDO,
            motivo="la respuesta es sobre otro certificado",
        )

    problema = _verificar_respuesta_ocsp(respuesta, emisor)
    if problema:
        return ResultadoDeRevocacion(EstadoDeRevocacion.DESCONOCIDO, motivo=problema)

    if respuesta.certificate_status is ocsp.OCSPCertStatus.REVOKED:
        revocado_el = respuesta.revocation_time_utc
        if revocado_el and momento < revocado_el:
            # Se revocó DESPUES del momento evaluado: cuando se firmó, servía.
            return ResultadoDeRevocacion(
                EstadoDeRevocacion.VIGENTE,
                fuente="OCSP",
                consultado=url,
                motivo=(
                    f"se revocó el {revocado_el:%d/%m/%Y}, después del momento evaluado"
                ),
            )
        return ResultadoDeRevocacion(
            EstadoDeRevocacion.REVOCADO,
            fuente="OCSP",
            consultado=url,
            revocado_el=revocado_el,
            razon=respuesta.revocation_reason.name
            if respuesta.revocation_reason
            else None,
        )

    if respuesta.certificate_status is ocsp.OCSPCertStatus.UNKNOWN:
        return ResultadoDeRevocacion(
            EstadoDeRevocacion.DESCONOCIDO,
            motivo="el respondedor no conoce este certificado",
        )

    return ResultadoDeRevocacion(
        EstadoDeRevocacion.VIGENTE, fuente="OCSP", consultado=url
    )


def _verificar_respuesta_ocsp(
    respuesta: ocsp.OCSPResponse, emisor: x509.Certificate
) -> str | None:
    """Comprueba que la respuesta la firmó quien corresponde.

    Devuelve el motivo del rechazo, o ``None`` si está bien. Sin esto, cualquiera
    que intercepte la conexión podría contestar "vigente".
    """
    firmante, problema = _firmante_ocsp(respuesta, emisor)
    if firmante is None:
        return problema

    try:
        _verificar_firma(
            firmante.public_key(),
            respuesta.signature,
            respuesta.tbs_response_bytes,
            respuesta.signature_hash_algorithm,
        )
    except InvalidSignature:
        return "la firma de la respuesta no verifica"
    except Exception as exc:  # pragma: no cover - depende del respondedor
        return f"no pude verificar la firma de la respuesta: {exc}"

    ahora = datetime.now(UTC)
    siguiente = respuesta.next_update_utc
    if siguiente and siguiente < ahora:
        return f"la respuesta caducó el {siguiente:%d/%m/%Y}"
    return None


def _firmante_ocsp(
    respuesta: ocsp.OCSPResponse, emisor: x509.Certificate
) -> tuple[x509.Certificate | None, str | None]:
    """Devuelve el certificado que firmó la respuesta, si es admisible.

    O bien la firmó el propio emisor, o bien un respondedor al que el emisor
    delegó: tiene que estar emitido por él y llevar ``id-kp-OCSPSigning``, como
    manda el apartado 4.2.2.2 del RFC 6960.
    """
    if not respuesta.certificates:
        return emisor, None

    delegado = respuesta.certificates[0]
    try:
        delegado.verify_directly_issued_by(emisor)
    except Exception:
        return None, "el respondedor no fue delegado por el emisor del certificado"

    try:
        usos = delegado.extensions.get_extension_for_oid(
            ExtensionOID.EXTENDED_KEY_USAGE
        ).value
    except x509.ExtensionNotFound:
        return None, "el respondedor no declara que pueda firmar respuestas OCSP"

    if ExtendedKeyUsageOID.OCSP_SIGNING not in usos:  # type: ignore[operator]
        return None, "el respondedor no está habilitado para firmar respuestas OCSP"
    return delegado, None


def _verificar_firma(
    clave: Any,
    firma: bytes,
    contenido: bytes,
    algoritmo: hashes.HashAlgorithm | None,
) -> None:
    """Verifica una firma con la clave que sea, RSA o de curva elíptica."""
    if algoritmo is None:
        raise InvalidSignature("la respuesta no declara su algoritmo de resumen")
    if isinstance(clave, rsa.RSAPublicKey):
        clave.verify(firma, contenido, padding.PKCS1v15(), algoritmo)
        return
    if isinstance(clave, ec.EllipticCurvePublicKey):
        clave.verify(firma, contenido, ec.ECDSA(algoritmo))
        return
    raise InvalidSignature("el firmante usa un tipo de clave que no manejo")


def _por_crl(
    certificado: x509.Certificate,
    emisor: x509.Certificate,
    url: str,
    tiempo_limite: int,
    momento: datetime,
) -> ResultadoDeRevocacion:
    """Descarga la lista de revocados del prestador y busca el certificado."""
    try:
        crudo = _pedir(url, tiempo_limite)
        lista = _leer_crl(crudo)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return ResultadoDeRevocacion(EstadoDeRevocacion.DESCONOCIDO, motivo=str(exc))

    clave = emisor.public_key()
    if not isinstance(clave, rsa.RSAPublicKey | ec.EllipticCurvePublicKey):
        return ResultadoDeRevocacion(
            EstadoDeRevocacion.DESCONOCIDO,
            motivo="el emisor usa un tipo de clave que no manejo",
        )
    if not lista.is_signature_valid(clave):
        return ResultadoDeRevocacion(
            EstadoDeRevocacion.DESCONOCIDO,
            motivo="la lista no está firmada por el emisor del certificado",
        )

    entrada = lista.get_revoked_certificate_by_serial_number(certificado.serial_number)
    if entrada is None:
        return ResultadoDeRevocacion(
            EstadoDeRevocacion.VIGENTE, fuente="CRL", consultado=url
        )

    revocado_el = entrada.revocation_date_utc
    if momento < revocado_el:
        return ResultadoDeRevocacion(
            EstadoDeRevocacion.VIGENTE,
            fuente="CRL",
            consultado=url,
            motivo=(
                f"se revocó el {revocado_el:%d/%m/%Y}, después del momento evaluado"
            ),
        )
    return ResultadoDeRevocacion(
        EstadoDeRevocacion.REVOCADO,
        fuente="CRL",
        consultado=url,
        revocado_el=revocado_el,
        razon=_razon(entrada),
    )


def _leer_crl(crudo: bytes) -> x509.CertificateRevocationList:
    """Interpreta una lista de revocados, venga en DER o en PEM."""
    try:
        return x509.load_der_x509_crl(crudo)
    except ValueError:
        return x509.load_pem_x509_crl(crudo)


def _razon(entrada: x509.RevokedCertificate) -> str | None:
    """Devuelve el motivo de la revocación, si la entrada lo declara."""
    try:
        extension = entrada.extensions.get_extension_for_oid(
            CRLEntryExtensionOID.CRL_REASON
        )
    except x509.ExtensionNotFound:
        return None
    return str(extension.value.reason.name)  # type: ignore[attr-defined]
