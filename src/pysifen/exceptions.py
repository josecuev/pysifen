"""Excepciones de la librería.

Todas heredan de :class:`SifenError`, de modo que un consumidor pueda capturar
la familia entera con un solo ``except``.

Ninguna excepción de este módulo incluye material sensible en su mensaje: ni
clave privada, ni contraseña de keystore, ni el Código de Seguridad del
Contribuyente (CSC). Ver ``docs/seguridad/custodia.md``.
"""

from __future__ import annotations

__all__ = [
    "CdcError",
    "ConfiguracionError",
    "FirmaError",
    "PkiError",
    "SifenError",
    "ValidacionError",
]


class SifenError(Exception):
    """Error base de pysifen."""


class ConfiguracionError(SifenError):
    """La configuración provista es inválida o está incompleta."""


class ValidacionError(SifenError):
    """Un dato no cumple una regla del Manual Técnico.

    Args:
        mensaje: descripción del problema en castellano.
        campo: identificador del campo del Manual Técnico, por ejemplo
            ``"C002"`` o ``"dCodSeg"``, cuando se lo puede señalar.
        regla: identificador de la regla de validación del manual, por ejemplo
            ``"D208c"``, cuando corresponde.
    """

    def __init__(
        self,
        mensaje: str,
        *,
        campo: str | None = None,
        regla: str | None = None,
    ) -> None:
        self.campo = campo
        self.regla = regla
        partes = [mensaje]
        if campo:
            partes.append(f"(campo {campo})")
        if regla:
            partes.append(f"[regla {regla}]")
        super().__init__(" ".join(partes))


class CdcError(ValidacionError):
    """El Código de Control es inválido o no se puede construir."""


class FirmaError(SifenError):
    """Falló la firma digital del documento."""


class PkiError(SifenError):
    """Problema con el certificado, su cadena de confianza o su prestador."""
