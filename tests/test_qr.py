"""Pruebas del código QR.

El caso de referencia es el ejemplo del apartado 13.8.4 del Manual Técnico v150,
incluidos los valores hexadecimales que el propio manual publica.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal

import pytest

from pysifen.enums import Ambiente
from pysifen.exceptions import ValidacionError
from pysifen.qr import DatosQr, generar_url_qr
from pysifen.security import Secreto

CDC_DEL_MANUAL = "01444444017001001001452822017012515873260988"
DIGEST_DEL_MANUAL = "yzGYhUx1/XYYzksWB+fPR3Qc50c="
CSC_DEL_MANUAL = "ABCD0000000000000000000000000000"

# Cadena del paso 1 tal como la publica el manual en 13.8.4.1.
CADENA_DEL_MANUAL = (
    "nVersion=150"
    f"&Id={CDC_DEL_MANUAL}"
    "&dFeEmiDE=323031372d30312d32355430393a33353a3137"
    "&dRucRec=88899990"
    "&dTotGralOpe=300000"
    "&dTotIVA=27272"
    "&cItems=2"
    "&DigestValue=797a4759685578312f5859597a6b7357422b6650523351633530633d"
    "&IdCSC=0001"
)


@pytest.fixture
def datos() -> DatosQr:
    return DatosQr(
        cdc=CDC_DEL_MANUAL,
        fecha_emision=datetime(2017, 1, 25, 9, 35, 17),  # noqa: DTZ001
        digest_value=DIGEST_DEL_MANUAL,
        id_csc="0001",
        identificador_receptor="88899990",
        total_general=300000,
        total_iva=27272,
        cantidad_items=2,
        version=150,
    )


class TestConversionHexadecimal:
    def test_fecha_coincide_con_el_manual(self, datos: DatosQr) -> None:
        parametros = dict(datos.parametros())
        assert parametros["dFeEmiDE"] == "323031372d30312d32355430393a33353a3137"

    def test_digest_coincide_con_el_manual(self, datos: DatosQr) -> None:
        parametros = dict(datos.parametros())
        assert parametros["DigestValue"] == (
            "797a4759685578312f5859597a6b7357422b6650523351633530633d"
        )


class TestCadenaDeParametros:
    def test_reproduce_el_paso_1_del_manual(self, datos: DatosQr) -> None:
        assert datos.cadena_parametros() == CADENA_DEL_MANUAL

    def test_respeta_el_orden_normado(self, datos: DatosQr) -> None:
        esperado = [
            "nVersion",
            "Id",
            "dFeEmiDE",
            "dRucRec",
            "dTotGralOpe",
            "dTotIVA",
            "cItems",
            "DigestValue",
            "IdCSC",
        ]
        assert [clave for clave, _ in datos.parametros()] == esperado

    def test_receptor_sin_ruc_usa_dNumIDRec(  # noqa: N802
        self, datos: DatosQr
    ) -> None:
        otros = DatosQr(
            cdc=datos.cdc,
            fecha_emision=datos.fecha_emision,
            digest_value=datos.digest_value,
            id_csc=datos.id_csc,
            identificador_receptor="1234567",
            receptor_con_ruc=False,
        )
        assert "dNumIDRec=1234567" in otros.cadena_parametros()

    @pytest.mark.parametrize(
        ("total_general", "total_iva", "nombre"),
        [
            (None, 27272, "dTotGralOpe"),
            (300000, None, "dTotIVA"),
        ],
    )
    def test_completa_con_cero_cuando_falta_un_total(
        self,
        datos: DatosQr,
        total_general: int | None,
        total_iva: int | None,
        nombre: str,
    ) -> None:
        sin_total = DatosQr(
            cdc=datos.cdc,
            fecha_emision=datos.fecha_emision,
            digest_value=datos.digest_value,
            id_csc=datos.id_csc,
            identificador_receptor=datos.identificador_receptor,
            total_general=total_general,
            total_iva=total_iva,
        )
        assert f"{nombre}=0" in sin_total.cadena_parametros()

    def test_receptor_innominado_va_en_cero(self, datos: DatosQr) -> None:
        innominado = DatosQr(
            cdc=datos.cdc,
            fecha_emision=datos.fecha_emision,
            digest_value=datos.digest_value,
            id_csc=datos.id_csc,
            identificador_receptor=None,
        )
        assert "dRucRec=0" in innominado.cadena_parametros()

    def test_acepta_decimal(self, datos: DatosQr) -> None:
        con_decimal = DatosQr(
            cdc=datos.cdc,
            fecha_emision=datos.fecha_emision,
            digest_value=datos.digest_value,
            id_csc=datos.id_csc,
            total_general=Decimal("300000"),
        )
        assert "dTotGralOpe=300000" in con_decimal.cadena_parametros()

    def test_acepta_la_fecha_ya_formateada(self, datos: DatosQr) -> None:
        con_texto = DatosQr(
            cdc=datos.cdc,
            fecha_emision="2017-01-25T09:35:17",
            digest_value=datos.digest_value,
            id_csc=datos.id_csc,
            identificador_receptor=datos.identificador_receptor,
            total_general=300000,
            total_iva=27272,
            cantidad_items=2,
        )
        assert con_texto.cadena_parametros() == CADENA_DEL_MANUAL


class TestUrl:
    def test_hash_es_sha256_de_la_cadena_mas_el_csc(self, datos: DatosQr) -> None:
        url = generar_url_qr(datos, Secreto(CSC_DEL_MANUAL, nombre="CSC"))
        esperado = hashlib.sha256(
            f"{CADENA_DEL_MANUAL}{CSC_DEL_MANUAL}".encode()
        ).hexdigest()
        assert url.endswith(f"&cHashQR={esperado}")

    def test_el_csc_nunca_aparece_en_la_url(self, datos: DatosQr) -> None:
        url = generar_url_qr(datos, Secreto(CSC_DEL_MANUAL, nombre="CSC"))
        assert CSC_DEL_MANUAL not in url

    def test_url_de_produccion(self, datos: DatosQr) -> None:
        url = generar_url_qr(
            datos, Secreto(CSC_DEL_MANUAL), ambiente=Ambiente.PRODUCCION
        )
        assert url.startswith("https://ekuatia.set.gov.py/consultas/qr?")

    def test_url_de_test(self, datos: DatosQr) -> None:
        url = generar_url_qr(datos, Secreto(CSC_DEL_MANUAL), ambiente=Ambiente.TEST)
        assert url.startswith("https://ekuatia.set.gov.py/consultas-test/qr?")

    def test_csc_distinto_cambia_el_hash(self, datos: DatosQr) -> None:
        uno = generar_url_qr(datos, Secreto(CSC_DEL_MANUAL))
        otro = generar_url_qr(datos, Secreto("X" * 32))
        assert uno != otro

    def test_exige_el_digest_de_la_firma(self, datos: DatosQr) -> None:
        sin_firma = DatosQr(
            cdc=datos.cdc,
            fecha_emision=datos.fecha_emision,
            digest_value="",
            id_csc=datos.id_csc,
        )
        with pytest.raises(ValidacionError, match="DigestValue"):
            generar_url_qr(sin_firma, Secreto(CSC_DEL_MANUAL))

    def test_exige_el_cdc(self, datos: DatosQr) -> None:
        sin_cdc = DatosQr(
            cdc="",
            fecha_emision=datos.fecha_emision,
            digest_value=datos.digest_value,
            id_csc=datos.id_csc,
        )
        with pytest.raises(ValidacionError, match="CDC"):
            generar_url_qr(sin_cdc, Secreto(CSC_DEL_MANUAL))

    def test_exige_el_id_csc(self, datos: DatosQr) -> None:
        sin_id = DatosQr(
            cdc=datos.cdc,
            fecha_emision=datos.fecha_emision,
            digest_value=datos.digest_value,
            id_csc="",
        )
        with pytest.raises(ValidacionError, match="IdCSC"):
            generar_url_qr(sin_id, Secreto(CSC_DEL_MANUAL))
