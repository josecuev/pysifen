"""Cimientos del armado del XML del documento electrónico.

Cada grupo de campos del Manual Técnico se modela como una subclase de
:class:`GrupoSifen`. El modelo **es** la especificación:

- El nombre del atributo es el nombre del campo tal como lo escribe el manual
  (``dNumTim``, ``iTipEmi``), sin traducir ni normalizar.
- El orden de declaración es el orden en que los elementos salen en el XML.
- Cada campo lleva su identificador del manual (``C004``, ``B002``) en la
  metadata, de modo que se pueda auditar contra el documento oficial y armar la
  matriz de trazabilidad sin reconstruirla a mano.

Esa correspondencia uno a uno es deliberada: buscar un campo en el manual y
buscarlo en el código tiene que dar lo mismo.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, ClassVar

from lxml import etree
from pydantic import BaseModel, ConfigDict, Field

__all__ = ["GrupoSifen", "campo", "identificadores_del_manual"]


def campo(
    identificador: str,
    descripcion: str,
    **extra: Any,
) -> Any:
    """Declara un campo con su identificador del Manual Técnico.

    Args:
        identificador: el identificador del manual, por ejemplo ``"C004"``.
        descripcion: la descripción del campo, en las palabras del manual.
        **extra: cualquier restricción adicional de pydantic, como
            ``min_length`` o ``max_length``.

    Returns:
        El descriptor de campo para pydantic.

    Example:
        >>> class Ejemplo(GrupoSifen):
        ...     _etiqueta = "gEjemplo"
        ...     dNumTim: str = campo("C004", "Número del timbrado")
    """
    return Field(
        ...,
        description=f"{identificador} · {descripcion}",
        json_schema_extra={"sifen": identificador},
        **extra,
    )


def campo_opcional(
    identificador: str,
    descripcion: str,
    **extra: Any,
) -> Any:
    """Igual que :func:`campo`, pero el campo admite ``None``.

    Un campo en ``None`` no se emite en el XML.

    Args:
        identificador: el identificador del manual.
        descripcion: la descripción del campo.
        **extra: restricciones adicionales de pydantic.

    Returns:
        El descriptor de campo para pydantic.
    """
    return Field(
        default=None,
        description=f"{identificador} · {descripcion}",
        json_schema_extra={"sifen": identificador},
        **extra,
    )


class GrupoSifen(BaseModel):
    """Un grupo de campos del Manual Técnico.

    Las subclases declaran ``_etiqueta`` con el nombre del elemento XML del
    grupo, y sus campos en el orden en que el manual los dispone.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    #: Nombre del elemento XML que representa a este grupo.
    _etiqueta: ClassVar[str] = ""

    def a_elemento(self, espacio: str | None = None) -> etree._Element:
        """Convierte el grupo en un elemento XML.

        Recorre los campos en orden de declaración. Los que valen ``None`` no se
        emiten: el manual los marca con ocurrencia ``0-1`` y un elemento vacío
        no es lo mismo que un elemento ausente.

        Args:
            espacio: espacio de nombres a aplicar, o ``None`` para ninguno.

        Returns:
            El elemento con sus hijos ya poblados.
        """
        elemento = etree.Element(_calificar(type(self)._etiqueta, espacio))
        for nombre, valor in self._campos_en_orden():
            _agregar(elemento, nombre, valor, espacio)
        return elemento

    def _campos_en_orden(self) -> list[tuple[str, Any]]:
        """Devuelve los pares nombre-valor en orden de declaración."""
        return [(nombre, getattr(self, nombre)) for nombre in type(self).model_fields]


def _calificar(etiqueta: str, espacio: str | None) -> str:
    """Antepone el espacio de nombres a una etiqueta, si lo hay."""
    return f"{{{espacio}}}{etiqueta}" if espacio else etiqueta


def _agregar(
    padre: etree._Element,
    nombre: str,
    valor: Any,
    espacio: str | None,
) -> None:
    """Agrega un campo al elemento padre, si tiene valor."""
    if valor is None:
        return

    if isinstance(valor, GrupoSifen):
        padre.append(valor.a_elemento(espacio))
        return

    if isinstance(valor, list | tuple):
        for uno in valor:
            _agregar(padre, nombre, uno, espacio)
        return

    hijo = etree.SubElement(padre, _calificar(nombre, espacio))
    hijo.text = formatear(valor)


def formatear(valor: Any) -> str:
    """Lleva un valor de Python al texto que espera el XML del SIFEN.

    Las fechas y horas van en ``AAAA-MM-DDThh:mm:ss`` y las fechas sueltas en
    ``AAAA-MM-DD``, como fija el manual. Los enteros de las enumeraciones salen
    por su valor numérico, no por su nombre.

    Args:
        valor: el valor a formatear.

    Returns:
        El texto a poner en el elemento.
    """
    if isinstance(valor, bool):  # antes que int: bool es subclase de int
        return "1" if valor else "0"
    if isinstance(valor, datetime):
        return valor.isoformat(timespec="seconds")
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        # Sin normalize: el SIFEN escribe los importes con sus decimales
        # explícitos (36500.00000000) y el hash del QR se calcula sobre
        # esa cadena exacta.
        return format(valor, "f")
    if isinstance(valor, int):
        return str(int(valor))
    return str(valor)


def identificadores_del_manual(grupo: type[GrupoSifen]) -> dict[str, str]:
    """Devuelve el mapa ``campo -> identificador del manual`` de un grupo.

    Es lo que permite armar la matriz de trazabilidad desde el propio código, en
    vez de mantenerla a mano en un documento que se desactualiza.

    Args:
        grupo: la clase del grupo.

    Returns:
        Un diccionario del nombre del campo a su identificador, por ejemplo
        ``{"dNumTim": "C004"}``.

    Example:
        >>> from pysifen.documento.timbrado import Timbrado
        >>> identificadores_del_manual(Timbrado)["dNumTim"]
        'C004'
    """
    mapa: dict[str, str] = {}
    for nombre, info in grupo.model_fields.items():
        extra = info.json_schema_extra
        if isinstance(extra, dict) and "sifen" in extra:
            mapa[nombre] = str(extra["sifen"])
    return mapa


#: Tipo de los importes del SIFEN: hasta 15 enteros y 8 decimales.
Importe = Annotated[Decimal, Field(max_digits=23, decimal_places=8)]
