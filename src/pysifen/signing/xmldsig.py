"""Firma XMLDSig de los documentos electrónicos.

Implementa los apartados 7.6 y 7.7 del Manual Técnico SIFEN v150.

La firma abarca el grupo ``A001`` —el elemento ``DE``— identificado por su
atributo ``Id``, cuyo valor es el CDC. El mismo CDC, precedido por ``#``, va en
el atributo ``URI`` del ``Reference``.

Las dos particularidades del SIFEN
----------------------------------

**1. Mezcla las dos canonicalizaciones.** El manual pide c14n *inclusivo*
(``REC-xml-c14n-20010315``) en el ``CanonicalizationMethod`` del ``SignedInfo``,
y c14n *exclusivo* (``xml-exc-c14n#``) en el ``Transform`` de la ``Reference``.
No es un error de tipeo del manual: hay que respetarlo tal cual o la firma no
valida del otro lado.

**2. La firma no está adentro de lo firmado.** El manual declara la
transformación ``enveloped-signature``, pero en su propio ejemplo el
``Signature`` es *hermano* del ``DE``, los dos colgando de ``rDE``. Con esa
disposición la transformación no tiene nada que quitar. Se declara igual, porque
el manual la exige, y se aplica de forma defensiva por si algún emisor coloca la
firma dentro del ``DE``.

Elementos prohibidos
--------------------

El apartado 7.6 prohíbe que el documento firmado lleve ``X509SubjectName``,
``X509IssuerSerial``, ``X509IssuerName`` y ``X509SKI``, y desaconseja
``KeyValue``, ``RSAKeyValue``, ``Modulus`` y ``Exponent``: son datos que el
SIFEN saca del propio certificado. El ``KeyInfo`` que genera este módulo lleva
únicamente ``X509Data/X509Certificate``.
"""

from __future__ import annotations

import base64
import hashlib
from typing import TYPE_CHECKING, Final

from lxml import etree

from pysifen.exceptions import FirmaError

if TYPE_CHECKING:  # pragma: no cover
    from pysifen.signing.ports import Firmante

__all__ = [
    "ALGORITMO_DIGEST",
    "ALGORITMO_FIRMA",
    "C14N_EXCLUSIVO",
    "C14N_INCLUSIVO",
    "NS_SIFEN",
    "NS_XMLDSIG",
    "TRANSFORMACION_ENVELOPED",
    "firmar_documento",
    "firmar_elemento",
]

#: Espacio de nombres de los documentos electrónicos del SIFEN.
NS_SIFEN: Final = "http://ekuatia.set.gov.py/sifen/xsd"

#: Espacio de nombres de la firma digital XML, según el W3C.
NS_XMLDSIG: Final = "http://www.w3.org/2000/09/xmldsig#"

#: Canonicalización inclusiva, la del ``SignedInfo``.
C14N_INCLUSIVO: Final = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"

#: Canonicalización exclusiva, la del ``Transform`` de la ``Reference``.
C14N_EXCLUSIVO: Final = "http://www.w3.org/2001/10/xml-exc-c14n#"

#: Transformación que excluye a la propia firma de lo firmado.
TRANSFORMACION_ENVELOPED: Final = (
    "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
)

#: Algoritmo de firma: RSA con SHA-256 (7.7).
ALGORITMO_FIRMA: Final = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"

#: Algoritmo de resumen: SHA-256 (7.7).
ALGORITMO_DIGEST: Final = "http://www.w3.org/2001/04/xmlenc#sha256"


def _ds(etiqueta: str) -> str:
    """Devuelve el nombre calificado de un elemento de la firma."""
    return f"{{{NS_XMLDSIG}}}{etiqueta}"


def _canonicalizar(elemento: etree._Element, *, exclusivo: bool) -> bytes:
    """Canonicaliza un elemento en el contexto de su documento.

    Args:
        elemento: el elemento a canonicalizar.
        exclusivo: ``True`` para c14n exclusiva, ``False`` para la inclusiva.

    Returns:
        La forma canónica en bytes.
    """
    return etree.tostring(
        elemento,
        method="c14n",
        exclusive=exclusivo,
        with_comments=False,
    )


def _aplicar_enveloped(elemento: etree._Element) -> etree._Element:
    """Quita del subárbol cualquier firma que hubiera adentro.

    Con la disposición que muestra el manual la firma es hermana del ``DE`` y
    esta función no encuentra nada que sacar. Se aplica igual porque la
    transformación está declarada en la ``Reference`` y tiene que ser cierta.

    Returns:
        Una copia del elemento sin nodos ``Signature``, o el mismo elemento si
        no había ninguno.
    """
    if elemento.find(f".//{_ds('Signature')}") is None:
        return elemento

    copia = etree.fromstring(etree.tostring(elemento))
    for firma in copia.findall(f".//{_ds('Signature')}"):
        padre = firma.getparent()
        if padre is not None:
            padre.remove(firma)
    return copia


def _buscar_por_id(raiz: etree._Element, identificador: str) -> etree._Element:
    """Busca el elemento cuyo atributo ``Id`` coincide.

    Raises:
        FirmaError: si no aparece ninguno.
    """
    for elemento in raiz.iter():
        if elemento.get("Id") == identificador:
            return elemento
    raise FirmaError(
        f"no encontré ningún elemento con Id={identificador!r} para firmar"
    )


