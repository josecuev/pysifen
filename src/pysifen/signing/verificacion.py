"""Verificación de la firma de un documento recibido.

Firmar y verificar son operaciones distintas y las necesita gente distinta.
Quien **emite** firma; quien **recibe** verifica, y para eso no necesita ningún
certificado propio: el documento trae adentro el certificado del emisor.

Qué se comprueba acá, siguiendo el apartado 7.8 del Manual Técnico:

1. Que el resumen declarado corresponda al contenido firmado. Si alguien
   modificó un solo carácter del documento, esto falla.
2. Que la firma corresponda al ``SignedInfo`` y al certificado que el documento
   declara.

Qué **no** se comprueba acá, a propósito:

- La cadena de confianza hasta la Autoridad Certificadora Raíz.
- La lista de certificados revocados.

Eso vive en :mod:`pysifen.lectura`, que reúne todas las comprobaciones en un
informe. Este módulo hace sólo la parte criptográfica, que es la que tiene que
ser exacta.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from lxml import etree

from pysifen.pki.certificado import Certificado
from pysifen.signing.xmldsig import C14N_EXCLUSIVO, NS_XMLDSIG

__all__ = ["ResultadoDeFirma", "verificar_firma"]


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
        motivo: por qué falló, cuando falló.
    """

    tiene_firma: bool
    resumen_coincide: bool | None = None
    firma_coincide: bool | None = None
    certificado: Certificado | None = None
    referencia: str | None = None
    motivo: str | None = None

    @property
    def valida(self) -> bool:
        """``True`` sólo si el resumen y la firma cierran los dos."""
        return bool(self.tiene_firma and self.resumen_coincide and self.firma_coincide)


def verificar_firma(raiz: etree._Element) -> ResultadoDeFirma:
    """Verifica la firma de un documento ya interpretado.

    Args:
        raiz: el elemento ``rDE`` con su ``Signature`` adentro.

    Returns:
        El resultado, que nunca lanza por un documento mal formado: un
        documento adulterado es un caso esperado, no un error del programa.

    Example:
        >>> resultado = verificar_firma(arbol)  # doctest: +SKIP
        >>> resultado.valida  # doctest: +SKIP
        True
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

    resumen_coincide, motivo = _comprobar_resumen(raiz, referencia, uri)
    if motivo is not None:
        return ResultadoDeFirma(
            tiene_firma=True,
            resumen_coincide=resumen_coincide,
            certificado=certificado,
            referencia=uri,
            motivo=motivo,
        )

    firma_coincide, motivo = _comprobar_firma(info, valor.text, certificado)

    return ResultadoDeFirma(
        tiene_firma=True,
        resumen_coincide=resumen_coincide,
        firma_coincide=firma_coincide,
        certificado=certificado,
        referencia=uri,
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


def _comprobar_resumen(
    raiz: etree._Element, referencia: etree._Element, uri: str
) -> tuple[bool | None, str | None]:
    """Recalcula el resumen del elemento firmado y lo compara con el declarado."""
    declarado = referencia.find(_ds("DigestValue"))
    if declarado is None or not declarado.text:
        return None, "la firma no declara el resumen del contenido"

    identificador = uri.removeprefix("#")
    firmado = None
    for elemento in raiz.iter():
        if elemento.get("Id") == identificador:
            firmado = elemento
            break
    if firmado is None:
        return (
            None,
            f"no encontré el elemento con Id={identificador!r} que la firma referencia",
        )

    exclusiva = any(
        t.get("Algorithm") == C14N_EXCLUSIVO for t in referencia.iter(_ds("Transform"))
    )
    canonico = etree.tostring(
        etree.fromstring(etree.tostring(firmado)),
        method="c14n",
        exclusive=exclusiva,
        with_comments=False,
    )
    calculado = base64.b64encode(hashlib.sha256(canonico).digest()).decode()

    if calculado != declarado.text.strip():
        return False, "el contenido no corresponde al resumen firmado: fue alterado"
    return True, None


def _comprobar_firma(
    info: etree._Element,
    valor: str,
    certificado: Certificado | None,
) -> tuple[bool | None, str | None]:
    """Verifica la firma del ``SignedInfo`` con la clave del certificado."""
    if certificado is None:
        return None, "el documento no trae un certificado legible en su KeyInfo"

    metodo = info.find(_ds("CanonicalizationMethod"))
    exclusiva = metodo is not None and metodo.get("Algorithm") == C14N_EXCLUSIVO

    # El SignedInfo se canonicaliza dentro de su documento, para que herede los
    # espacios de nombres igual que cuando se lo firmó.
    canonico = etree.tostring(
        info, method="c14n", exclusive=exclusiva, with_comments=False
    )

    clave = certificado.x509.public_key()
    if not isinstance(clave, rsa.RSAPublicKey):
        return None, "el certificado no tiene una clave RSA"

    try:
        clave.verify(
            base64.b64decode(valor),
            canonico,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except InvalidSignature:
        return False, "la firma no corresponde al certificado del documento"
    except Exception as exc:
        return None, f"no pude verificar la firma: {exc}"

    return True, None
