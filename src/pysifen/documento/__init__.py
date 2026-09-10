"""Armado del XML del documento electrónico.

Cada grupo de campos del Manual Técnico v150 se modela como una clase cuyos
atributos llevan el nombre exacto del campo y su identificador del manual.
"""

from __future__ import annotations

from pysifen.documento.base import (
    GrupoSifen,
    campo,
    campo_opcional,
    identificadores_del_manual,
)
from pysifen.documento.sobre import (
    NS_SIFEN,
    VERSION_DEL_FORMATO,
    DocumentoElectronico,
    Operacion,
    Timbrado,
    sobre_rde,
)

__all__ = [
    "NS_SIFEN",
    "VERSION_DEL_FORMATO",
    "DocumentoElectronico",
    "GrupoSifen",
    "Operacion",
    "Timbrado",
    "campo",
    "campo_opcional",
    "identificadores_del_manual",
    "sobre_rde",
]
