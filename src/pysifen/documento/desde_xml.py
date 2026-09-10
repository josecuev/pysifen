"""Lectura de un documento electrónico a los modelos.

El camino de vuelta de :meth:`GrupoSifen.a_elemento`. Toma el XML de un
documento recibido y devuelve los modelos poblados, con los tipos de Python que
corresponden: ``Decimal`` para los importes, ``date`` y ``datetime`` para las
fechas, los enteros de las enumeraciones como enteros.

Por qué genérico y no 49 funciones
----------------------------------

Los modelos ya saben todo lo que hace falta: su etiqueta XML, sus campos, el
tipo de cada uno y si se repite. El generador garantiza además que **el nombre
del campo es la etiqueta del elemento**, sin una sola excepción en los 49
grupos, así que la correspondencia no necesita una tabla.

Con eso, leer es recorrer el árbol armando un diccionario anidado y dejar que
pydantic haga la conversión y la validación. Un grupo nuevo en el esquema
aparece solo al regenerar los modelos: acá no hay nada que tocar.

Qué se rechaza
--------------

Un elemento que el modelo no declara. Los modelos son ``extra="forbid"`` a
propósito: un documento con un elemento desconocido no es un documento del
SIFEN, y aceptarlo en silencio sería perder justamente lo que se vino a
comprobar.
"""

from __future__ import annotations

import types
import typing
from typing import Any

from lxml import etree

from pysifen.documento._generado import DocumentoElectronico
from pysifen.documento.base import GrupoSifen
from pysifen.documento.sobre import NS_SIFEN
from pysifen.exceptions import SifenError

__all__ = [
    "NS_SIFEN",
    "documento_desde_xml",
    "grupo_desde_elemento",
]


def documento_desde_xml(xml: bytes | str | etree._Element) -> DocumentoElectronico:
    """Lee un documento recibido y devuelve el ``DE`` como modelo.

    Acepta el ``rDE`` completo, el ``DE`` suelto o un ``rLoteDE`` con un
    documento adentro.

    Args:
        xml: el documento, en bytes, texto o ya interpretado.

    Returns:
        El documento electrónico con todos sus grupos poblados.

    Raises:
        SifenError: si el XML no se puede interpretar, si no se encuentra el
            ``DE``, o si el documento no corresponde al esquema.

    Example:
        >>> de = documento_desde_xml(recibido)  # doctest: +SKIP
        >>> de.gDatGralOpe.gEmis.dNomEmi  # doctest: +SKIP
        'SERVICIOS RAPIDOS DEL PARAGUAY S.A.'
    """
    raiz = _interpretar(xml)
    de = _encontrar_de(raiz)
    if de is None:
        raise SifenError("no encontré el elemento DE en el documento")
    return grupo_desde_elemento(de, DocumentoElectronico)


def grupo_desde_elemento[G: GrupoSifen](elemento: etree._Element, modelo: type[G]) -> G:
    """Lee un elemento XML al modelo del grupo que le corresponde.

    Args:
        elemento: el elemento a leer.
        modelo: la clase del grupo, por ejemplo ``Emis`` o ``CamItem``.

    Returns:
        El grupo poblado.

    Raises:
        SifenError: si el elemento trae hijos que el grupo no declara, o si
            algún valor no pasa la validación del modelo.
    """
    datos = _a_diccionario(elemento, modelo)
    try:
        return modelo.model_validate(datos)
    except Exception as exc:
        raise SifenError(
            f"el elemento {etree.QName(elemento).localname!r} no corresponde al "
            f"grupo {modelo.__name__}: {exc}"
        ) from exc


def _interpretar(xml: bytes | str | etree._Element) -> etree._Element:
    """Normaliza la entrada a un elemento."""
    if isinstance(xml, etree._Element):
        return xml
    crudo = xml.encode() if isinstance(xml, str) else xml
    analizador = etree.XMLParser(resolve_entities=False, no_network=True)
    try:
        return etree.fromstring(crudo, parser=analizador)
    except etree.XMLSyntaxError as exc:
        raise SifenError(f"el documento no es XML válido: {exc}") from exc


def _encontrar_de(raiz: etree._Element) -> etree._Element | None:
    """Ubica el ``DE``, venga suelto, dentro de un ``rDE`` o de un lote."""
    if etree.QName(raiz).localname == "DE":
        return raiz
    for elemento in raiz.iter():
        if etree.QName(elemento).localname == "DE":
            return elemento
    return None


def _a_diccionario(
    elemento: etree._Element, modelo: type[GrupoSifen]
) -> dict[str, Any]:
    """Arma el diccionario anidado que pydantic va a validar."""
    datos: dict[str, Any] = {}
    declarados = set(modelo.model_fields)

    for nombre, info in modelo.model_fields.items():
        tipo, repetido = _tipo_del_campo(info.annotation)
        hijos = _hijos(elemento, nombre)
        if not hijos:
            continue

        if repetido:
            datos[nombre] = [_valor(h, tipo) for h in hijos]
        else:
            datos[nombre] = _valor(hijos[0], tipo)

    desconocidos = sorted(
        {etree.QName(h).localname for h in elemento} - declarados - {"Signature"}
    )
    if desconocidos:
        raise SifenError(
            f"el grupo {modelo.__name__} no declara estos elementos, que el "
            f"documento trae: {', '.join(desconocidos)}"
        )
    return datos


def _valor(hijo: etree._Element, tipo: Any) -> Any:
    """Devuelve el valor de un hijo: otro grupo, o el texto tal cual."""
    if isinstance(tipo, type) and issubclass(tipo, GrupoSifen):
        return _a_diccionario(hijo, tipo)
    return hijo.text or ""


def _hijos(elemento: etree._Element, nombre: str) -> list[etree._Element]:
    """Devuelve los hijos directos con ese nombre, con espacio o sin él."""
    return [h for h in elemento if etree.QName(h).localname == nombre]


def _tipo_del_campo(anotacion: Any) -> tuple[Any, bool]:
    """Devuelve el tipo útil de un campo y si admite repetición.

    Desenvuelve ``X | None``, ``Optional[X]``, ``Annotated[X, ...]`` y
    ``tuple[X, ...]``, que es como el generador expresa los grupos que el
    esquema declara con ocurrencia múltiple.
    """
    anotacion = _sin_opcional(_sin_anotado(anotacion))
    if typing.get_origin(anotacion) is tuple:
        argumentos = typing.get_args(anotacion)
        interno = _sin_opcional(_sin_anotado(argumentos[0])) if argumentos else Any
        return interno, True
    return anotacion, False


def _sin_anotado(anotacion: Any) -> Any:
    """Quita el envoltorio ``Annotated`` si lo hay."""
    while typing.get_origin(anotacion) is typing.Annotated:
        anotacion = typing.get_args(anotacion)[0]
    return anotacion


def _sin_opcional(anotacion: Any) -> Any:
    """Quita el ``None`` de una unión de dos, que es como se declara opcional."""
    origen = typing.get_origin(anotacion)
    if origen is not typing.Union and not isinstance(anotacion, types.UnionType):
        return anotacion
    reales = [a for a in typing.get_args(anotacion) if a is not type(None)]
    return _sin_anotado(reales[0]) if len(reales) == 1 else anotacion
