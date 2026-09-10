"""Verificación de la firma de un documento recibido.

Firmar y verificar son operaciones distintas y las necesita gente distinta.
Quien **emite** firma; quien **recibe** verifica, y para eso no necesita ningún
certificado propio: el documento trae adentro el certificado del emisor.

Qué se comprueba acá, siguiendo el apartado 7.8 del Manual Técnico:

1. Que el resumen declarado corresponda al contenido firmado. Si alguien
   modificó un carácter del documento, esto falla.
2. Que la firma corresponda al ``SignedInfo`` y al certificado que el documento
   declara.

Estricto primero, tolerante después, y siempre declarándolo
-----------------------------------------------------------

Los documentos que circulan de verdad no siempre verifican con la lectura más
estricta del estándar. Sobre cinco documentos reales de cinco emisores
distintos aparecieron dos desvíos, los dos del lado del emisor:

**El ``SignedInfo`` canonicalizado en aislamiento.** Con canonicalización
inclusiva, la lectura estricta dice que el ``SignedInfo`` hereda los espacios de
nombres de sus ancestros —en estos documentos, el ``xmlns:xsi`` del ``rDE``—.
Pero varios emisores arman la firma como documento aparte y recién después la
insertan, así que firman una forma sin ese espacio de nombres heredado. Dos de
los cinco documentos son así.

**El XML indentado después de firmar.** Un emisor formatea el XML para que se
lea mejor *después* de calcular la firma. La canonicalización conserva los
espacios entre elementos, así que el resumen deja de cerrar. Uno de los cinco
es así.

Ninguno de los dos desvíos debilita nada: el contenido sigue siendo el mismo y
la firma sigue probando su integridad. Por eso el verificador los tolera. Pero
**declara cuál toleró**, en :attr:`ResultadoDeFirma.tolerancias`, porque quien
audita tiene derecho a saber que el documento no era estrictamente conforme.

Lo que no se tolera es que el contenido no corresponda. Un documento así se
rechaza, y de los cinco reales hubo uno.

Qué no se comprueba acá
-----------------------

La cadena de confianza y la lista de certificados revocados. Eso vive en
:mod:`pysifen.lectura`, que reúne todas las comprobaciones en un informe. Este
módulo hace sólo la parte criptográfica.
"""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Iterator
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from lxml import etree

from pysifen.pki.certificado import Certificado
from pysifen.signing.xmldsig import C14N_EXCLUSIVO, NS_XMLDSIG

__all__ = [
    "TOLERANCIA_ESPACIOS_DE_NOMBRES",
    "TOLERANCIA_INDENTACION",
    "ResultadoDeFirma",
    "verificar_firma",
]

#: El emisor armó la firma como documento aparte antes de insertarla.
TOLERANCIA_ESPACIOS_DE_NOMBRES = (
    "el SignedInfo se canonicalizó en aislamiento, sin los espacios de nombres "
    "heredados del rDE: el emisor armó la firma como documento aparte"
)

#: El emisor formateó el XML después de calcular la firma.
TOLERANCIA_INDENTACION = (
    "se ignoró la indentación entre elementos: el emisor formateó el XML "
    "después de firmarlo"
)


def _ds(etiqueta: str) -> str:
    """Devuelve el nombre calificado de un elemento de la firma."""
    return f"{{{NS_XMLDSIG}}}{etiqueta}"


