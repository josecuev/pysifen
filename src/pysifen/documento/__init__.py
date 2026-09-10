"""Armado del XML del documento electrónico.

Los modelos de los 49 grupos se generan desde el esquema oficial de la DNIT, así
que su orden, sus longitudes, sus patrones y sus valores enumerados son los del
esquema y no una transcripción. Ver
:mod:`pysifen.documento._generado` y ``scripts/generar_modelos.py``.

Los nombres de las clases derivan del tipo del esquema (``tgCamItem`` →
``CamItem``). Para los grupos de uso más frecuente se exponen además alias con
el nombre de dominio, que se leen mejor en el código de una aplicación:

=================  ==================  =========================
Alias              Clase generada      Elemento XML
=================  ==================  =========================
``Operacion``      ``COpeDE``          ``gOpeDE``
``Timbrado``       ``DTim``            ``gTimb``
``DatosGenerales`` ``DaGOC``          ``gDatGralOpe``
``Emisor``         ``Emis``            ``gEmis``
``Receptor``       ``DatRec``          ``gDatRec``
``Item``           ``CamItem``         ``gCamItem``
``Totales``        ``TotSub``          ``gTotSub``
=================  ==================  =========================
"""

from __future__ import annotations

from pysifen.documento import _generado
from pysifen.documento._generado import (
    RDE,
    CamAE,
    CamCond,
    CamDEAsoc,
    CamFE,
    CamItem,
    CamIVA,
    CamNCDE,
    CamNRE,
    COpeDE,
    DaGOC,
    DatRec,
    DocumentoElectronico,
    DTim,
    Emis,
    PagCred,
    TotSub,
    ValorItem,
)
from pysifen.documento.base import (
    GrupoSifen,
    campo,
    campo_opcional,
    cobertura_de_identificadores,
    formatear,
    identificadores_del_manual,
)
from pysifen.documento.sobre import (
    NS_SIFEN,
    VERSION_DEL_FORMATO,
    agregar_campos_fuera_de_firma,
    sobre_rde,
)

#: Alias con nombre de dominio, para que el código de una aplicación se lea.
Operacion = COpeDE
Timbrado = DTim
DatosGenerales = DaGOC
Emisor = Emis
Receptor = DatRec
Item = CamItem
Totales = TotSub

__all__ = [
    "NS_SIFEN",
    "RDE",
    "VERSION_DEL_FORMATO",
    "COpeDE",
    "CamAE",
    "CamCond",
    "CamDEAsoc",
    "CamFE",
    "CamIVA",
    "CamItem",
    "CamNCDE",
    "CamNRE",
    "DTim",
    "DaGOC",
    "DatRec",
    "DatosGenerales",
    "DocumentoElectronico",
    "Emis",
    "Emisor",
    "GrupoSifen",
    "Item",
    "Operacion",
    "PagCred",
    "Receptor",
    "Timbrado",
    "TotSub",
    "Totales",
    "ValorItem",
    "agregar_campos_fuera_de_firma",
    "campo",
    "campo_opcional",
    "cobertura_de_identificadores",
    "formatear",
    "identificadores_del_manual",
    "sobre_rde",
]


def grupos_disponibles() -> dict[str, type[GrupoSifen]]:
    """Devuelve todos los grupos generados, por nombre de clase.

    Útil para inspeccionar la estructura completa del documento sin tener que
    importar cada clase por separado.

    Returns:
        Un diccionario del nombre de la clase al modelo.

    Example:
        >>> grupos = grupos_disponibles()
        >>> len(grupos)
        49
        >>> "CamNRE" in grupos
        True
    """
    return {nombre: getattr(_generado, nombre) for nombre in _generado.__all__}
