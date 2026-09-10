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

    El código ``8`` (Comprobante de retención electrónico) figura en el manual
    marcado como *futuro* y todavía no está operativo en SIFEN.
    """

    FACTURA = 1
    FACTURA_EXPORTACION = 2
    FACTURA_IMPORTACION = 3
    AUTOFACTURA = 4
    NOTA_CREDITO = 5
    NOTA_DEBITO = 6
    NOTA_REMISION = 7
    COMPROBANTE_RETENCION = 8

    @property
    def descripcion(self) -> str:
        """Texto normado para el campo ``dDesTiDE`` (C003)."""
        return {
            TipoDocumento.FACTURA: "Factura electrónica",
            TipoDocumento.FACTURA_EXPORTACION: "Factura electrónica de exportación",
            TipoDocumento.FACTURA_IMPORTACION: "Factura electrónica de importación",
            TipoDocumento.AUTOFACTURA: "Autofactura electrónica",
            TipoDocumento.NOTA_CREDITO: "Nota de crédito electrónica",
            TipoDocumento.NOTA_DEBITO: "Nota de débito electrónica",
            TipoDocumento.NOTA_REMISION: "Nota de remisión electrónica",
            TipoDocumento.COMPROBANTE_RETENCION: "Comprobante de retención electrónico",
        }[self]

    @property
    def operativo(self) -> bool:
        """``False`` para los tipos que el manual marca como futuros."""
        return self is not TipoDocumento.COMPROBANTE_RETENCION


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
