"""Tablas de códigos del Manual Técnico SIFEN v150.

Cada enumeración lleva el identificador del campo del manual al que corresponde,
para que se pueda auditar contra el documento oficial sin adivinar.

Los valores son los del manual. La propiedad ``descripcion`` devuelve el texto
exacto que el manual exige en el campo descriptivo asociado (por ejemplo
``dDesTiDE`` para ``iTiDE``); esos textos son literales normados y no se
traducen ni se reescriben.
"""

from __future__ import annotations

from enum import IntEnum

__all__ = [
    "Ambiente",
    "TipoContribuyente",
    "TipoDocumento",
    "TipoEmision",
]


class Ambiente(IntEnum):
    """Ambiente de operación. Campo ``iAmbDE`` (grupo A)."""

    TEST = 1
    PRODUCCION = 2

    @property
    def descripcion(self) -> str:
        """Texto normado para el campo ``dDesAmbDE``."""
        return {
            Ambiente.TEST: "Test",
            Ambiente.PRODUCCION: "Producción",
        }[self]


class TipoDocumento(IntEnum):
    """Tipo de documento electrónico. Campo ``iTiDE`` (C002).

    Los valores son los que admite el esquema oficial (``tiTiDE``, patrón
    ``1|[4-7]|9|10``), no los de la tabla del manual. La tabla del manual lista
    además el 2, el 3 y el 8 —factura de exportación, de importación y
    comprobante de retención— pero el esquema los tiene **comentados**: un
    documento con esos códigos no lo acepta el SIFEN, y un CDC que empiece con
    ellos no describe a ningún documento real.

    A la inversa, el 9 y el 10 —las boletas de venta— no figuran en la tabla
    del manual v150 y sí en el esquema. Un lector que se guiara por la tabla
    rechazaría una boleta legítima. Cuando el manual y el esquema no coinciden,
    manda el esquema: ver la decisión 0003.
    """

    FACTURA = 1
    AUTOFACTURA = 4
    NOTA_CREDITO = 5
    NOTA_DEBITO = 6
    NOTA_REMISION = 7
    BOLETA_VENTA = 9
    BOLETA_RESIMPLE = 10

    @property
    def descripcion(self) -> str:
        """Texto normado para el campo ``dDesTiDE`` (C003), tal cual el esquema."""
        return {
            TipoDocumento.FACTURA: "Factura electrónica",
            TipoDocumento.AUTOFACTURA: "Autofactura electrónica",
            TipoDocumento.NOTA_CREDITO: "Nota de crédito electrónica",
            TipoDocumento.NOTA_DEBITO: "Nota de débito electrónica",
            TipoDocumento.NOTA_REMISION: "Nota de remisión electrónica",
            TipoDocumento.BOLETA_VENTA: "Boleta de venta electrónica",
            TipoDocumento.BOLETA_RESIMPLE: "Boleta resimple electrónica",
        }[self]


class TipoEmision(IntEnum):
    """Tipo de emisión. Campo ``iTipEmi`` (B002)."""

    NORMAL = 1
    CONTINGENCIA = 2

    @property
    def descripcion(self) -> str:
        """Texto normado para el campo ``dDesTipEmi`` (B003)."""
        return {
            TipoEmision.NORMAL: "Normal",
            TipoEmision.CONTINGENCIA: "Contingencia",
        }[self]


class TipoContribuyente(IntEnum):
    """Tipo de contribuyente emisor. Campo ``iTipCont`` (D101).

    Es también la posición 25 del CDC.
    """

    PERSONA_FISICA = 1
    PERSONA_JURIDICA = 2

    @property
    def descripcion(self) -> str:
        """Texto habitual para el tipo de contribuyente."""
        return {
            TipoContribuyente.PERSONA_FISICA: "Persona Física",
            TipoContribuyente.PERSONA_JURIDICA: "Persona Jurídica",
        }[self]