@dataclass(frozen=True, slots=True)
class ResultadoDeFirma:
    """Lo que se pudo determinar sobre la firma de un documento.

    Attributes:
        tiene_firma: si el documento trae un elemento ``Signature``.
        resumen_coincide: si el ``DigestValue`` declarado corresponde al
            contenido. ``None`` si no se pudo calcular.
        firma_coincide: si la firma verifica contra el certificado declarado.
            ``None`` si no se pudo comprobar.
        certificado: el certificado que el documento trae en su ``KeyInfo``.
        referencia: el valor del atributo ``URI`` de la ``Reference``, que en un
            documento del SIFEN es el CDC precedido por ``#``.
        tolerancias: qué desvíos del estándar hubo que tolerar para que la firma
            verifique. Vacío significa estrictamente conforme.
        motivo: por qué falló, cuando falló.
    """

    tiene_firma: bool
    resumen_coincide: bool | None = None
    firma_coincide: bool | None = None
    certificado: Certificado | None = None
    referencia: str | None = None
    tolerancias: tuple[str, ...] = field(default_factory=tuple)
    motivo: str | None = None

    @property
    def valida(self) -> bool:
        """``True`` sólo si el resumen y la firma cierran los dos."""
        return bool(self.tiene_firma and self.resumen_coincide and self.firma_coincide)

    @property
    def estrictamente_conforme(self) -> bool:
        """``True`` si verificó sin necesitar ninguna tolerancia."""
        return self.valida and not self.tolerancias


def verificar_firma(raiz: etree._Element) -> ResultadoDeFirma:
    """Verifica la firma de un documento ya interpretado.

    Args:
        raiz: el elemento ``rDE`` con su ``Signature`` adentro.

    Returns:
        El resultado, que nunca lanza por un documento mal formado: un documento
        adulterado es un caso esperado, no un error del programa.

    Example:
        >>> resultado = verificar_firma(arbol)  # doctest: +SKIP
        >>> resultado.valida  # doctest: +SKIP
        True
        >>> resultado.estrictamente_conforme  # doctest: +SKIP
        False
    """
    firma = raiz.find(_ds("Signature"))
    if firma is None:
        return ResultadoDeFirma(
            tiene_firma=False, motivo="el documento no está firmado"
        )

    info = firma.find(_ds("SignedInfo"))
    referencia = firma.find(f"{_ds('SignedInfo')}/{_ds('Reference')}")
    valor = firma.find(_ds("SignatureValue"))
    nodo_certificado = firma.find(
        f"{_ds('KeyInfo')}/{_ds('X509Data')}/{_ds('X509Certificate')}"
    )

    if info is None or referencia is None or valor is None or not valor.text:
        return ResultadoDeFirma(
            tiene_firma=True, motivo="la firma está incompleta: le faltan elementos"
        )

    certificado = _leer_certificado(nodo_certificado)
    uri = referencia.get("URI", "")
    tolerancias: list[str] = []

    resumen_coincide, motivo = _comprobar_resumen(raiz, referencia, uri, tolerancias)
    if motivo is not None:
        return ResultadoDeFirma(
            tiene_firma=True,
            resumen_coincide=resumen_coincide,
            certificado=certificado,
            referencia=uri,
            tolerancias=tuple(tolerancias),
            motivo=motivo,
        )

    firma_coincide, motivo = _comprobar_firma(
        info, valor.text, certificado, tolerancias
    )

    return ResultadoDeFirma(
        tiene_firma=True,
        resumen_coincide=resumen_coincide,
        firma_coincide=firma_coincide,
        certificado=certificado,
        referencia=uri,
        tolerancias=tuple(tolerancias),
        motivo=motivo,
    )


def _leer_certificado(nodo: etree._Element | None) -> Certificado | None:
    """Lee el certificado del ``KeyInfo``, si está y se puede interpretar."""
    if nodo is None or not nodo.text:
        return None
    try:
        return Certificado.desde_der(base64.b64decode(nodo.text))
    except Exception:
        return None


def _sin_indentacion(elemento: etree._Element) -> etree._Element | None:
    """Devuelve el elemento reinterpretado sin los espacios entre elementos."""
    try:
        analizador = etree.XMLParser(remove_blank_text=True, resolve_entities=False)
        return etree.fromstring(etree.tostring(elemento), parser=analizador)
    except etree.XMLSyntaxError:  # pragma: no cover - ya se interpretó una vez
        return None


def _canonicalizar(elemento: etree._Element, exclusiva: bool) -> bytes:
    """Canonicaliza un elemento con el algoritmo pedido."""
    return etree.tostring(
        elemento, method="c14n", exclusive=exclusiva, with_comments=False
    )


