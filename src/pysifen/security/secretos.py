"""Envoltorio para valores secretos.

El Código de Seguridad del Contribuyente (CSC) y las contraseñas de keystore son
secretos compartidos que no deben aparecer nunca en un log, en un ``repr`` de
depuración ni en una traza de excepción.

:class:`Secreto` guarda el valor pero no lo muestra: hay que pedirlo de forma
explícita con :meth:`Secreto.revelar`. La explicitud es el punto — un secreto
que se filtra a un log lo hace casi siempre por un ``print`` o un ``f-string``
que nadie escribió a propósito.
"""

from __future__ import annotations

import hmac
from typing import Any

__all__ = ["Secreto"]

_OCULTO = "***"


class Secreto:
    """Contiene un valor sensible y evita que se muestre por accidente.

    Args:
        valor: el texto secreto.
        nombre: etiqueta para los mensajes, por ejemplo ``"CSC"``. Nunca
            contiene el valor.

    Raises:
        ValueError: si el valor está vacío.

    Example:
        >>> csc = Secreto("ABCD0000000000000000000000000000", nombre="CSC")
        >>> print(csc)
        Secreto(CSC=***)
        >>> csc.revelar()[:4]
        'ABCD'
    """

    __slots__ = ("_nombre", "_valor")

    def __init__(self, valor: str, *, nombre: str = "secreto") -> None:
        if not valor:
            raise ValueError(f"{nombre} no puede estar vacío")
        self._valor = valor
        self._nombre = nombre

    @property
    def nombre(self) -> str:
        """Etiqueta del secreto. No revela el valor."""
        return self._nombre

    def revelar(self) -> str:
        """Devuelve el valor en claro.

        Llamar a esto es la única forma de obtener el secreto. Usarlo lo más
        tarde posible y no guardar el resultado en una variable de larga vida.
        """
        return self._valor

    def __repr__(self) -> str:
        """Representación sin el valor."""
        return f"Secreto({self._nombre}={_OCULTO})"

    __str__ = __repr__

    def __eq__(self, otro: object) -> bool:
        """Compara en tiempo constante contra otro :class:`Secreto`."""
        if not isinstance(otro, Secreto):
            return NotImplemented
        return hmac.compare_digest(self._valor, otro._valor)

    def __hash__(self) -> int:
        """Hashea la identidad, no el valor, para no filtrarlo por el hash."""
        return hash(id(self))

    def __len__(self) -> int:
        """Largo del secreto. No revela su contenido."""
        return len(self._valor)

    def __bool__(self) -> bool:
        """Un :class:`Secreto` siempre es verdadero: no puede estar vacío."""
        return True

    def __getstate__(self) -> Any:
        """Impide serializar el secreto con ``pickle``.

        Raises:
            TypeError: siempre.
        """
        raise TypeError(f"{self._nombre} no se puede serializar")

    def __copy__(self) -> Secreto:
        """Devuelve el mismo objeto: no se duplica material sensible."""
        return self

    def __deepcopy__(self, memo: dict[int, Any]) -> Secreto:
        """Devuelve el mismo objeto: no se duplica material sensible."""
        return self
