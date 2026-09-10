"""Generación del código de seguridad ``dCodSeg``.

Implementa el apartado 10.3 del Manual Técnico SIFEN v150.

El manual exige, textualmente, que el código de seguridad sea un número positivo
de nueve dígitos, aleatorio, distinto para cada documento electrónico, generado
por *un algoritmo de complejidad suficiente para evitar la reproducción del
valor*, en un rango **no secuencial** entre ``000000001`` y ``999999999``, sin
relación con ningún dato del documento ni del emisor, y distinto del número de
documento ``dNumDoc``.

Ese requisito es criptográfico, no estadístico: si el código se pudiera predecir,
se podría anticipar el CDC de un documento ajeno. Por eso acá se usa
:mod:`secrets` y no :mod:`random`, cuyo generador es reproducible a partir de su
estado.
"""

from __future__ import annotations

import secrets
from typing import Final

from pysifen.exceptions import ValidacionError

__all__ = [
    "LARGO_CODIGO_SEGURIDAD",
    "MAXIMO_CODIGO_SEGURIDAD",
    "MINIMO_CODIGO_SEGURIDAD",
    "generar_codigo_seguridad",
    "validar_codigo_seguridad",
]

#: Cantidad de dígitos del campo ``dCodSeg``.
LARGO_CODIGO_SEGURIDAD: Final = 9

#: Menor valor admitido por el manual.
MINIMO_CODIGO_SEGURIDAD: Final = 1

#: Mayor valor admitido por el manual.
MAXIMO_CODIGO_SEGURIDAD: Final = 999_999_999


def generar_codigo_seguridad(*, distinto_de: str | int | None = None) -> str:
    """Genera un código de seguridad ``dCodSeg``.

    Usa el generador de números aleatorios criptográfico del sistema operativo.

    Args:
        distinto_de: normalmente el número de documento ``dNumDoc``. El manual
            prohíbe que el código coincida con él, así que si sale igual se
            vuelve a sortear.

    Returns:
        Nueve dígitos, con ceros a la izquierda si hacen falta.

    Example:
        >>> codigo = generar_codigo_seguridad()
        >>> len(codigo)
        9
        >>> codigo.isdigit()
        True
    """
    prohibido = _normalizar(distinto_de) if distinto_de is not None else None

    while True:
        valor = secrets.randbelow(MAXIMO_CODIGO_SEGURIDAD) + MINIMO_CODIGO_SEGURIDAD
        codigo = f"{valor:0{LARGO_CODIGO_SEGURIDAD}d}"
        if codigo != prohibido:
            return codigo


def validar_codigo_seguridad(
    codigo: str,
    *,
    distinto_de: str | int | None = None,
) -> str:
    """Valida un código de seguridad contra las reglas del apartado 10.3.

    Args:
        codigo: el valor a validar.
        distinto_de: número de documento con el que no puede coincidir.

    Returns:
        El código normalizado a nueve dígitos.

    Raises:
        ValidacionError: si no son nueve dígitos, si vale cero, o si coincide
            con ``distinto_de``.
    """
    texto = str(codigo).strip()

    if not texto.isdigit():
        raise ValidacionError(
            "el código de seguridad debe tener sólo dígitos",
            campo="dCodSeg",
        )
    if len(texto) > LARGO_CODIGO_SEGURIDAD:
        raise ValidacionError(
            f"el código de seguridad no puede exceder {LARGO_CODIGO_SEGURIDAD} "
            f"dígitos, tiene {len(texto)}",
            campo="dCodSeg",
        )

    texto = texto.rjust(LARGO_CODIGO_SEGURIDAD, "0")

    if int(texto) < MINIMO_CODIGO_SEGURIDAD:
        raise ValidacionError(
            "el código de seguridad debe ser un número positivo",
            campo="dCodSeg",
        )

    if distinto_de is not None and texto == _normalizar(distinto_de):
        raise ValidacionError(
            "el código de seguridad no puede ser igual al número de documento",
            campo="dCodSeg",
        )

    return texto


def _normalizar(valor: str | int) -> str:
    """Lleva un valor a nueve dígitos con ceros a la izquierda."""
    return str(valor).strip().rjust(LARGO_CODIGO_SEGURIDAD, "0")
