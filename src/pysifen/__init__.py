"""pysifen — documentos tributarios electrónicos del Paraguay (SIFEN).

Librería para **leer, verificar y armar** documentos tributarios electrónicos
del Sistema Integrado de Facturación Electrónica Nacional de la Dirección
Nacional de Ingresos Tributarios.

La implementación sigue el **Manual Técnico v150** con las **Notas Técnicas 001
a 027** aplicadas de forma acumulativa. Cada módulo indica en su docstring el
apartado del manual que implementa.

Lo que la versión 1 estabiliza
------------------------------

Leer un documento recibido y decir si se puede confiar en él. Para eso **no
hace falta certificado propio ni estar habilitado como facturador**: el
documento trae adentro el certificado de quien lo firmó.

Example:
    >>> from pysifen import verificar_documento
    >>> resultado = verificar_documento(recibido)  # doctest: +SKIP
    >>> resultado.confiable  # doctest: +SKIP
    True

Armar y firmar documentos propios ya funciona y está probado, pero la promesa
de estabilidad de la versión 1 **no lo cubre**: se cierra en la 2, cuando haya
un documento aceptado por el SIFEN. Ver la hoja de ruta.

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
from pysifen.documento import documento_desde_xml
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
from pysifen.lectura import (
    Verificacion,
    leer_documentos,
    verificar_documento,
    verificar_lote,
)
from pysifen.pki.cadena import ListaDeConfianza, lista_de_confianza, validar_cadena
from pysifen.pki.certificado import Certificado
from pysifen.pki.revocacion import (
    EstadoDeRevocacion,
    ResultadoDeRevocacion,
    consultar_revocacion,
)
from pysifen.qr import DatosQr, generar_url_qr
from pysifen.security import (
    Secreto,
    generar_codigo_seguridad,
    validar_codigo_seguridad,
)
from pysifen.validacion import validar_documento, validar_evento

__version__ = "1.0.0"

#: Lo que la versión 1 estabiliza. Un cambio incompatible acá obliga a subir la
#: versión mayor; lo que no esté en esta lista puede cambiar.
__all__ = [
    "Ambiente",
    "Cdc",
    "CdcError",
    "Certificado",
    "ConfiguracionError",
    "DatosQr",
    "EstadoDeRevocacion",
    "FirmaError",
    "ListaDeConfianza",
    "PkiError",
    "ResultadoDeRevocacion",
    "Secreto",
    "SifenError",
    "TipoContribuyente",
    "TipoDocumento",
    "TipoEmision",
    "ValidacionError",
    "Verificacion",
    "__version__",
    "calcular_dv_mod11",
    "consultar_revocacion",
    "documento_desde_xml",
    "dv_ruc",
    "generar_codigo_seguridad",
    "generar_url_qr",
    "leer_documentos",
    "lista_de_confianza",
    "validar_cadena",
    "validar_codigo_seguridad",
    "validar_documento",
    "validar_evento",
    "verificar_documento",
    "verificar_lote",
]
