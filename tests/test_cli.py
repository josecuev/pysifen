"""Pruebas de la línea de comandos.

La CLI es la puerta de entrada para quien no conoce la estructura del documento
—una persona explorando, o un agente que necesita descubrirla— así que se
verifica sobre todo que describa bien y que la salida JSON sea consumible.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pysifen.cli import main

CDC_DEL_MANUAL = "01444444017001001001452822017012515873260988"


def _json(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    """Lee la salida y la interpreta como JSON."""
    datos: dict[str, Any] = json.loads(capsys.readouterr().out)
    return datos


class TestDescubrimiento:
    """Lo que permite usar la librería sin saberse el manual de memoria."""

    def test_lista_los_49_grupos(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--json", "grupos"]) == 0
        datos = _json(capsys)
        assert datos["total"] == 49

    def test_describe_un_grupo_con_sus_campos(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["--json", "grupo", "CamItem"]) == 0
        datos = _json(capsys)
        assert datos["elemento"] == "gCamItem"
        campos = {c["campo"]: c for c in datos["campos"]}
        assert "dDesProSer" in campos
        assert campos["dDesProSer"]["obligatorio"] is True

    def test_dice_si_un_campo_es_opcional(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(["--json", "grupo", "DTim"])
        campos = {c["campo"]: c for c in _json(capsys)["campos"]}
        assert campos["dSerieNum"]["obligatorio"] is False
        assert campos["dNumTim"]["obligatorio"] is True

    def test_encuentra_en_que_grupo_vive_un_campo(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Es la pregunta más frecuente: "¿dónde va este campo?"
        assert main(["--json", "buscar", "dTotGralOpe"]) == 0
        datos = _json(capsys)
        assert [r["grupo"] for r in datos["resultados"]] == ["TotSub"]

    def test_la_busqueda_tambien_mira_las_descripciones(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(["--json", "buscar", "timbrado"])
        assert _json(capsys)["resultados"]

    def test_sugiere_cuando_el_grupo_no_existe(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["grupo", "CamIte"]) == 1
        assert "CamItem" in capsys.readouterr().err

    def test_grupo_inexistente_sin_parecidos(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["grupo", "Inexistente"]) == 1
        assert "no existe" in capsys.readouterr().err


class TestCdc:
    def test_descompone_el_cdc_del_manual(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["--json", "cdc", CDC_DEL_MANUAL]) == 0
        datos = _json(capsys)
        assert datos["tipo_documento"] == "FACTURA"
        assert datos["ruc_emisor"] == "44444401-7"
        assert datos["numero_documento"] == "001-001-0014528"
        assert datos["fecha_emision"] == "2017-01-25"

    def test_rechaza_un_cdc_invalido(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["cdc", "123"]) == 1
        assert "error:" in capsys.readouterr().err


class TestValidacion:
    def test_devuelve_2_si_el_documento_es_invalido(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # El código de salida permite usarlo en un script sin leer la salida.
        archivo = tmp_path / "malo.xml"
        archivo.write_text(
            '<rDE xmlns="http://ekuatia.set.gov.py/sifen/xsd"><malo/></rDE>',
            encoding="utf-8",
        )
        assert main(["--json", "validar", str(archivo)]) == 2
        datos = _json(capsys)
        assert datos["valido"] is False
        assert datos["problemas"]

    def test_avisa_si_el_archivo_no_existe(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["validar", str(tmp_path / "no-existe.xml")]) == 1
        assert "no encontré" in capsys.readouterr().err


class TestEsquemas:
    def test_informa_el_origen_oficial(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["--json", "esquemas"]) == 0
        datos = _json(capsys)
        assert datos["origen"] == "https://ekuatia.set.gov.py/sifen/xsd/"
        assert len(datos["archivos"]) == 11


class TestSalidaParaLeer:
    """La salida sin --json tiene que ser legible, no un volcado."""

    @pytest.mark.parametrize(
        "argumentos",
        [
            ["grupos"],
            ["grupo", "COpeDE"],
            ["buscar", "dCodSeg"],
            ["cdc", CDC_DEL_MANUAL],
            ["esquemas"],
        ],
    )
    def test_no_rompe(
        self, argumentos: list[str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(argumentos) == 0
        assert capsys.readouterr().out.strip()
