"""Pruebas del Código de Control.

El caso de referencia es el ejemplo que trae el propio Manual Técnico v150 en
los apartados 10.1 y 13.8.4, de modo que la implementación se valida contra el
documento oficial y no contra sí misma.
"""

from __future__ import annotations

from datetime import date

import pytest

from pysifen.cdc import Cdc, calcular_dv_mod11, dv_ruc
from pysifen.enums import TipoContribuyente, TipoDocumento, TipoEmision
from pysifen.exceptions import CdcError

# Ejemplo del Manual Técnico v150, apartado 10.1.
CDC_DEL_MANUAL = "01444444017001001001452822017012515873260988"


class TestDigitoVerificador:
    def test_dv_del_ruc_del_manual(self) -> None:
        # El manual usa el RUC 44444401 con dígito verificador 7.
        assert dv_ruc("44444401") == 7

    def test_dv_del_cdc_del_manual(self) -> None:
        assert calcular_dv_mod11(CDC_DEL_MANUAL[:-1]) == 8

    def test_acepta_ruc_con_formato(self) -> None:
        assert dv_ruc("44.444.401") == 7

    @pytest.mark.parametrize("entrada", ["", "abc", "123x", " "])
    def test_rechaza_lo_que_no_sea_digito(self, entrada: str) -> None:
        with pytest.raises(CdcError):
            calcular_dv_mod11(entrada)


class TestCrear:
    def test_reproduce_el_cdc_del_manual(self) -> None:
        cdc = Cdc.crear(
            tipo_documento=TipoDocumento.FACTURA,
            ruc_emisor="44444401-7",
            establecimiento="001",
            punto_expedicion="001",
            numero="0014528",
            tipo_contribuyente=TipoContribuyente.PERSONA_JURIDICA,
            fecha_emision=date(2017, 1, 25),
            codigo_seguridad="587326098",
        )
        assert cdc.valor == CDC_DEL_MANUAL
        assert len(cdc.valor) == 44

    def test_calcula_el_dv_del_ruc_si_no_se_lo_pasa(self) -> None:
        cdc = Cdc.crear(
            tipo_documento=TipoDocumento.FACTURA,
            ruc_emisor="44444401",
            establecimiento=1,
            punto_expedicion=1,
            numero=14528,
            tipo_contribuyente=TipoContribuyente.PERSONA_JURIDICA,
            fecha_emision=date(2017, 1, 25),
            codigo_seguridad="587326098",
        )
        assert cdc.dv_ruc == 7
        assert cdc.valor == CDC_DEL_MANUAL

    def test_rellena_con_ceros_a_la_izquierda(self) -> None:
        cdc = Cdc.crear(
            tipo_documento=TipoDocumento.FACTURA,
            ruc_emisor="44444401-7",
            establecimiento="1",
            punto_expedicion="1",
            numero="14528",
            tipo_contribuyente=TipoContribuyente.PERSONA_JURIDICA,
            fecha_emision=date(2017, 1, 25),
            codigo_seguridad="587326098",
        )
        assert cdc.establecimiento == "001"
        assert cdc.numero == "0014528"

    def test_rechaza_componente_demasiado_largo(self) -> None:
        with pytest.raises(CdcError, match="establecimiento"):
            Cdc.crear(
                tipo_documento=TipoDocumento.FACTURA,
                ruc_emisor="44444401-7",
                establecimiento="12345",
                punto_expedicion="001",
                numero="0014528",
                tipo_contribuyente=TipoContribuyente.PERSONA_JURIDICA,
                fecha_emision=date(2017, 1, 25),
                codigo_seguridad="587326098",
            )

    def test_contingencia_cambia_el_cdc(self) -> None:
        def construir(tipo_emision: TipoEmision) -> Cdc:
            return Cdc.crear(
                tipo_documento=TipoDocumento.FACTURA,
                ruc_emisor="44444401-7",
                establecimiento="001",
                punto_expedicion="001",
                numero="0014528",
                tipo_contribuyente=TipoContribuyente.PERSONA_JURIDICA,
                fecha_emision=date(2017, 1, 25),
                codigo_seguridad="587326098",
                tipo_emision=tipo_emision,
            )

        assert (
            construir(TipoEmision.NORMAL).valor
            != construir(TipoEmision.CONTINGENCIA).valor
        )


class TestParse:
    def test_descompone_el_cdc_del_manual(self) -> None:
        cdc = Cdc.parse(CDC_DEL_MANUAL)
        assert cdc.tipo_documento is TipoDocumento.FACTURA
        assert cdc.ruc_emisor == "44444401"
        assert cdc.dv_ruc == 7
        assert cdc.establecimiento == "001"
        assert cdc.punto_expedicion == "001"
        assert cdc.numero == "0014528"
        assert cdc.tipo_contribuyente is TipoContribuyente.PERSONA_JURIDICA
        assert cdc.fecha_emision == date(2017, 1, 25)
        assert cdc.tipo_emision is TipoEmision.NORMAL
        assert cdc.codigo_seguridad == "587326098"
        assert cdc.dv == 8

    def test_tolera_el_formato_impreso_en_grupos_de_cuatro(self) -> None:
        agrupado = "0144 4444 0170 0100 1001 4528 2201 7012 5158 7326 0988"
        assert Cdc.parse(agrupado).valor == CDC_DEL_MANUAL

    def test_ida_y_vuelta(self) -> None:
        assert Cdc.parse(CDC_DEL_MANUAL).valor == CDC_DEL_MANUAL

    def test_rechaza_largo_incorrecto(self) -> None:
        with pytest.raises(CdcError, match="44 dígitos"):
            Cdc.parse("0144444401")

    def test_rechaza_dv_que_no_cierra(self) -> None:
        alterado = CDC_DEL_MANUAL[:-1] + "0"
        with pytest.raises(CdcError, match="dígito verificador"):
            Cdc.parse(alterado)

    def test_rechaza_fecha_imposible(self) -> None:
        # Mes 13 en la posición de la fecha, recalculando el dígito verificador
        # para que falle por la fecha y no por el dígito.
        base = list(CDC_DEL_MANUAL[:-1])
        base[29:31] = list("13")
        sin_dv = "".join(base)
        con_dv = sin_dv + str(calcular_dv_mod11(sin_dv))
        with pytest.raises(CdcError, match="fecha"):
            Cdc.parse(con_dv)

    def test_rechaza_codigo_fuera_de_tabla(self) -> None:
        # Tipo de documento 99, que no existe en la tabla del manual.
        base = "99" + CDC_DEL_MANUAL[2:-1]
        con_dv = base + str(calcular_dv_mod11(base))
        with pytest.raises(CdcError, match="fuera de tabla"):
            Cdc.parse(con_dv)


class TestPresentacion:
    def test_formateado_en_grupos_de_cuatro(self) -> None:
        cdc = Cdc.parse(CDC_DEL_MANUAL)
        assert cdc.formateado == (
            "0144 4444 0170 0100 1001 4528 2201 7012 5158 7326 0988"
        )

    def test_numero_de_documento(self) -> None:
        assert Cdc.parse(CDC_DEL_MANUAL).numero_documento == "001-001-0014528"

    def test_str_devuelve_el_cdc(self) -> None:
        assert str(Cdc.parse(CDC_DEL_MANUAL)) == CDC_DEL_MANUAL

    def test_es_inmutable(self) -> None:
        cdc = Cdc.parse(CDC_DEL_MANUAL)
        with pytest.raises((AttributeError, TypeError)):
            cdc.numero = "0000001"  # type: ignore[misc]
