"""Pruebas de la lectura y verificación de documentos recibidos.

Los documentos de prueba se arman y firman acá con un certificado autofirmado.
En el repositorio no entra ningún documento tributario real: traen datos de
contribuyentes.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from lxml import etree

from pysifen.documento import (
    DocumentoElectronico,
    Operacion,
    Timbrado,
    sobre_rde,
)
from pysifen.lectura import Verificacion, leer_documentos, verificar_documento
from pysifen.signing import firmar_documento
from pysifen.signing.backends.pkcs12 import FirmantePkcs12
from pysifen.signing.verificacion import verificar_firma
from tests.conftest import construir_certificado, construir_pkcs12

CDC = "01444444017001001001452822017012515873260988"


def _documento_firmado(firmante: FirmantePkcs12) -> bytes:
    """Arma y firma un documento de prueba."""
    de = DocumentoElectronico.model_construct(
        dDVId=8,
        dFecFirma=datetime(2026, 9, 10, 10, 0, 0),  # noqa: DTZ001
        dSisFact=1,
        gOpeDE=Operacion(iTipEmi=1, dDesTipEmi="Normal", dCodSeg=587326098),
        gTimb=Timbrado(
            iTiDE=1,
            dDesTiDE="Factura electrónica",
            dNumTim="12558946",
            dEst="001",
            dPunExp="001",
            dNumDoc="0014528",
            dFeIniT=date(2026, 1, 1),
        ),
        gDatGralOpe=None,
        gDtipDE=None,
        gTotSub=None,
        gCamGen=None,
        gCamDEAsoc=(),
    )
    return firmar_documento(etree.tostring(sobre_rde(de, CDC)), firmante)


class TestVerificacionDeLaFirma:
    """Lo que detecta que un documento fue alterado."""

    def test_una_firma_propia_verifica(self, firmante: FirmantePkcs12) -> None:
        arbol = etree.fromstring(_documento_firmado(firmante))
        resultado = verificar_firma(arbol)
        assert resultado.valida
        assert resultado.certificado is not None

    def test_detecta_un_solo_caracter_cambiado(self, firmante: FirmantePkcs12) -> None:
        # Es la prueba que importa: cambiar un dígito del código de seguridad
        # tiene que romper la firma.
        firmado = _documento_firmado(firmante).replace(b"587326098", b"587326099")
        resultado = verificar_firma(etree.fromstring(firmado))
        assert resultado.valida is False
        assert resultado.motivo is not None
        assert "alterado" in resultado.motivo

    def test_un_documento_sin_firma(self) -> None:
        arbol = sobre_rde(
            DocumentoElectronico.model_construct(
                dDVId=8,
                dFecFirma=datetime(2026, 9, 10, 10, 0),  # noqa: DTZ001
                dSisFact=1,
                gOpeDE=None,
                gTimb=None,
                gDatGralOpe=None,
                gDtipDE=None,
                gTotSub=None,
                gCamGen=None,
                gCamDEAsoc=(),
            ),
            CDC,
        )
        resultado = verificar_firma(arbol)
        assert resultado.tiene_firma is False
        assert resultado.valida is False

    def test_una_firma_incompleta(self, firmante: FirmantePkcs12) -> None:
        arbol = etree.fromstring(_documento_firmado(firmante))
        ds = "{http://www.w3.org/2000/09/xmldsig#}"
        valor = arbol.find(f"{ds}Signature/{ds}SignatureValue")
        assert valor is not None
        padre = valor.getparent()
        assert padre is not None
        padre.remove(valor)
        assert verificar_firma(arbol).valida is False


class TestTolerancias:
    """Desvíos del estándar que los emisores reales producen.

    El verificador los tolera porque no debilitan nada —el contenido sigue
    siendo el mismo— pero deja constancia de cuál toleró.
    """

    def test_una_firma_conforme_no_necesita_tolerancias(
        self, firmante: FirmantePkcs12
    ) -> None:
        resultado = verificar_firma(etree.fromstring(_documento_firmado(firmante)))
        assert resultado.valida
        assert resultado.estrictamente_conforme
        assert resultado.tolerancias == ()

    def test_tolera_el_xml_indentado_despues_de_firmar(
        self, firmante: FirmantePkcs12
    ) -> None:
        # Un emisor real formatea el XML una vez firmado. La canonicalización
        # conserva esos espacios, así que el resumen deja de cerrar.
        arbol = etree.fromstring(_documento_firmado(firmante))
        indentado = etree.tostring(arbol, pretty_print=True)

        resultado = verificar_firma(etree.fromstring(indentado))
        assert resultado.valida
        assert resultado.estrictamente_conforme is False
        assert any("indentación" in t for t in resultado.tolerancias)

    def test_tolera_el_signed_info_de_un_documento_con_mas_espacios_de_nombres(
        self, firmante: FirmantePkcs12
    ) -> None:
        # Dos de los cinco emisores reales arman la firma como documento
        # aparte, sin heredar el xmlns:xsi del rDE.
        firmado = _documento_firmado(firmante)
        con_xsi = firmado.replace(
            b'<rDE xmlns="http://ekuatia.set.gov.py/sifen/xsd">',
            b'<rDE xmlns="http://ekuatia.set.gov.py/sifen/xsd" '
            b'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">',
            1,
        )
        resultado = verificar_firma(etree.fromstring(con_xsi))
        # La firma sigue siendo válida: el contenido no cambió.
        assert resultado.valida

    def test_no_tolera_que_el_contenido_no_corresponda(
        self, firmante: FirmantePkcs12
    ) -> None:
        # El límite de la tolerancia: si el contenido cambió, se rechaza.
        alterado = _documento_firmado(firmante).replace(b"587326098", b"111111111")
        resultado = verificar_firma(etree.fromstring(alterado))
        assert resultado.valida is False
        assert resultado.tolerancias == ()

    def test_el_informe_declara_las_tolerancias(self, firmante: FirmantePkcs12) -> None:
        arbol = etree.fromstring(_documento_firmado(firmante))
        indentado = etree.tostring(arbol, pretty_print=True)

        resultado = verificar_documento(indentado)
        assert resultado.tolerancias
        assert "tolerancias" in resultado.resumir()
        assert any("estrictamente conforme" in o for o in resultado.observaciones)


class TestInformeCompleto:
    def test_reune_todas_las_comprobaciones(self, firmante: FirmantePkcs12) -> None:
        resultado = verificar_documento(_documento_firmado(firmante))
        assert resultado.firma_valida is True
        assert resultado.cdc == CDC
        assert resultado.cdc_coherente is True

    def test_identificar_al_prestador_no_prueba_nada(
        self, firmante: FirmantePkcs12
    ) -> None:
        # El certificado de prueba es AUTOFIRMADO y aun así se lo identifica
        # como DOCUMENTA, porque así dice su campo de emisor. Este test deja
        # constancia de la limitación: identificar por nombre clasifica, no
        # prueba. Va a cambiar cuando se valide la cadena de confianza.
        resultado = verificar_documento(_documento_firmado(firmante))
        assert resultado.prestador == "DOCUMENTA S.A."

    def test_un_emisor_desconocido_si_se_reporta(self) -> None:
        from pysifen.security.secretos import Secreto

        cert = construir_certificado(
            ruc_en_subject="RUC80012345-6", emisor="CERTIFICADORA IMAGINARIA S.A."
        )
        with pytest.warns(UserWarning, match="custodia"):
            firmante = FirmantePkcs12.desde_bytes(
                construir_pkcs12(cert),
                Secreto("prueba"),
                permitir_clave_en_memoria=True,
            )
        resultado = verificar_documento(_documento_firmado(firmante))
        assert resultado.prestador is None
        assert resultado.confiable is False
        assert any("prestador" in o for o in resultado.observaciones)

    def test_el_resumen_declara_su_propio_limite(
        self, firmante: FirmantePkcs12
    ) -> None:
        # Un modelo que lea esto tiene que enterarse de qué NO se verificó.
        resumen = verificar_documento(_documento_firmado(firmante)).resumir()
        assert "falsificable" in resumen["limite_de_la_verificacion"]

    def test_detecta_el_certificado_vencido_al_firmar(self) -> None:
        # Lo que importa es la vigencia al momento de la firma, no la de hoy.
        ahora = datetime.now(tz=None).astimezone()
        cert = construir_certificado(
            ruc_en_subject="RUC80012345-6",
            valido_desde=ahora - timedelta(days=900),
            valido_hasta=ahora - timedelta(days=500),
        )
        from pysifen.security.secretos import Secreto

        with pytest.warns(UserWarning, match="custodia"):
            firmante = FirmantePkcs12.desde_bytes(
                construir_pkcs12(cert),
                Secreto("prueba"),
                permitir_clave_en_memoria=True,
            )
        resultado = verificar_documento(_documento_firmado(firmante))
        assert resultado.certificado_vigente_a_la_firma is False
        assert any("vigente" in o for o in resultado.observaciones)

    def test_un_xml_roto_no_lanza(self) -> None:
        resultado = verificar_documento(b"<esto no es xml")
        assert resultado.confiable is False
        assert resultado.observaciones

    def test_acepta_un_lote(self, firmante: FirmantePkcs12) -> None:
        lote = etree.Element("rLoteDE")
        lote.append(etree.fromstring(_documento_firmado(firmante)))
        assert verificar_documento(lote).firma_valida is True

    def test_avisa_si_el_lote_trae_varios(self, firmante: FirmantePkcs12) -> None:
        lote = etree.Element("rLoteDE")
        for _ in range(2):
            lote.append(etree.fromstring(_documento_firmado(firmante)))
        resultado = verificar_documento(lote)
        assert any("2 documentos" in o for o in resultado.observaciones)


class TestResumenParaModelos:
    """La representación compacta, que es la que consume un modelo."""

    def test_es_mucho_mas_chico_que_el_xml(self, firmante: FirmantePkcs12) -> None:
        firmado = _documento_firmado(firmante)
        resumen = verificar_documento(firmado).resumir()
        import json

        texto = json.dumps(resumen, ensure_ascii=False)
        assert len(texto) < len(firmado) / 3

    def test_el_veredicto_va_primero(self, firmante: FirmantePkcs12) -> None:
        resumen = verificar_documento(_documento_firmado(firmante)).resumir()
        assert next(iter(resumen)) == "confiable"

    def test_omite_lo_que_no_tiene_valor(self, firmante: FirmantePkcs12) -> None:
        resumen = verificar_documento(_documento_firmado(firmante)).resumir()
        assert None not in resumen.values()

    def test_es_serializable_a_json(self, firmante: FirmantePkcs12) -> None:
        import json

        json.dumps(verificar_documento(_documento_firmado(firmante)).resumir())


class TestLote:
    def test_procesa_varios_archivos(
        self, firmante: FirmantePkcs12, tmp_path: Path
    ) -> None:
        rutas = []
        for indice in range(3):
            archivo = tmp_path / f"documento{indice}.xml"
            archivo.write_bytes(_documento_firmado(firmante))
            rutas.append(archivo)
        informes = leer_documentos(rutas)
        assert len(informes) == 3
        assert all(i.firma_valida for i in informes)

    def test_un_archivo_que_no_existe_no_frena_el_lote(self, tmp_path: Path) -> None:
        informes = leer_documentos([tmp_path / "no-existe.xml"])
        assert len(informes) == 1
        assert informes[0].confiable is False


class TestInformeLegible:
    def test_incluye_el_veredicto(self, firmante: FirmantePkcs12) -> None:
        texto = verificar_documento(_documento_firmado(firmante)).informe()
        assert CDC in texto
        assert "firma" in texto

    def test_un_informe_vacio_no_rompe(self) -> None:
        assert Verificacion().informe()
