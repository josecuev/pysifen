"""Firma remota en el HSM del prestador, o sea un certificado F3.

Es el nivel de custodia más alto que existe para este caso de uso: la clave se
genera y vive dentro del HSM del prestador cualificado y **nunca estuvo del lado
del contribuyente**. No hay archivo que robar, ni token que sustraer, ni clave
en memoria que volcar.

Cada prestador expone su propio servicio de firma, con su propia autenticación y
su propio protocolo. Por eso acá no hay un cliente HTTP concreto: hay un
protocolo :class:`ServicioDeFirmaRemota` que cada prestador implementa. Sumar
uno nuevo no requiere tocar este módulo.

.. warning::
   El apartado 7.9 del Manual Técnico exige **autenticación mutua TLS** contra
   los servicios del SIFEN, y para eso hace falta una clave utilizable con
   ``clientAuth``. Antes de comprometerse a un esquema puramente remoto hay que
   confirmar con el prestador cómo se resuelve esa parte: firmar el documento y
   autenticar la conexión son dos usos distintos de la clave.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pysifen.exceptions import FirmaError
from pysifen.signing.ports import NivelDeCustodia

if TYPE_CHECKING:  # pragma: no cover
    from pysifen.pki.certificado import Certificado

__all__ = ["FirmanteRemoto", "ServicioDeFirmaRemota"]


@runtime_checkable
class ServicioDeFirmaRemota(Protocol):
    """Lo que tiene que ofrecer el servicio de firma de un prestador.

    Es el punto de extensión: para soportar un prestador nuevo alcanza con
    implementar estos dos miembros contra su API.
    """

    @property
    def certificado(self) -> Certificado:
        """El certificado cuya clave custodia el prestador."""
        ...

    def firmar_remotamente(self, datos: bytes) -> bytes:
        """Pide al prestador la firma RSA con SHA-256 de unos bytes.

        Args:
            datos: los bytes a firmar.

        Returns:
            La firma en crudo, sin codificar en base64.
        """
        ...


class FirmanteRemoto:
    """Firmante que delega la operación en el HSM de un prestador.

    Cumple el protocolo :class:`~pysifen.signing.ports.Firmante` y no hace más
    que adaptar el servicio del prestador a ese contrato, traduciendo cualquier
    falla a :class:`~pysifen.exceptions.FirmaError`.

    Args:
        servicio: la implementación del prestador.
    """

    __slots__ = ("_servicio",)

    def __init__(self, servicio: ServicioDeFirmaRemota) -> None:
        self._servicio = servicio

    @property
    def certificado(self) -> Certificado:
        """El certificado del contribuyente, que informa el prestador."""
        return self._servicio.certificado

    @property
    def nivel_de_custodia(self) -> NivelDeCustodia:
        """La clave nunca estuvo del lado del contribuyente."""
        return NivelDeCustodia.CLAVE_FUERA_DEL_ALCANCE

    def firmar(self, datos: bytes) -> bytes:
        """Pide la firma al prestador.

        Args:
            datos: los bytes a firmar, ya canonicalizados por quien llama.

        Returns:
            La firma en crudo.

        Raises:
            FirmaError: si el servicio falla o devuelve algo que no son bytes.
        """
        try:
            firma = self._servicio.firmar_remotamente(datos)
        except FirmaError:
            raise
        except Exception as exc:
            raise FirmaError(f"el servicio de firma remota falló: {exc}") from exc

        if not isinstance(firma, bytes) or not firma:
            raise FirmaError("el servicio de firma remota no devolvió una firma válida")
        return firma

    def __repr__(self) -> str:
        """Representación sin datos del servicio ni credenciales."""
        return f"FirmanteRemoto(servicio={type(self._servicio).__name__})"

    def __getstate__(self) -> object:
        """Impide serializar el firmante.

        Raises:
            TypeError: siempre.
        """
        raise TypeError("un firmante no se puede serializar")