def _formas_del_contenido(
    firmado: etree._Element, exclusiva: bool
) -> Iterator[tuple[bytes, str | None]]:
    """Genera las formas canónicas admisibles del elemento firmado.

    Primero la estricta; después la que ignora la indentación, para los emisores
    que formatean el XML una vez firmado.
    """
    yield _canonicalizar(firmado, exclusiva), None
    compacto = _sin_indentacion(firmado)
    if compacto is not None:
        yield _canonicalizar(compacto, exclusiva), TOLERANCIA_INDENTACION


def _comprobar_resumen(
    raiz: etree._Element,
    referencia: etree._Element,
    uri: str,
    tolerancias: list[str],
) -> tuple[bool | None, str | None]:
    """Recalcula el resumen del elemento firmado y lo compara con el declarado."""
    declarado = referencia.find(_ds("DigestValue"))
    if declarado is None or not declarado.text:
        return None, "la firma no declara el resumen del contenido"

    identificador = uri.removeprefix("#")
    firmado = next((e for e in raiz.iter() if e.get("Id") == identificador), None)
    if firmado is None:
        return (
            None,
            f"no encontré el elemento con Id={identificador!r} que la firma referencia",
        )

    exclusiva = any(
        t.get("Algorithm") == C14N_EXCLUSIVO for t in referencia.iter(_ds("Transform"))
    )
    esperado = declarado.text.strip()

    for canonico, tolerancia in _formas_del_contenido(firmado, exclusiva):
        if base64.b64encode(hashlib.sha256(canonico).digest()).decode() == esperado:
            if tolerancia and tolerancia not in tolerancias:
                tolerancias.append(tolerancia)
            return True, None

    return False, "el contenido no corresponde al resumen firmado: fue alterado"


def _formas_del_signed_info(
    info: etree._Element, exclusiva: bool
) -> Iterator[tuple[bytes, str | None]]:
    """Genera las formas canónicas admisibles del ``SignedInfo``.

    Primero en el contexto del documento, que es la lectura estricta; después en
    aislamiento, que es lo que producen los emisores que arman la firma como
    documento aparte antes de insertarla. Y las dos también sin la indentación,
    para el emisor que formatea el XML una vez firmado.
    """
    yield _canonicalizar(info, exclusiva), None

    suelto = etree.fromstring(etree.tostring(info))
    yield _canonicalizar(suelto, exclusiva), TOLERANCIA_ESPACIOS_DE_NOMBRES

    compacto = _sin_indentacion(info)
    if compacto is None:  # pragma: no cover - ya se interpretó una vez
        return
    yield _canonicalizar(compacto, exclusiva), TOLERANCIA_INDENTACION
    yield (
        _canonicalizar(etree.fromstring(etree.tostring(compacto)), exclusiva),
        TOLERANCIA_ESPACIOS_DE_NOMBRES,
    )


def _comprobar_firma(
    info: etree._Element,
    valor: str,
    certificado: Certificado | None,
    tolerancias: list[str],
) -> tuple[bool | None, str | None]:
    """Verifica la firma del ``SignedInfo`` con la clave del certificado."""
    if certificado is None:
        return None, "el documento no trae un certificado legible en su KeyInfo"

    metodo = info.find(_ds("CanonicalizationMethod"))
    exclusiva = metodo is not None and metodo.get("Algorithm") == C14N_EXCLUSIVO

    clave = certificado.x509.public_key()
    if not isinstance(clave, rsa.RSAPublicKey):
        return None, "el certificado no tiene una clave RSA"

    try:
        firmado = base64.b64decode(valor)
    except Exception:
        return None, "el valor de la firma no está en base64"

    for canonico, tolerancia in _formas_del_signed_info(info, exclusiva):
        try:
            clave.verify(firmado, canonico, padding.PKCS1v15(), hashes.SHA256())
        except InvalidSignature:
            continue
        except Exception as exc:  # pragma: no cover - falla del backend
            return None, f"no pude verificar la firma: {exc}"
        if tolerancia and tolerancia not in tolerancias:
            tolerancias.append(tolerancia)
        return True, None

    return False, "la firma no corresponde al certificado del documento"
