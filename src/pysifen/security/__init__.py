"""Primitivas de seguridad: secretos y código de seguridad del documento."""

from __future__ import annotations

from pysifen.security.codigo_seguridad import (
    LARGO_CODIGO_SEGURIDAD,
    MAXIMO_CODIGO_SEGURIDAD,
    MINIMO_CODIGO_SEGURIDAD,
    generar_codigo_seguridad,
    validar_codigo_seguridad,
)
from pysifen.security.secretos import Secreto

__all__ = [
    "LARGO_CODIGO_SEGURIDAD",
    "MAXIMO_CODIGO_SEGURIDAD",
    "MINIMO_CODIGO_SEGURIDAD",
    "Secreto",
    "generar_codigo_seguridad",
    "validar_codigo_seguridad",
]
