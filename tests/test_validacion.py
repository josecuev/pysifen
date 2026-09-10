"""Pruebas de la validación contra el esquema oficial."""

from __future__ import annotations

import hashlib
import json

import pytest
from lxml import etree

from pysifen.documento import DocumentoElectronico, sobre_rde
from pysifen.validacion import (
    DIRECTORIO_DE_ESQUEMAS,
    URL_OFICIAL,
    esquema_de_documento,
    esquema_de_evento,
    validar_documento,
    validar_evento,
)

NS = "http://ekuatia.set.gov.py/sifen/xsd"


class TestLosEsquemasIncluidos:
    """Las copias tienen que ser idénticas a las que publica la DNIT.

    Si alguien las edita para "arreglar" algo, la librería empieza a aceptar
    documentos que el SIFEN rechaza, que es la peor falla posible acá.
    """

    def test_coinciden_con_el_manifiesto(self) -> None:
        manifiesto = json.loads(
            (DIRECTORIO_DE_ESQUEMAS / "checksums.json").read_text(encoding="utf-8")
        )
        for nombre, esperado in manifiesto["archivos"].items():
            ruta = DIRECTORIO_DE_ESQUEMAS / nombre
            assert ruta.is_file(), f"falta {nombre}"
            actual = hashlib.sha256(ruta.read_bytes()).hexdigest()
            assert actual == esperado["sha256"], (
                f"{nombre} fue modificado; las copias deben ser idénticas a las "
                f"de {URL_OFICIAL}"
            )

    def test_el_manifiesto_cubre_todos_los_esquemas(self) -> None:
        manifiesto = json.loads(
            (DIRECTORIO_DE_ESQUEMAS / "checksums.json").read_text(encoding="utf-8")
        )
        en_disco = {p.name for p in DIRECTORIO_DE_ESQUEMAS.glob("*.xsd")}
        assert en_disco == set(manifiesto["archivos"])

    def test_apunta_al_origen_oficial(self) -> None:
        manifiesto = json.loads(
            (DIRECTORIO_DE_ESQUEMAS / "checksums.json").read_text(encoding="utf-8")
        )
        assert manifiesto["origen"] == URL_OFICIAL


class TestCompilacion:
    def test_el_esquema_de_documento_compila(self) -> None:
        # Los include son URL absolutas; se resuelven contra las copias locales
        # sin salir a la red.
        assert isinstance(esquema_de_documento(), etree.XMLSchema)

    def test_el_esquema_de_evento_compila(self) -> None:
        assert isinstance(esquema_de_evento(), etree.XMLSchema)

    def test_se_reutiliza(self) -> None:
        # Compilar el esquema completo es caro; tiene que quedar cacheado.
        assert esquema_de_documento() is esquema_de_documento()


class TestValidacionDeDocumentos:
    def test_un_documento_ajeno_al_esquema_no_valida(self) -> None:
        problemas = validar_documento(f'<rDE xmlns="{NS}"><cualquiera/></rDE>')
        assert problemas

    def test_el_sobre_incompleto_reporta_lo_que_falta(self) -> None:
        # El armador todavía cubre sólo los grupos AA, A, B y C, así que un
        # documento suyo no es válido: le faltan los datos generales. Este test
        # deja constancia del hueco y falla cuando se lo cierre.
        raiz = sobre_rde(
            DocumentoElectronico.model_construct(
                dDVId=8,
                dFecFirma="2026-09-10T10:00:00",
                dSisFact=1,
                gOpeDE=None,
                gTimb=None,
            ),
            "0" * 44,
        )
        assert validar_documento(raiz)

    def test_acepta_un_lote(self) -> None:
        lote = etree.Element("rLoteDE")
        lote.append(etree.fromstring(f'<rDE xmlns="{NS}"><malo/></rDE>'))
        problemas = validar_documento(lote)
        assert problemas
        assert problemas[0].startswith("documento 1:")

    def test_acepta_bytes_texto_y_elemento(self) -> None:
        crudo = f'<rDE xmlns="{NS}"><malo/></rDE>'
        assert validar_documento(crudo)
        assert validar_documento(crudo.encode())
        assert validar_documento(etree.fromstring(crudo))

    def test_los_problemas_traen_la_linea(self) -> None:
        problemas = validar_documento(f'<rDE xmlns="{NS}"><malo/></rDE>')
        assert all(p.startswith("línea ") for p in problemas)


class TestValidacionDeEventos:
    def test_un_evento_ajeno_al_esquema_no_valida(self) -> None:
        assert validar_evento(f'<gGroupGesEve xmlns="{NS}"><malo/></gGroupGesEve>')


class TestTiposDeDocumentoCubiertos:
    """El esquema tiene que traer los grupos de todos los tipos de documento."""

    @pytest.mark.parametrize(
        "tipo",
        [
            "tgCamFE",  # factura
            "tgCamAE",  # autofactura
            "tgCamNCDE",  # nota de crédito y débito
            "tgCamNRE",  # nota de remisión
            "tgCamDEAsoc",  # documento asociado
            "tgPagCred",  # operación a crédito
            "tgTransp",  # transporte
        ],
    )
    def test_el_esquema_define_el_grupo(self, tipo: str) -> None:
        texto = (DIRECTORIO_DE_ESQUEMAS / "DE_v150.xsd").read_text(encoding="utf-8")
        assert f'name="{tipo}"' in texto
