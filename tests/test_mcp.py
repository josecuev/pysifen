"""Pruebas del servidor MCP.

Se ejercitan las herramientas directamente, sin levantar un transporte: lo que
importa es que el contrato con el modelo sea correcto y que los errores vuelvan
como dato y no como excepción.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

mcp = pytest.importorskip("mcp", reason="requiere el extra pysifen[mcp]")

from pysifen.mcp import construir_servidor  # noqa: E402

CDC = "01444444017001001001452822017012515873260988"


@pytest.fixture(scope="module")
def servidor() -> Any:
    """El servidor MCP, armado una sola vez."""
    return construir_servidor()


async def _llamar(
    servidor: Any, nombre: str, argumentos: dict[str, Any]
) -> dict[str, Any]:
    """Invoca una herramienta y devuelve su resultado estructurado."""
    resultado = await servidor.call_tool(nombre, argumentos)
    datos: dict[str, Any] = dict(resultado.structured_content or {})
    return datos


class TestHerramientasDisponibles:
    @pytest.mark.anyio
    async def test_estan_las_seis(self, servidor: Any) -> None:
        nombres = {h.name for h in await servidor.list_tools()}
        assert nombres == {
            "verificar_factura",
            "verificar_facturas",
            "analizar_cdc",
            "buscar_campo",
            "describir_grupo",
            "listar_grupos",
        }

    @pytest.mark.anyio
    async def test_todas_describen_para_que_sirven(self, servidor: Any) -> None:
        for herramienta in await servidor.list_tools():
            assert herramienta.description
            assert len(herramienta.description) > 40


class TestAnalizarCdc:
    @pytest.mark.anyio
    async def test_descompone_el_cdc(self, servidor: Any) -> None:
        datos = await _llamar(servidor, "analizar_cdc", {"codigo": CDC})
        assert datos["ok"] is True
        assert datos["ruc_emisor"] == "44444401-7"

    @pytest.mark.anyio
    async def test_un_cdc_invalido_vuelve_como_dato(self, servidor: Any) -> None:
        # Un modelo maneja mejor un resultado que una excepción.
        datos = await _llamar(servidor, "analizar_cdc", {"codigo": "123"})
        assert datos["ok"] is False
        assert datos["error"]


class TestDescubrimiento:
    @pytest.mark.anyio
    async def test_busca_un_campo(self, servidor: Any) -> None:
        datos = await _llamar(servidor, "buscar_campo", {"texto": "dTotGralOpe"})
        assert [r["grupo"] for r in datos["resultados"]] == ["TotSub"]

    @pytest.mark.anyio
    async def test_describe_un_grupo(self, servidor: Any) -> None:
        datos = await _llamar(servidor, "describir_grupo", {"nombre": "CamItem"})
        assert datos["elemento"] == "gCamItem"

    @pytest.mark.anyio
    async def test_sugiere_si_el_grupo_no_existe(self, servidor: Any) -> None:
        datos = await _llamar(servidor, "describir_grupo", {"nombre": "CamIte"})
        assert datos["ok"] is False
        assert "CamItem" in datos["error"]

    @pytest.mark.anyio
    async def test_lista_los_grupos(self, servidor: Any) -> None:
        datos = await _llamar(servidor, "listar_grupos", {})
        assert len(datos["grupos"]) == 49


class TestVerificar:
    @pytest.mark.anyio
    async def test_exige_uno_de_los_dos_argumentos(self, servidor: Any) -> None:
        datos = await _llamar(servidor, "verificar_factura", {})
        assert datos["ok"] is False
        assert "exactamente uno" in datos["error"]

    @pytest.mark.anyio
    async def test_rechaza_los_dos_a_la_vez(self, servidor: Any) -> None:
        datos = await _llamar(
            servidor, "verificar_factura", {"xml": "<a/>", "ruta": "x.xml"}
        )
        assert datos["ok"] is False

    @pytest.mark.anyio
    async def test_un_archivo_inexistente_vuelve_como_dato(self, servidor: Any) -> None:
        datos = await _llamar(servidor, "verificar_factura", {"ruta": "no-existe.xml"})
        assert datos["ok"] is False

    @pytest.mark.anyio
    async def test_un_documento_roto_no_es_confiable(self, servidor: Any) -> None:
        datos = await _llamar(servidor, "verificar_factura", {"xml": "<roto"})
        assert datos["confiable"] is False

    @pytest.mark.anyio
    async def test_siempre_declara_su_limite(self, servidor: Any) -> None:
        # Quien lea la respuesta tiene que saber qué NO se verificó.
        datos = await _llamar(servidor, "verificar_factura", {"xml": "<roto"})
        assert "revocados" in datos["limite_de_la_verificacion"]

    @pytest.mark.anyio
    async def test_el_lote_vacio_vuelve_como_dato(self, servidor: Any) -> None:
        datos = await _llamar(servidor, "verificar_facturas", {"rutas": []})
        assert datos["ok"] is False

    @pytest.mark.anyio
    async def test_el_lote_tiene_tope(self, servidor: Any) -> None:
        datos = await _llamar(
            servidor, "verificar_facturas", {"rutas": ["x.xml"] * 201}
        )
        assert datos["ok"] is False
        assert "tope" in datos["error"]

    @pytest.mark.anyio
    async def test_procesa_un_lote(self, servidor: Any, tmp_path: Path) -> None:
        archivo = tmp_path / "roto.xml"
        archivo.write_text("<roto", encoding="utf-8")
        datos = await _llamar(servidor, "verificar_facturas", {"rutas": [str(archivo)]})
        assert datos["total"] == 1
        assert datos["confiables"] == 0


class TestRespuestasSerializables:
    @pytest.mark.anyio
    async def test_todo_vuelve_como_json(self, servidor: Any) -> None:
        for nombre, argumentos in (
            ("listar_grupos", {}),
            ("analizar_cdc", {"codigo": CDC}),
            ("buscar_campo", {"texto": "dCodSeg"}),
        ):
            json.dumps(await _llamar(servidor, nombre, argumentos))
