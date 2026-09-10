"""Firma digital de los documentos electrónicos."""

from __future__ import annotations

from pysifen.signing.auditoria import (
    EventoDeFirma,
    FirmanteAuditado,
    registrar_en_log,
)
from pysifen.signing.ports import Firmante, NivelDeCustodia, exigir_nivel
from pysifen.signing.xmldsig import firmar_documento, firmar_elemento

__all__ = [
    "EventoDeFirma",
    "Firmante",
    "FirmanteAuditado",
    "NivelDeCustodia",
    "exigir_nivel",
    "firmar_documento",
    "firmar_elemento",
    "registrar_en_log",
]
