"""Pruebas del armado del XML del documento electrónico."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from lxml import etree
from pydantic import ValidationError

from pysifen.cdc import Cdc
from pysifen.documento import (
    NS_SIFEN,
    VERSION_DEL_FORMATO,
    DocumentoElectronico,
    Operacion,
    Timbrado,
    identificadores_del_manual,
    sobre_rde,
)
from pysifen.documento.base import formatear
from pysifen.enums import TipoContribuyente, TipoDocumento, TipoEmision
from pysifen.signing import firmar_documento
from pysifen.signing.backends.pkcs12 import FirmantePkcs12

CDC_DEL_MANUAL = "01444444017001001001452822017012515873260988"


def _timbrado(**cambios: object) -> Timbrado:
    """Arma un timbrado de prueba, con los cambios que se pidan."""
    valores: dict[str, object] = {
        "iTiDE": TipoDocumento.FACTURA,
        "dDesTiDE": TipoDocumento.FACTURA.descripcion,
        "dNumTim": "12558946",
        "dEst": "001",
        "dPunExp": "001",
        "dNumDoc": "0014528",
        "dFeIniT": date(2026, 1, 1),
    }
    valores.update(cambios)
    return Timbrado(**valores)  # type: ignore[arg-type]


def _documento(**cambios: object) -> DocumentoElectronico:
    """Arma un DE de prueba, con los cambios que se pidan."""
    valores: dict[str, object] = {
        "dDVId": 8,
        "dFecFirma": datetime(2026, 9, 10, 10, 0, 0),  # noqa: DTZ001
        "dSisFact": 1,
        "gOpeDE": Operacion.normal("587326098"),
        "gTimb": _timbrado(),
    }
    valores.update(cambios)
    return DocumentoElectronico(**valores)  # type: ignore[arg-type]


class TestEstructuraDelSobre:
    def test_la_raiz_es_rde_con_el_espacio_del_sifen(self) -> None:
        raiz = sobre_rde(_documento(), CDC_DEL_MANUAL)
        assert etree.QName(raiz).localname == "rDE"
        assert etree.QName(raiz).namespace == NS_SIFEN

    def test_la_version_del_formato_es_150(self) -> None:
        raiz = sobre_rde(_documento(), CDC_DEL_MANUAL)
        version = raiz.find(f"{{{NS_SIFEN}}}dVerFor")
        assert version is not None
        assert version.text == str(VERSION_DEL_FORMATO) == "150"

    def test_el_cdc_va_como_atributo_id_del_de(self) -> None:
        # Es lo que exige el apartado 7.6: el Id del DE es el CDC, y la firma
        # apunta ahí.
        raiz = sobre_rde(_documento(), CDC_DEL_MANUAL)
        de = raiz.find(f"{{{NS_SIFEN}}}DE")
        assert de is not None
        assert de.get("Id") == CDC_DEL_MANUAL

    def test_el_orden_de_los_hijos_del_de(self) -> None:
        raiz = sobre_rde(_documento(), CDC_DEL_MANUAL)
        de = raiz.find(f"{{{NS_SIFEN}}}DE")
        assert de is not None
        assert [etree.QName(h).localname for h in de] == [
            "dDVId",
            "dFecFirma",
            "dSisFact",
            "gOpeDE",
            "gTimb",
        ]

    def test_se_puede_armar_sin_espacio_de_nombres(self) -> None:
        raiz = sobre_rde(_documento(), CDC_DEL_MANUAL, espacio=None)
        assert raiz.tag == "rDE"


class TestGrupoOperacion:
    def test_orden_de_los_campos(self) -> None:
        elemento = Operacion.normal("587326098").a_elemento()
        assert [h.tag for h in elemento] == ["iTipEmi", "dDesTipEmi", "dCodSeg"]

    def test_la_etiqueta_es_gopede(self) -> None:
        assert Operacion.normal("587326098").a_elemento().tag == "gOpeDE"

    def test_la_descripcion_acompana_al_tipo(self) -> None:
        operacion = Operacion.normal("587326098")
        assert operacion.iTipEmi is TipoEmision.NORMAL
        assert operacion.dDesTipEmi == "Normal"

    def test_los_opcionales_ausentes_no_se_emiten(self) -> None:
        # Ocurrencia 0-1: un elemento vacío no es lo mismo que uno ausente.
        elemento = Operacion.normal("587326098").a_elemento()
        assert elemento.find("dInfoEmi") is None
        assert elemento.find("dInfoFisc") is None

    def test_los_opcionales_presentes_si_se_emiten(self) -> None:
        operacion = Operacion.normal("587326098", dInfoFisc="Nota de remisión")
        elemento = operacion.a_elemento()
        nodo = elemento.find("dInfoFisc")
        assert nodo is not None
        assert nodo.text == "Nota de remisión"

    @pytest.mark.parametrize("invalido", ["12345678", "1234567890", "abcdefghi"])
    def test_rechaza_codigo_de_seguridad_invalido(self, invalido: str) -> None:
        with pytest.raises(ValidationError):
            Operacion.normal(invalido)


class TestGrupoTimbrado:
    def test_orden_de_los_campos(self) -> None:
        # dSerieNum lleva el identificador C010 pero va entre C007 y C008.
        # Ver docs/decisiones/0001-orden-de-los-campos.md
        elemento = _timbrado(dSerieNum="AB", dFeFinT=date(2027, 1, 1)).a_elemento()
        assert [h.tag for h in elemento] == [
            "iTiDE",
            "dDesTiDE",
            "dNumTim",
            "dEst",
            "dPunExp",
            "dNumDoc",
            "dSerieNum",
            "dFeIniT",
            "dFeFinT",
        ]

    def test_la_etiqueta_es_gtimb(self) -> None:
        assert _timbrado().a_elemento().tag == "gTimb"

    def test_las_fechas_van_sin_hora(self) -> None:
        elemento = _timbrado().a_elemento()
        nodo = elemento.find("dFeIniT")
        assert nodo is not None
        assert nodo.text == "2026-01-01"

    @pytest.mark.parametrize(
        ("campo_invalido", "valor"),
        [
            ("dNumTim", "1234567"),
            ("dNumTim", "abcdefgh"),
            ("dEst", "1"),
            ("dPunExp", "0001"),
            ("dNumDoc", "123"),
        ],
    )
    def test_rechaza_largos_incorrectos(self, campo_invalido: str, valor: str) -> None:
        with pytest.raises(ValidationError):
            _timbrado(**{campo_invalido: valor})

    def test_rechaza_numeracion_en_cero(self) -> None:
        # El manual pide que un timbrado nuevo empiece en 1.
        with pytest.raises(ValidationError, match="empezar en 1"):
            _timbrado(dNumDoc="0000000")

    def test_rechaza_campos_desconocidos(self) -> None:
        # Un campo que el manual no define es un error, no algo a ignorar.
        with pytest.raises(ValidationError):
            _timbrado(dInventado="x")

    def test_es_inmutable(self) -> None:
        timbrado = _timbrado()
        with pytest.raises(ValidationError):
            timbrado.dNumDoc = "0000001"


class TestTrazabilidad:
    """La correspondencia con el manual se puede leer desde el propio código."""

    def test_los_campos_declaran_su_identificador(self) -> None:
        mapa = identificadores_del_manual(Timbrado)
        assert mapa["iTiDE"] == "C002"
        assert mapa["dNumTim"] == "C004"
        assert mapa["dSerieNum"] == "C010"

    def test_todos_los_campos_tienen_identificador(self) -> None:
        for grupo in (Operacion, Timbrado, DocumentoElectronico):
            mapa = identificadores_del_manual(grupo)
            assert set(mapa) == set(grupo.model_fields)

    def test_los_identificadores_no_se_repiten_dentro_del_grupo(self) -> None:
        for grupo in (Operacion, Timbrado, DocumentoElectronico):
            valores = list(identificadores_del_manual(grupo).values())
            assert len(valores) == len(set(valores))


class TestFormateo:
    @pytest.mark.parametrize(
        ("valor", "esperado"),
        [
            (150, "150"),
            (TipoDocumento.FACTURA, "1"),
            (date(2026, 1, 1), "2026-01-01"),
            (datetime(2026, 1, 1, 9, 35, 17), "2026-01-01T09:35:17"),  # noqa: DTZ001
            (Decimal("1000.00"), "1000"),
            (Decimal("1000.50"), "1000.5"),
            ("texto", "texto"),
            (True, "1"),
            (False, "0"),
        ],
    )
    def test_formatea_como_espera_el_sifen(self, valor: object, esperado: str) -> None:
        assert formatear(valor) == esperado


class TestIntegracionConLaFirma:
    """De punta a punta: armar el documento, calcular el CDC y firmarlo."""

    def test_documento_armado_y_firmado(self, firmante: FirmantePkcs12) -> None:
        cdc = Cdc.crear(
            tipo_documento=TipoDocumento.FACTURA,
            ruc_emisor="80012345-6",
            establecimiento="001",
            punto_expedicion="001",
            numero="0014528",
            tipo_contribuyente=TipoContribuyente.PERSONA_JURIDICA,
            fecha_emision=date(2026, 9, 10),
            codigo_seguridad="587326098",
        )

        documento = _documento(
            dDVId=cdc.dv,
            gTimb=_timbrado(
                dEst=cdc.establecimiento,
                dPunExp=cdc.punto_expedicion,
                dNumDoc=cdc.numero,
            ),
        )
        raiz = sobre_rde(documento, cdc.valor)
        firmado = firmar_documento(etree.tostring(raiz), firmante)

        arbol = etree.fromstring(firmado)
        referencia = arbol.find(
            "{http://www.w3.org/2000/09/xmldsig#}Signature"
            "/{http://www.w3.org/2000/09/xmldsig#}SignedInfo"
            "/{http://www.w3.org/2000/09/xmldsig#}Reference"
        )
        assert referencia is not None
        assert referencia.get("URI") == f"#{cdc.valor}"

    def test_lo_firmado_verifica_con_una_implementacion_independiente(
        self, firmante: FirmantePkcs12
    ) -> None:
        from signxml import XMLVerifier  # type: ignore[attr-defined]

        raiz = sobre_rde(_documento(), CDC_DEL_MANUAL)
        firmado = firmar_documento(etree.tostring(raiz), firmante)

        XMLVerifier().verify(
            firmado,
            x509_cert=firmante.certificado.x509,
            expect_references=1,
        )
