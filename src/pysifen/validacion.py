"""Validación de documentos y eventos contra el esquema oficial.

El SIFEN valida cada documento que recibe contra un XSD. Validar antes de
transmitir convierte un rechazo remoto —con un mensaje escueto y un viaje de ida
y vuelta— en un error local con la línea exacta.

De dónde salen los esquemas
---------------------------

De ``https://ekuatia.set.gov.py/sifen/xsd/``, que es donde la DNIT los publica y
donde el propio ``schemaLocation`` de los documentos apunta. Las copias que
vienen con la librería son **byte a byte idénticas** a las de ese servidor; ver
``esquemas/FUENTE.md`` para las fechas y los checksums.

.. warning::
   No confundir con otras dos copias que circulan y **no** sirven:

   - El ``Estructura_DE xsd.rar`` del portal de documentación técnica, que es de
     2018 y describe nodos que ya no existen.
   - El paquete ``20190910_XSD_v150`` que aparece en repositorios públicos, que
     es la publicación original del v150 y **no** trae las enmiendas de las
     notas técnicas. Documentos reales de producción no validan contra él:
     rechaza ``dBasExe`` (agregado por la NT-013), el grupo ``gOblAfe`` y el
     valor ``IVA - Renta`` de ``dDesTImp``.

   Los esquemas incluidos acá sí validan documentos reales emitidos en 2026.

Los esquemas declaran sus dependencias con URL absolutas. Se resuelven contra
las copias locales, de modo que validar no necesita red y las copias quedan
comparables con el original para detectar cambios.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Final

from lxml import etree

__all__ = [
    "DIRECTORIO_DE_ESQUEMAS",
    "URL_OFICIAL",
    "esquema_de_documento",
    "esquema_de_evento",
    "validar_documento",
    "validar_evento",
]

#: Dónde viven las copias de los esquemas dentro del paquete.
DIRECTORIO_DE_ESQUEMAS: Final = Path(__file__).parent / "esquemas"

#: Dónde los publica la DNIT.
URL_OFICIAL: Final = "https://ekuatia.set.gov.py/sifen/xsd/"

_NS_SIFEN: Final = "http://ekuatia.set.gov.py/sifen/xsd"


class _ResolverLocal(etree.Resolver):
    """Redirige los ``include`` absolutos a las copias locales.

    Los esquemas oficiales se referencian entre sí por URL absoluta. Sin esto,
    compilarlos saldría a internet en cada arranque, y fallaría sin conexión.
    """

    # lxml-stubs declara resolve() sin el parámetro `context`, pero lxml lo
    # pasa siempre y resolve_filename() lo exige. Los stubs están
    # incompletos acá; la firma de abajo es la real.
    def resolve(  # type: ignore[override]
        self, system_url: str, public_id: str, context: object
    ) -> object:
        """Devuelve la copia local si el nombre del archivo coincide."""
        nombre = system_url.rsplit("/", 1)[-1]
        candidato = DIRECTORIO_DE_ESQUEMAS / nombre
        if candidato.is_file():
            return self.resolve_filename(  # type: ignore[attr-defined]
                str(candidato), context
            )
        return None


def _compilar(nombre: str) -> etree.XMLSchema:
    """Compila un esquema del paquete, resolviendo sus dependencias local."""
    analizador = etree.XMLParser(no_network=True)
    analizador.resolvers.add(_ResolverLocal())
    arbol = etree.parse(str(DIRECTORIO_DE_ESQUEMAS / nombre), parser=analizador)
    return etree.XMLSchema(arbol)


@lru_cache(maxsize=1)
def esquema_de_documento() -> etree.XMLSchema:
    """Devuelve el esquema de los documentos electrónicos (``rDE``).

    Se compila una sola vez y se reutiliza: armar el esquema completo lleva del
    orden de un segundo.
    """
    return _compilar("siRecepDE_v150.xsd")


@lru_cache(maxsize=1)
def esquema_de_evento() -> etree.XMLSchema:
    """Devuelve el esquema de los eventos (``gGroupGesEve``)."""
    return _compilar("siRecepEvento_v150.xsd")


def _a_elemento(xml: bytes | str | etree._Element) -> etree._Element:
    """Normaliza la entrada a un elemento, sin resolver entidades externas."""
    if isinstance(xml, etree._Element):
        return xml
    crudo = xml.encode() if isinstance(xml, str) else xml
    analizador = etree.XMLParser(resolve_entities=False, no_network=True)
    return etree.fromstring(crudo, parser=analizador)


def validar_documento(xml: bytes | str | etree._Element) -> list[str]:
    """Valida un documento electrónico contra el esquema oficial.

    Acepta un ``rDE`` suelto o un ``rLoteDE`` con varios adentro, que es como
    viajan al servicio de recepción por lote.

    Args:
        xml: el documento, en bytes, texto o ya interpretado.

    Returns:
        La lista de problemas encontrados, en castellano tal como los reporta el
        validador. Vacía si el documento es válido.

    Example:
        >>> problemas = validar_documento(firmado)  # doctest: +SKIP
        >>> if problemas:  # doctest: +SKIP
        ...     for p in problemas:
        ...         print(p)
    """
    raiz = _a_elemento(xml)
    esquema = esquema_de_documento()

    if etree.QName(raiz).localname == "rLoteDE":
        problemas: list[str] = []
        for indice, hijo in enumerate(raiz, start=1):
            for detalle in _validar_uno(esquema, hijo):
                problemas.append(f"documento {indice}: {detalle}")
        return problemas

    return _validar_uno(esquema, raiz)


def validar_evento(xml: bytes | str | etree._Element) -> list[str]:
    """Valida un evento contra el esquema oficial.

    Args:
        xml: el evento, en bytes, texto o ya interpretado.

    Returns:
        La lista de problemas. Vacía si el evento es válido.
    """
    return _validar_uno(esquema_de_evento(), _a_elemento(xml))


def _validar_uno(esquema: etree.XMLSchema, elemento: etree._Element) -> list[str]:
    """Valida un elemento aislado de su árbol original.

    Se lo reserializa para desprenderlo de cualquier contenedor, porque el
    validador exige que la raíz sea el elemento global declarado.
    """
    suelto = etree.fromstring(etree.tostring(elemento))
    if esquema.validate(suelto):
        return []
    # error_log es iterable en tiempo de ejecución; los stubs no lo declaran.
    errores = list(esquema.error_log)  # type: ignore[call-overload]
    return [f"línea {error.line}: {error.message}" for error in errores]
