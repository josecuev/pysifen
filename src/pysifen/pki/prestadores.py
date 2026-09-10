"""Los prestadores cualificados habilitados en el Paraguay.

Datos tomados del registro de la Autoridad Certificadora Raíz del Paraguay,
administrada por el Ministerio de Industria y Comercio, consultado el
**10 de setiembre de 2026**.

Cada prestador es una función de fábrica declarada como *entry point* del grupo
``pysifen.psc``. Para sumar uno nuevo, sea acá o desde un paquete de terceros,
alcanza con escribir una función equivalente y declararla: no hay que tocar
:mod:`pysifen.pki.psc` ni ningún otro módulo del núcleo.

.. note::
   Esta lista refleja quién estaba habilitado al momento de escribirla. Que un
   certificado no coincida con ninguno de estos prestadores **no prueba que sea
   inválido**: puede venir de uno habilitado después.
"""

from __future__ import annotations

from pysifen.pki.psc import DatosPrestador, PrestadorPorEmisor, TipoCertificado

__all__ = [
    "code100",
    "confirma",
    "documenta",
    "identificaciones",
    "itti",
    "sos",
    "todos",
    "vit",
]

_F1_F2_F3 = frozenset({TipoCertificado.F1, TipoCertificado.F2, TipoCertificado.F3})


def vit() -> PrestadorPorEmisor:
    """VIT S.A., habilitado por Resolución 774/2014."""
    return PrestadorPorEmisor(
        datos=DatosPrestador(
            identificador="vit",
            nombre="VIT S.A.",
            resolucion="774/2014",
            tipos=_F1_F2_F3,
            sitio="https://www.vitsa.com.py",
        ),
        patrones=("VIT S.A.", "VIT SA", "VITSA"),
    )


def code100() -> PrestadorPorEmisor:
    """CODE100 S.A., habilitado por Resolución 187/2015."""
    return PrestadorPorEmisor(
        datos=DatosPrestador(
            identificador="code100",
            nombre="CODE100 S.A.",
            resolucion="187/2015",
            tipos=_F1_F2_F3,
            sitio="https://www.code100.com.py",
        ),
        patrones=("CODE100", "CODE 100"),
    )


def documenta() -> PrestadorPorEmisor:
    """DOCUMENTA S.A., habilitado por Resolución 20/2016."""
    return PrestadorPorEmisor(
        datos=DatosPrestador(
            identificador="documenta",
            nombre="DOCUMENTA S.A.",
            resolucion="20/2016",
            tipos=_F1_F2_F3,
            sitio="https://www.digito.com.py",
        ),
        patrones=("DOCUMENTA", "DIGITO"),
    )


def identificaciones() -> PrestadorPorEmisor:
    """Ministerio del Interior, habilitado por Resolución 381/2023.

    Emite únicamente certificados F2, a través del Departamento de
    Identificaciones de la Policía Nacional.
    """
    return PrestadorPorEmisor(
        datos=DatosPrestador(
            identificador="identificaciones",
            nombre="Ministerio del Interior",
            resolucion="381/2023",
            tipos=frozenset({TipoCertificado.F2}),
            sitio="https://www.identificaciones.gov.py",
        ),
        patrones=(
            "Ministerio del Interior",
            "Policia Nacional",
            "Identificaciones",
        ),
    )


def confirma() -> PrestadorPorEmisor:
    """CONFIRMA S.A., habilitado por Resolución 510/2023."""
    return PrestadorPorEmisor(
        datos=DatosPrestador(
            identificador="confirma",
            nombre="CONFIRMA S.A.",
            resolucion="510/2023",
            tipos=_F1_F2_F3,
            sitio="https://www.confirma.com.py",
        ),
        patrones=("CONFIRMA",),
    )


def itti() -> PrestadorPorEmisor:
    """ITTI S.A.E.C.A., habilitado por Resolución 530/2024.

    Emite F1 y F3, no F2.
    """
    return PrestadorPorEmisor(
        datos=DatosPrestador(
            identificador="itti",
            nombre="ITTI S.A.E.C.A.",
            resolucion="530/2024",
            tipos=frozenset({TipoCertificado.F1, TipoCertificado.F3}),
            sitio="https://secure.itti.digital",
        ),
        patrones=("ITTI",),
    )


def sos() -> PrestadorPorEmisor:
    """SOS Tecnología y Gestión de Información Ltda., Resolución 0365/2025."""
    return PrestadorPorEmisor(
        datos=DatosPrestador(
            identificador="sos",
            nombre="SOS Tecnología y Gestión de Información Ltda.",
            resolucion="0365/2025",
            tipos=_F1_F2_F3,
            sitio="https://sosdocs.com.py",
        ),
        patrones=("SOS Tecnologia", "SOSDOCS", "SOS TGI"),
    )


def todos() -> tuple[PrestadorPorEmisor, ...]:
    """Devuelve los siete prestadores habilitados, en orden de habilitación."""
    return (
        vit(),
        code100(),
        documenta(),
        identificaciones(),
        confirma(),
        itti(),
        sos(),
    )
