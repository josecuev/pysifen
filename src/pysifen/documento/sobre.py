"""El sobre del documento electrónico y los grupos comunes a todo tipo de DE.

Cubre los grupos ``AA`` (formato electrónico XML), ``A`` (campos firmados),
``B`` (operación) y ``C`` (timbrado) del Manual Técnico SIFEN v150. Son los que
lleva **todo** documento electrónico, sea factura, autofactura, nota de crédito
o nota de remisión.

.. warning::
   Los grupos ``D`` a ``J`` todavía no están modelados. Un ``rDE`` armado sólo
   con lo de acá no es un documento válido para transmitir: le faltan los datos
   generales, los ítems y los totales. Ver el estado en el README.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import ClassVar

from lxml import etree
from pydantic import field_validator

from pysifen.documento.base import GrupoSifen, campo, campo_opcional
from pysifen.enums import TipoDocumento, TipoEmision

__all__ = [
    "VERSION_DEL_FORMATO",
    "DocumentoElectronico",
    "Operacion",
    "Timbrado",
    "sobre_rde",
]

#: Versión del formato que exige el manual en el campo ``dVerFor`` (AA002).
VERSION_DEL_FORMATO = 150

#: Espacio de nombres de los documentos electrónicos del SIFEN.
NS_SIFEN = "http://ekuatia.set.gov.py/sifen/xsd"


class Operacion(GrupoSifen):
    """Grupo B. Campos inherentes a la operación del DE (B001-B099).

    El elemento se llama ``gOpeDE``.
    """

    _etiqueta: ClassVar[str] = "gOpeDE"

    iTipEmi: TipoEmision = campo("B002", "Tipo de emisión")
    dDesTipEmi: str = campo("B003", "Descripción del tipo de emisión")
    dCodSeg: str = campo(
        "B004",
        "Código de seguridad",
        min_length=9,
        max_length=9,
        pattern=r"^\d{9}$",
    )
    dInfoEmi: str | None = campo_opcional(
        "B005",
        "Información de interés del emisor respecto al DE",
        max_length=3000,
    )
    dInfoFisc: str | None = campo_opcional(
        "B006",
        "Información de interés del Fisco respecto al DE",
        max_length=3000,
    )

    @classmethod
    def normal(cls, codigo_de_seguridad: str, **extras: str | None) -> Operacion:
        """Arma el grupo para una emisión normal, con su descripción normada.

        Args:
            codigo_de_seguridad: el ``dCodSeg`` de nueve dígitos.
            **extras: ``dInfoEmi`` o ``dInfoFisc``, si corresponden.

        Returns:
            El grupo listo.
        """
        return cls(
            iTipEmi=TipoEmision.NORMAL,
            dDesTipEmi=TipoEmision.NORMAL.descripcion,
            dCodSeg=codigo_de_seguridad,
            **extras,
        )


class Timbrado(GrupoSifen):
    """Grupo C. Datos del timbrado (C001-C099).

    El elemento se llama ``gTimb``.

    .. note::
       El orden de ``dSerieNum`` sale de la tabla del manual, donde figura entre
       ``dNumDoc`` (C007) y ``dFeIniT`` (C008) pese a llevar el identificador
       C010. Es lo que pasa cuando una nota técnica agrega un campo al medio de
       una secuencia ya publicada. Ver ``docs/decisiones/0001-orden-de-los-campos.md``.
    """

    _etiqueta: ClassVar[str] = "gTimb"

    iTiDE: TipoDocumento = campo("C002", "Tipo de documento electrónico")
    dDesTiDE: str = campo("C003", "Descripción del tipo de documento electrónico")
    dNumTim: str = campo(
        "C004",
        "Número del timbrado",
        min_length=8,
        max_length=8,
        pattern=r"^\d{8}$",
    )
    dEst: str = campo(
        "C005", "Establecimiento", min_length=3, max_length=3, pattern=r"^\d{3}$"
    )
    dPunExp: str = campo(
        "C006",
        "Punto de expedición",
        min_length=3,
        max_length=3,
        pattern=r"^\d{3}$",
    )
    dNumDoc: str = campo(
        "C007",
        "Número del documento",
        min_length=7,
        max_length=7,
        pattern=r"^\d{7}$",
    )
    dSerieNum: str | None = campo_opcional(
        "C010",
        "Serie del número de timbrado",
        min_length=2,
        max_length=2,
    )
    dFeIniT: date = campo("C008", "Fecha de inicio de vigencia del timbrado")
    dFeFinT: date | None = campo_opcional(
        "C009", "Fecha de fin de vigencia del timbrado"
    )

    @field_validator("dNumDoc")
    @classmethod
    def _no_puede_ser_cero(cls, valor: str) -> str:
        """El manual exige que la numeración empiece en 1 para un timbrado nuevo."""
        if int(valor) == 0:
            raise ValueError(
                "el número de documento debe empezar en 1 para un timbrado nuevo (C007)"
            )
        return valor


class DocumentoElectronico(GrupoSifen):
    """Grupo A. Campos firmados del Documento Electrónico (A001-A099).

    El elemento se llama ``DE`` y es el que se firma: lleva el CDC en su
    atributo ``Id`` (A002), que es a lo que apunta la ``Reference`` de la firma.
    """

    _etiqueta: ClassVar[str] = "DE"

    dDVId: int = campo("A003", "Dígito verificador del identificador del DE")
    dFecFirma: datetime = campo("A004", "Fecha de la firma")
    dSisFact: int = campo("A005", "Sistema de facturación")
    gOpeDE: Operacion = campo("B001", "Campos inherentes a la operación de DE")
    gTimb: Timbrado = campo("C001", "Datos del timbrado")

    # El Id (A002) no es un elemento hijo sino un atributo del DE, y su valor es
    # el CDC. Lo completa sobre_rde(), que es quien lo conoce.


def sobre_rde(
    documento: DocumentoElectronico,
    cdc: str,
    *,
    espacio: str | None = NS_SIFEN,
) -> etree._Element:
    """Arma el ``rDE``, o sea el grupo AA que envuelve al documento.

    Args:
        documento: el ``DE`` ya poblado.
        cdc: el Código de Control, que va como atributo ``Id`` del ``DE``
            (A002) y al que apunta la firma.
        espacio: espacio de nombres a aplicar. Por omisión, el del SIFEN.

    Returns:
        El elemento ``rDE`` listo para firmar.

    Example:
        >>> raiz = sobre_rde(documento, cdc.valor)  # doctest: +SKIP
        >>> firmar_elemento(raiz, firmante)  # doctest: +SKIP
    """
    etiqueta = f"{{{espacio}}}rDE" if espacio else "rDE"
    # lxml admite None como clave para el espacio por omisión; los stubs no.
    nsmap = {None: espacio} if espacio else None
    raiz = etree.Element(etiqueta, nsmap=nsmap)  # type: ignore[arg-type]

    version = etree.SubElement(raiz, f"{{{espacio}}}dVerFor" if espacio else "dVerFor")
    version.text = str(VERSION_DEL_FORMATO)

    elemento = documento.a_elemento(espacio)
    elemento.set("Id", cdc)
    raiz.append(elemento)

    return raiz
