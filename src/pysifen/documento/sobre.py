"""Armado del sobre ``rDE`` que envuelve al documento electrónico.

Los modelos de los grupos viven en :mod:`pysifen.documento._generado`, que sale
del esquema oficial. Acá está sólo lo que el esquema no puede expresar: dónde va
el CDC —que es un atributo, no un elemento— y en qué momento se inserta la
firma.

El orden de las operaciones importa y no es negociable:

1. Se arma el ``rDE`` con el ``DE`` adentro, y el CDC como atributo ``Id``.
2. Se **firma**, lo que inserta el ``Signature`` como hermano del ``DE``.
3. Se agrega el ``gCamFuFD`` con el QR, que va **después** de la firma porque
   el QR incluye el ``DigestValue`` que la firma acaba de producir.

Invertir 2 y 3 produce un QR que no verifica.
"""

from __future__ import annotations

from typing import Any, Final

from lxml import etree

from pysifen.documento._generado import DocumentoElectronico

__all__ = [
    "NS_SIFEN",
    "VERSION_DEL_FORMATO",
    "agregar_campos_fuera_de_firma",
    "sobre_rde",
]

#: Versión del formato que exige el manual en el campo ``dVerFor``.
VERSION_DEL_FORMATO: Final = 150

#: Espacio de nombres de los documentos electrónicos del SIFEN.
NS_SIFEN: Final = "http://ekuatia.set.gov.py/sifen/xsd"


def _calificar(etiqueta: str, espacio: str | None) -> str:
    """Antepone el espacio de nombres a una etiqueta, si lo hay."""
    return f"{{{espacio}}}{etiqueta}" if espacio else etiqueta


def sobre_rde(
    documento: DocumentoElectronico,
    cdc: str,
    *,
    espacio: str | None = NS_SIFEN,
) -> etree._Element:
    """Arma el ``rDE`` listo para firmar.

    Args:
        documento: el ``DE`` ya poblado.
        cdc: el Código de Control. Va como atributo ``Id`` del ``DE``, que es a
            lo que apunta la ``Reference`` de la firma.
        espacio: espacio de nombres a aplicar. Por omisión, el del SIFEN.

    Returns:
        El elemento ``rDE``, sin firma todavía.

    Example:
        >>> raiz = sobre_rde(documento, cdc.valor)  # doctest: +SKIP
        >>> firmar_elemento(raiz, firmante)  # doctest: +SKIP
        >>> agregar_campos_fuera_de_firma(raiz, url_del_qr)  # doctest: +SKIP
    """
    # lxml admite None como clave del nsmap para declarar el espacio por
    # omisión; los stubs lo tipan como Mapping[str, str] y no lo contemplan.
    nsmap: Any = {None: espacio} if espacio else None
    raiz = etree.Element(_calificar("rDE", espacio), nsmap=nsmap)

    version = etree.SubElement(raiz, _calificar("dVerFor", espacio))
    version.text = str(VERSION_DEL_FORMATO)

    elemento = documento.a_elemento(espacio)
    elemento.set("Id", cdc)
    raiz.append(elemento)

    return raiz


def agregar_campos_fuera_de_firma(
    raiz: etree._Element,
    url_del_qr: str,
    *,
    informacion_adicional: str | None = None,
    espacio: str | None = NS_SIFEN,
) -> etree._Element:
    """Agrega el ``gCamFuFD`` con el QR, después de la firma.

    El nombre del grupo lo dice: son los *campos fuera de la firma*. Van al
    final del ``rDE``, detrás del ``Signature``, y quedan deliberadamente fuera
    de lo firmado porque el QR se calcula **a partir** de la firma: incluye su
    ``DigestValue``.

    Args:
        raiz: el ``rDE`` ya firmado.
        url_del_qr: la URL que devuelve
            :func:`~pysifen.qr.generar_url_qr`.
        informacion_adicional: campo ``dInfAdic``, si corresponde.
        espacio: espacio de nombres a aplicar.

    Returns:
        El elemento ``gCamFuFD`` recién creado.

    Raises:
        ValueError: si el documento todavía no está firmado. Agregar el QR
            antes de firmar produciría un QR que no verifica.
    """
    firma = raiz.find("{http://www.w3.org/2000/09/xmldsig#}Signature")
    if firma is None:
        raise ValueError(
            "hay que firmar antes de agregar el QR: el QR incluye el "
            "DigestValue que produce la firma"
        )

    grupo = etree.SubElement(raiz, _calificar("gCamFuFD", espacio))
    etree.SubElement(grupo, _calificar("dCarQR", espacio)).text = url_del_qr
    if informacion_adicional:
        etree.SubElement(
            grupo, _calificar("dInfAdic", espacio)
        ).text = informacion_adicional
    return grupo
