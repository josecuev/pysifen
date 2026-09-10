"""Pruebas del armado del XML del documento electrónico.

Los modelos se generan desde el esquema oficial, así que acá no se prueba que el
orden de los campos sea el correcto —eso lo garantiza el XSD— sino que el
armado, la serialización y el sobre se comporten como corresponde.
"""

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
    agregar_campos_fuera_de_firma,
    grupos_disponibles,
    sobre_rde,
)
from pysifen.documento.base import formatear
from pysifen.enums import TipoContribuyente, TipoDocumento
from pysifen.signing import firmar_documento
from pysifen.signing.backends.pkcs12 import FirmantePkcs12

CDC_DEL_MANUAL = "01444444017001001001452822017012515873260988"


def _timbrado(**cambios: object) -> Timbrado:
    """Arma un timbrado de prueba."""
    valores: dict[str, object] = {
        "iTiDE": 1,
        "dDesTiDE": "Factura electrónica",
        "dNumTim": "12558946",
        "dEst": "001",
        "dPunExp": "001",
        "dNumDoc": "0014528",
        "dFeIniT": date(2026, 1, 1),
    }
    valores.update(cambios)
    return Timbrado(**valores)  # type: ignore[arg-type]


def _documento(**cambios: object) -> DocumentoElectronico:
    """Arma un DE de prueba con los grupos que ya se pueden poblar."""
    valores: dict[str, object] = {
        "dDVId": 8,
        "dFecFirma": datetime(2026, 9, 10, 10, 0, 0),  # noqa: DTZ001
        "dSisFact": 1,
        "gOpeDE": Operacion(iTipEmi=1, dDesTipEmi="Normal", dCodSeg=587326098),
        "gTimb": _timbrado(),
        "gDatGralOpe": None,
        "gDtipDE": None,
        "gTotSub": None,
        "gCamGen": None,
        "gCamDEAsoc": (),
    }
    valores.update(cambios)
    return DocumentoElectronico.model_construct(**valores)  # type: ignore[arg-type]


class TestModelosGenerados:
    """El esquema oficial define 49 grupos y todos tienen que estar."""

    def test_estan_los_49_grupos(self) -> None:
        assert len(grupos_disponibles()) == 49

    @pytest.mark.parametrize(
        ("grupo", "para"),
        [
            ("CamFE", "factura electrónica"),
            ("CamAE", "autofactura"),
            ("CamNCDE", "nota de crédito y débito"),
            ("CamNRE", "nota de remisión"),
            ("CamDEAsoc", "documento asociado"),
            ("PagCred", "operación a crédito"),
            ("Transp", "transporte"),
            ("GrupEner", "sector energía"),
            ("GrupSeg", "sector seguros"),
        ],
    )
    def test_cubre_cada_tipo_de_documento(self, grupo: str, para: str) -> None:
        assert grupo in grupos_disponibles(), f"falta el grupo de {para}"

    def test_los_campos_conservan_el_nombre_del_sifen(self) -> None:
        # Buscar un campo en el manual y en el código tiene que dar lo mismo.
        assert "dNumTim" in Timbrado.model_fields
        assert "dCodSeg" in Operacion.model_fields

    def test_el_orden_es_el_del_esquema(self) -> None:
        # dSerieNum va entre dNumDoc y dFeIniT pese a llevar un identificador
        # posterior en el manual. Lo confirma el esquema.
        campos = list(Timbrado.model_fields)
        assert campos.index("dNumDoc") < campos.index("dSerieNum")
        assert campos.index("dSerieNum") < campos.index("dFeIniT")

    def test_las_enumeraciones_son_exactas(self) -> None:
        # El esquema exige el literal carácter por carácter.
        with pytest.raises(ValidationError):
            Operacion(iTipEmi=1, dDesTipEmi="normal", dCodSeg=587326098)  # type: ignore[arg-type]

    def test_rechaza_campos_desconocidos(self) -> None:
        with pytest.raises(ValidationError):
            _timbrado(dInventado="x")

    def test_son_inmutables(self) -> None:
        with pytest.raises(ValidationError):
            _timbrado().dNumDoc = "0000001"


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
        raiz = sobre_rde(_documento(), CDC_DEL_MANUAL)
        de = raiz.find(f"{{{NS_SIFEN}}}DE")
        assert de is not None
        assert de.get("Id") == CDC_DEL_MANUAL

    def test_los_opcionales_ausentes_no_se_emiten(self) -> None:
        raiz = sobre_rde(_documento(), CDC_DEL_MANUAL)
        de = raiz.find(f"{{{NS_SIFEN}}}DE")
        assert de is not None
        assert de.find(f"{{{NS_SIFEN}}}gDatGralOpe") is None

    def test_se_puede_armar_sin_espacio_de_nombres(self) -> None:
        assert sobre_rde(_documento(), CDC_DEL_MANUAL, espacio=None).tag == "rDE"


