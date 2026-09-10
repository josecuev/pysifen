"""Registro de las operaciones de firma.

Firmar un documento tributario es un acto con consecuencias jurídicas. Saber
cuántas veces se firmó, cuándo y con qué certificado es lo que permite detectar
un uso indebido de la clave: si el registro muestra firmas a las tres de la
mañana de un domingo, algo pasó.

:class:`FirmanteAuditado` envuelve a cualquier firmante y anota cada operación.
Es un decorador, no una clase base: se puede aplicar sobre el backend que sea
sin que ninguno se entere.

Qué se registra y qué no
------------------------

Se registra el **hecho**: cuándo, con qué certificado, si salió bien, y un
resumen SHA-256 de lo firmado que sirve para correlacionar sin revelar nada.

**No** se registra el contenido firmado, ni la firma, ni la clave, ni ningún
secreto. Un registro de auditoría que filtra lo que audita no sirve para nada.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pysifen.exceptions import FirmaError

if TYPE_CHECKING:  # pragma: no cover
    from pysifen.pki.certificado import Certificado
    from pysifen.signing.ports import Firmante, NivelDeCustodia

__all__ = ["EventoDeFirma", "FirmanteAuditado", "registrar_en_log"]

_LOG = logging.getLogger("pysifen.firma")


@dataclass(frozen=True, slots=True)
class EventoDeFirma:
    """Una operación de firma, exitosa o fallida.

    Attributes:
        momento: instante de la operación, en UTC.
        titular: nombre del titular del certificado usado.
        serie_del_certificado: número de serie, en hexadecimal. Identifica sin
            ambigüedad qué certificado se usó.
        nivel_de_custodia: nombre del nivel del firmante subyacente.
        resumen_de_lo_firmado: SHA-256 en hexadecimal de los bytes firmados.
            Permite correlacionar dos registros sin revelar el contenido.
        exitosa: si la operación terminó bien.
        motivo_de_la_falla: descripción del error, si lo hubo.
    """

    momento: datetime
    titular: str
    serie_del_certificado: str
    nivel_de_custodia: str
    resumen_de_lo_firmado: str
    exitosa: bool
    motivo_de_la_falla: str | None = None


def registrar_en_log(evento: EventoDeFirma) -> None:
    """Escribe el evento en el log ``pysifen.firma``.

    Es el registrador por omisión. Una aplicación puede pasar el suyo para
    mandar los eventos a una base de datos o a un sistema de auditoría.

    Args:
        evento: el evento a registrar.
    """
    if evento.exitosa:
        _LOG.info(
            "firma emitida titular=%s serie=%s custodia=%s resumen=%s",
            evento.titular,
            evento.serie_del_certificado,
            evento.nivel_de_custodia,
            evento.resumen_de_lo_firmado[:16],
        )
    else:
        _LOG.warning(
            "firma fallida titular=%s serie=%s custodia=%s motivo=%s",
            evento.titular,
            evento.serie_del_certificado,
            evento.nivel_de_custodia,
            evento.motivo_de_la_falla,
        )


class FirmanteAuditado:
    """Envuelve un firmante y registra cada operación.

    Cumple el mismo protocolo que el firmante que envuelve, así que se puede
    usar en cualquier lugar donde se espere un
    :class:`~pysifen.signing.ports.Firmante`.

    Args:
        firmante: el firmante real.
        registrar: función que recibe cada :class:`EventoDeFirma`. Por omisión,
            :func:`registrar_en_log`.

    Example:
        >>> auditado = FirmanteAuditado(firmante)  # doctest: +SKIP
        >>> firmar_documento(xml, auditado)  # doctest: +SKIP
    """

    __slots__ = ("_firmante", "_registrar")

    def __init__(
        self,
        firmante: Firmante,
        registrar: Callable[[EventoDeFirma], None] = registrar_en_log,
    ) -> None:
        self._firmante = firmante
        self._registrar = registrar

    @property
    def certificado(self) -> Certificado:
        """El certificado del firmante envuelto."""
        return self._firmante.certificado

    @property
    def nivel_de_custodia(self) -> NivelDeCustodia:
        """El nivel del firmante envuelto. Auditar no cambia la custodia."""
        return self._firmante.nivel_de_custodia

    def firmar(self, datos: bytes) -> bytes:
        """Firma y registra el resultado, haya salido bien o mal.

        Args:
            datos: los bytes a firmar.

        Returns:
            La firma en crudo.

        Raises:
            FirmaError: lo que haya fallado en el firmante envuelto, después de
                dejarlo registrado.
        """
        resumen = hashlib.sha256(datos).hexdigest()
        try:
            firma = self._firmante.firmar(datos)
        except FirmaError as exc:
            self._anotar(resumen, exitosa=False, motivo=str(exc))
            raise
        self._anotar(resumen, exitosa=True, motivo=None)
        return firma

    def _anotar(self, resumen: str, *, exitosa: bool, motivo: str | None) -> None:
        """Arma el evento y se lo pasa al registrador."""
        certificado = self._firmante.certificado
        self._registrar(
            EventoDeFirma(
                momento=datetime.now(UTC),
                titular=certificado.titular,
                serie_del_certificado=certificado.numero_de_serie,
                nivel_de_custodia=self._firmante.nivel_de_custodia.name,
                resumen_de_lo_firmado=resumen,
                exitosa=exitosa,
                motivo_de_la_falla=motivo,
            )
        )

    def __repr__(self) -> str:
        """Representación que muestra qué firmante envuelve."""
        return f"FirmanteAuditado({self._firmante!r})"