def firmar_elemento(
    raiz: etree._Element,
    firmante: Firmante,
    *,
    identificador: str | None = None,
) -> etree._Element:
    """Firma un elemento del árbol y agrega la firma como hermano.

    Modifica el árbol recibido: agrega el ``Signature`` como último hijo de la
    raíz, que es la disposición que muestra el manual.

    Args:
        raiz: el elemento ``rDE``, que contiene al ``DE`` y albergará la firma.
        firmante: quien firma. Ver :class:`~pysifen.signing.ports.Firmante`.
        identificador: valor del atributo ``Id`` del elemento a firmar, o sea el
            CDC. Si no se pasa, se toma el del primer elemento que tenga ``Id``.

    Returns:
        El elemento ``Signature`` recién creado.

    Raises:
        FirmaError: si no se encuentra el elemento a firmar, o si el firmante
            falla.
    """
    if identificador is None:
        identificador = _detectar_identificador(raiz)

    firmado = _buscar_por_id(raiz, identificador)

    # Paso 1: resumen del elemento firmado, con la transformación declarada y
    # canonicalización exclusiva.
    transformado = _aplicar_enveloped(firmado)
    digest = hashlib.sha256(_canonicalizar(transformado, exclusivo=True)).digest()

    # Paso 2: armar el SignedInfo y colgarlo del árbol, para que la
    # canonicalización inclusiva vea los espacios de nombres heredados igual
    # que los verá quien valide.
    firma = etree.SubElement(raiz, _ds("Signature"))
    info = etree.SubElement(firma, _ds("SignedInfo"))

    etree.SubElement(info, _ds("CanonicalizationMethod"), Algorithm=C14N_INCLUSIVO)
    etree.SubElement(info, _ds("SignatureMethod"), Algorithm=ALGORITMO_FIRMA)

    referencia = etree.SubElement(info, _ds("Reference"), URI=f"#{identificador}")
    transformaciones = etree.SubElement(referencia, _ds("Transforms"))
    etree.SubElement(
        transformaciones, _ds("Transform"), Algorithm=TRANSFORMACION_ENVELOPED
    )
    etree.SubElement(transformaciones, _ds("Transform"), Algorithm=C14N_EXCLUSIVO)
    etree.SubElement(referencia, _ds("DigestMethod"), Algorithm=ALGORITMO_DIGEST)
    etree.SubElement(referencia, _ds("DigestValue")).text = base64.b64encode(
        digest
    ).decode()

    # Paso 3: firmar el SignedInfo canonicalizado de forma inclusiva.
    try:
        firmado_crudo = firmante.firmar(_canonicalizar(info, exclusivo=False))
    except FirmaError:
        raiz.remove(firma)
        raise
    except Exception as exc:
        raiz.remove(firma)
        raise FirmaError(f"el firmante no pudo firmar: {exc}") from exc

    etree.SubElement(firma, _ds("SignatureValue")).text = base64.b64encode(
        firmado_crudo
    ).decode()

    # Paso 4: KeyInfo con el certificado y nada más (7.6).
    informacion = etree.SubElement(firma, _ds("KeyInfo"))
    datos = etree.SubElement(informacion, _ds("X509Data"))
    etree.SubElement(datos, _ds("X509Certificate")).text = _certificado_en_base64(
        firmante
    )

    return firma


def firmar_documento(
    xml: bytes | str,
    firmante: Firmante,
    *,
    identificador: str | None = None,
) -> bytes:
    """Firma un documento electrónico completo.

    Args:
        xml: el ``rDE`` sin firmar, en bytes o texto.
        firmante: quien firma.
        identificador: CDC del documento a firmar. Si no se pasa, se toma el
            atributo ``Id`` del primer elemento que lo tenga.

    Returns:
        El documento firmado, serializado en UTF-8.

    Raises:
        FirmaError: si el XML no se puede interpretar, si no hay elemento con
            ``Id``, o si el firmante falla.

    Example:
        >>> firmado = firmar_documento(rde_sin_firma, firmante)  # doctest: +SKIP
    """
    crudo = xml.encode() if isinstance(xml, str) else xml

    analizador = etree.XMLParser(
        resolve_entities=False, no_network=True, huge_tree=False
    )
    try:
        raiz = etree.fromstring(crudo, parser=analizador)
    except etree.XMLSyntaxError as exc:
        raise FirmaError(f"el XML a firmar no es válido: {exc}") from exc

    firmar_elemento(raiz, firmante, identificador=identificador)
    return etree.tostring(raiz, encoding="UTF-8", xml_declaration=True)


def _detectar_identificador(raiz: etree._Element) -> str:
    """Devuelve el ``Id`` del primer elemento que lo tenga.

    Raises:
        FirmaError: si ningún elemento del árbol tiene ``Id``.
    """
    for elemento in raiz.iter():
        identificador = elemento.get("Id")
        if identificador:
            return identificador
    raise FirmaError(
        "el documento no tiene ningún elemento con atributo Id; el manual "
        "exige que el DE lleve el CDC en ese atributo (7.6)"
    )


def _certificado_en_base64(firmante: Firmante) -> str:
    """Devuelve el certificado del firmante en base64, sin cabeceras PEM."""
    from cryptography.hazmat.primitives.serialization import Encoding

    der = firmante.certificado.x509.public_bytes(Encoding.DER)
    return base64.b64encode(der).decode()