class TestCamposFueraDeLaFirma:
    """El QR va después de la firma porque se calcula a partir de ella."""

    def test_exige_que_el_documento_este_firmado(self) -> None:
        raiz = sobre_rde(_documento(), CDC_DEL_MANUAL)
        with pytest.raises(ValueError, match="firmar antes"):
            agregar_campos_fuera_de_firma(raiz, "https://ejemplo/qr?x=1")

    def test_se_agrega_al_final_despues_de_la_firma(
        self, firmante: FirmantePkcs12
    ) -> None:
        raiz = etree.fromstring(
            firmar_documento(
                etree.tostring(sobre_rde(_documento(), CDC_DEL_MANUAL)), firmante
            )
        )
        agregar_campos_fuera_de_firma(raiz, "https://ejemplo/qr?x=1")

        hijos = [etree.QName(h).localname for h in raiz]
        assert hijos == ["dVerFor", "DE", "Signature", "gCamFuFD"]

    def test_lleva_el_qr(self, firmante: FirmantePkcs12) -> None:
        raiz = etree.fromstring(
            firmar_documento(
                etree.tostring(sobre_rde(_documento(), CDC_DEL_MANUAL)), firmante
            )
        )
        agregar_campos_fuera_de_firma(
            raiz, "https://ejemplo/qr?x=1", informacion_adicional="nota"
        )
        qr = raiz.find(f"{{{NS_SIFEN}}}gCamFuFD/{{{NS_SIFEN}}}dCarQR")
        adicional = raiz.find(f"{{{NS_SIFEN}}}gCamFuFD/{{{NS_SIFEN}}}dInfAdic")
        assert qr is not None
        assert qr.text == "https://ejemplo/qr?x=1"
        assert adicional is not None


class TestFormateo:
    @pytest.mark.parametrize(
        ("valor", "esperado"),
        [
            (150, "150"),
            (TipoDocumento.FACTURA, "1"),
            (date(2026, 1, 1), "2026-01-01"),
            (datetime(2026, 1, 1, 9, 35, 17), "2026-01-01T09:35:17"),  # noqa: DTZ001
            # Los importes conservan sus decimales: el SIFEN los escribe así y
            # el hash del QR se calcula sobre esa cadena exacta.
            (Decimal("1000.00"), "1000.00"),
            (Decimal("36500.00000000"), "36500.00000000"),
            ("texto", "texto"),
            (True, "1"),
            (False, "0"),
        ],
    )
    def test_formatea_como_espera_el_sifen(self, valor: object, esperado: str) -> None:
        assert formatear(valor) == esperado


class TestIntegracionConLaFirma:
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
        raiz = sobre_rde(_documento(dDVId=cdc.dv), cdc.valor)
        firmado = firmar_documento(etree.tostring(raiz), firmante)

        arbol = etree.fromstring(firmado)
        ds = "{http://www.w3.org/2000/09/xmldsig#}"
        referencia = arbol.find(f"{ds}Signature/{ds}SignedInfo/{ds}Reference")
        assert referencia is not None
        assert referencia.get("URI") == f"#{cdc.valor}"

    def test_lo_firmado_verifica_con_una_implementacion_independiente(
        self, firmante: FirmantePkcs12
    ) -> None:
        from signxml import XMLVerifier  # type: ignore[attr-defined]

        raiz = sobre_rde(_documento(), CDC_DEL_MANUAL)
        firmado = firmar_documento(etree.tostring(raiz), firmante)

        XMLVerifier().verify(
            firmado, x509_cert=firmante.certificado.x509, expect_references=1
        )
