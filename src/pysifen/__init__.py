"""pysifen — facturación electrónica del Paraguay (SIFEN).

Librería para emitir documentos tributarios electrónicos contra el Sistema
Integrado de Facturación Electrónica Nacional de la Dirección Nacional de
Ingresos Tributarios.

La implementación sigue el **Manual Técnico v150** con las **Notas Técnicas 001
a 027** aplicadas de forma acumulativa. Cada módulo indica en su docstring el
apartado del manual que implementa.

Example:
    >>> from datetime import date
    >>> from pysifen import Cdc, TipoContribuyente, TipoDocumento
    >>> cdc = Cdc.crear(
    ...     tipo_documento=TipoDocumento.FACTURA,
    ...     ruc_emisor="44444401-7",
    ...     establecimiento="001",
    ...     punto_expedicion="001",
    ...     numero="0014528",
    ...     tipo_contribuyente=TipoContribuyente.PERSONA_JURIDICA,
    ...     fecha_emision=date(2017, 1, 25),
    ...     codigo_seguridad="587326098",
    ... )
    >>> cdc.valor
    '01444444017001001001452822017012515873260988'
"""

from __future__ import annotations

from pysifen.cdc import Cdc, calcular_dv_mod11, dv_ruc
from pysifen.enums import (
    Ambiente,
    TipoContribuyente,
    TipoDocumento,
    TipoEmision,
)
from pysifen.exceptions import (
    CdcError,
    ConfiguracionError,
    FirmaError,
    PkiError,
    SifenError,
    ValidacionError,
)
from pysifen.qr import DatosQr, generar_url_qr
from pysifen.security import (
    Secreto,
    generar_codigo_seguridad,
    validar_codigo_seguridad,
)
from pysifen.validacion import validar_documento, validar_evento

__version__ = "0.6.0"

__all__ = [
    "Ambiente",
    "Cdc",
    "CdcError",
    "ConfiguracionError",
    "DatosQr",
    "FirmaError",
    "PkiError",
    "Secreto",
    "SifenError",
    "TipoContribuyente",
    "TipoDocumento",
    "TipoEmision",
    "ValidacionError",
    "__version__",
    "calcular_dv_mod11",
    "dv_ruc",
    "generar_codigo_seguridad",
    "generar_url_qr",
    "validar_codigo_seguridad",
    "validar_documento",
    "validar_evento",
]
