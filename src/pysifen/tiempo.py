"""La hora del Paraguay, que es la hora de los documentos.

Los documentos del SIFEN escriben sus fechas y horas **sin zona horaria**:
``2026-09-10T18:50:50``. No es una omisión: el Manual Técnico las define en
hora local, y fija como referencia los servidores de hora de la propia DNIT
(``aravo1.set.gov.py`` y ``aravo2.set.gov.py``, apartado 7.11), que están en
Asunción.

Tratar esa hora como UTC sería correrla entre tres y cuatro horas. Casi nunca
importa, y cuando importa, importa mucho: un certificado que vence a la
medianoche y un documento firmado a las 22:00 de ese mismo día están del lado
bueno en hora de Asunción y del lado malo en UTC. Lo mismo con una revocación
de esa noche.

Así que toda hora sin zona que venga de un documento se interpreta acá, en
``America/Asuncion``, y recién después se compara con las fechas de los
certificados, que sí traen zona.

La base de datos de zonas la trae la dependencia ``tzdata``: Windows no la
tiene, y la imagen de Alpine tampoco. Depender de que el sistema la tenga sería
depender de la suerte.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final
from zoneinfo import ZoneInfo

__all__ = ["ZONA_PARAGUAY", "ahora", "con_zona"]

#: La zona horaria en la que el SIFEN escribe sus fechas.
ZONA_PARAGUAY: Final = ZoneInfo("America/Asuncion")


def con_zona(momento: datetime) -> datetime:
    """Devuelve el instante con zona, interpretando en Asunción si no la trae.

    Args:
        momento: la fecha y hora, con o sin zona.

    Returns:
        La misma fecha y hora, con zona. Si ya la traía, tal cual.

    Example:
        >>> from datetime import datetime
        >>> con_zona(
        ...     datetime(2026, 9, 10, 18, 50, 50)
        ... ).utcoffset().total_seconds() / 3600
        -3.0
    """
    if momento.tzinfo is not None:
        return momento
    return momento.replace(tzinfo=ZONA_PARAGUAY)


def ahora() -> datetime:
    """Devuelve el instante actual, con zona."""
    return datetime.now(ZONA_PARAGUAY)
