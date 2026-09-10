"""Pruebas de la hora del Paraguay.

Los documentos escriben sus horas sin zona, en hora de Asunción. Tomarlas
como UTC las correría tres horas, y eso decide de qué lado de una medianoche
cae una firma.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pysifen.tiempo import ZONA_PARAGUAY, ahora, con_zona


class TestConZona:
    def test_una_hora_sin_zona_es_hora_de_asuncion(self) -> None:
        momento = con_zona(datetime(2026, 9, 10, 22, 0, 0))  # noqa: DTZ001

        assert momento.tzinfo is ZONA_PARAGUAY
        # Paraguay quedó en UTC-3 todo el año desde octubre de 2024.
        assert momento.utcoffset() == timedelta(hours=-3)

    def test_una_hora_con_zona_no_se_toca(self) -> None:
        en_utc = datetime(2026, 9, 10, 22, 0, 0, tzinfo=UTC)

        assert con_zona(en_utc) is en_utc

    def test_la_diferencia_con_utc_es_real(self) -> None:
        # Las 22:00 en Asunción son la 01:00 del día siguiente en UTC. Un
        # certificado que vence a medianoche de Asunción sigue vigente para
        # una firma de las 22:00, y no lo estaría si se leyera como UTC.
        local = con_zona(datetime(2026, 9, 10, 22, 0, 0))  # noqa: DTZ001

        assert local.astimezone(UTC).day == 11


class TestAhora:
    def test_trae_zona(self) -> None:
        assert ahora().tzinfo is ZONA_PARAGUAY
