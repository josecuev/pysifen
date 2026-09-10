"""Servidor MCP de pysifen.

Requiere el extra ``mcp``::

    pip install "pysifen[mcp]"
"""

from __future__ import annotations

from pysifen.mcp.servidor import construir_servidor, main

__all__ = ["construir_servidor", "main"]
