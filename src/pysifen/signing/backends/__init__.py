"""Implementaciones concretas del puerto de firma.

Cada backend representa un nivel de custodia distinto de la clave privada:

===================  ===============================  ==========================
Backend              Certificado                      Nivel
===================  ===============================  ==========================
:class:`FirmanteRemoto`     F3, firma remota          Clave fuera del alcance
:class:`FirmantePkcs11`     F2, token o HSM           Clave en dispositivo
:class:`FirmantePkcs12`     F1, archivo por software  Clave en memoria
===================  ===============================  ==========================

Ver ``docs/seguridad/custodia.md`` para la comparación completa.

``FirmantePkcs11`` se importa por separado desde
:mod:`pysifen.signing.backends.pkcs11` porque necesita el extra ``pkcs11``.
"""

from __future__ import annotations

from pysifen.signing.backends.pkcs12 import AvisoDeCustodia, FirmantePkcs12
from pysifen.signing.backends.remoto import FirmanteRemoto, ServicioDeFirmaRemota

__all__ = [
    "AvisoDeCustodia",
    "FirmantePkcs12",
    "FirmanteRemoto",
    "ServicioDeFirmaRemota",
]
