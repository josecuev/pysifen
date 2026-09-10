"""El puerto de firma y los niveles de custodia.

Todo el resto de la librería firma a través de :class:`Firmante`. Ningún módulo
consume una clave privada directamente.

Por qué un puerto
-----------------

El Manual Técnico v150 (§7.5) contempla certificados F1, por software, y F2, por
hardware. Los prestadores hoy emiten además F3, de firma remota, donde la clave
vive en el HSM del prestador y nunca sale de ahí.

Son tres mecanismos con propiedades de seguridad muy distintas, y cuál se usa
depende de qué le vendió el prestador al contribuyente. Atar la librería a uno
solo sería atarla a la decisión de compra de un cliente.

El contrato es deliberadamente mínimo: *dame estos bytes firmados*. Un HSM sabe
hacer eso; un servicio de firma remota también. Lo que el puerto **no** ofrece
es ninguna forma de obtener la clave privada, porque para la mayoría de los
backends esa operación ni siquiera existe, y para el resto no debería.
"""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pysifen.exceptions import ConfiguracionError

if TYPE_CHECKING:  # pragma: no cover
    from pysifen.pki.certificado import Certificado

__all__ = ["Firmante", "NivelDeCustodia", "exigir_nivel"]


class NivelDeCustodia(IntEnum):
    """Qué tan expuesta está la clave privada, de menor a mayor protección.

    El orden importa: se comparan con ``<`` y ``>=`` para poder exigir un
    mínimo con :func:`exigir_nivel`.
    """

    CLAVE_EN_MEMORIA = 1
    """La clave existe como archivo y se carga en el proceso. Certificado F1.

    Quien obtenga el archivo y su contraseña puede emitir a nombre del
    contribuyente. Es el nivel que hay que evitar en producción.
    """

    CLAVE_EN_DISPOSITIVO = 2
    """La clave vive dentro de un token o HSM y no es exportable. Certificado F2.

    Si el servidor se ve comprometido, lo que se pierde es el *acceso* a firmar
    mientras dure el compromiso, no la clave.
    """

    CLAVE_FUERA_DEL_ALCANCE = 3
    """La clave nunca estuvo del lado del contribuyente. Certificado F3.

    Se genera y vive en el HSM del prestador cualificado. No hay nada que robar
    del servidor: ni archivo, ni dispositivo, ni clave en memoria.
    """

    @property
    def descripcion(self) -> str:
        """Descripción en una línea del nivel de custodia."""
        return {
            NivelDeCustodia.CLAVE_EN_MEMORIA: (
                "la clave privada se carga en memoria desde un archivo"
            ),
            NivelDeCustodia.CLAVE_EN_DISPOSITIVO: (
                "la clave privada no sale del token o HSM"
            ),
            NivelDeCustodia.CLAVE_FUERA_DEL_ALCANCE: (
                "la clave privada vive en el HSM del prestador"
            ),
        }[self]


@runtime_checkable
class Firmante(Protocol):
    """Algo capaz de firmar bytes con la clave del contribuyente.

    Las implementaciones concretas viven en :mod:`pysifen.signing.backends`.

    .. danger::
       Una implementación de este protocolo **no debe** exponer la clave
       privada, ni por atributo, ni por método, ni en su ``repr``. Si un backend
       necesita la clave en memoria, que quede encapsulada y fuera del alcance
       público.
    """

    @property
    def certificado(self) -> Certificado:
        """El certificado cuya clave privada usa este firmante.

        Es la parte pública, la que se publica dentro del ``KeyInfo`` de la
        firma.
        """
        ...

    @property
    def nivel_de_custodia(self) -> NivelDeCustodia:
        """Qué tan protegida está la clave que usa este firmante.

        Permite que una aplicación exija un mínimo sin conocer el backend
        concreto. Ver :func:`exigir_nivel`.
        """
        ...

    def firmar(self, datos: bytes) -> bytes:
        """Firma bytes con RSA y SHA-256.

        El apartado 7.7 del Manual Técnico fija RSA con SHA-256 como el único
        algoritmo admitido, así que el puerto no lo parametriza.

        Args:
            datos: los bytes a firmar. Quien llama ya se encargó de
                canonicalizar lo que corresponda; el firmante no interpreta el
                contenido.

        Returns:
            La firma en crudo, sin codificar en base64.

        Raises:
            FirmaError: si el dispositivo o el servicio de firma falla.
        """
        ...


def exigir_nivel(firmante: Firmante, minimo: NivelDeCustodia) -> Firmante:
    """Comprueba que un firmante alcance el nivel de custodia exigido.

    Sirve para que una aplicación fije su política en un solo lugar, en el
    arranque, en vez de confiar en que nadie configure mal el backend.

    Args:
        firmante: el firmante a verificar.
        minimo: nivel mínimo aceptable.

    Returns:
        El mismo firmante, para poder encadenar.

    Raises:
        ConfiguracionError: si el firmante no alcanza el nivel exigido.

    Example:
        >>> from pysifen.signing import NivelDeCustodia, exigir_nivel
        >>> firmante = exigir_nivel(  # doctest: +SKIP
        ...     construir_firmante(),
        ...     NivelDeCustodia.CLAVE_EN_DISPOSITIVO,
        ... )
    """
    actual = firmante.nivel_de_custodia
    if actual < minimo:
        raise ConfiguracionError(
            f"la política exige un nivel de custodia {minimo.name} "
            f"({minimo.descripcion}), y este firmante es {actual.name} "
            f"({actual.descripcion})"
        )
    return firmante
