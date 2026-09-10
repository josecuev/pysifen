"""Pruebas de la lectura y verificación de documentos recibidos.

Los documentos de prueba se arman y firman acá, con un certificado emitido por
la jerarquía de prueba que arma ``conftest``. En el repositorio no entra ningún
documento tributario real: traen datos de contribuyentes.

Casi todas las pruebas verifican contra ``anclas_de_prueba`` y no contra la
Lista de Confianza real. No es una comodidad: la lista real sólo reconoce a los
prestadores cualificados de verdad, así que un documento de prueba jamás podría
salir confiable contra ella. Y que no pueda es exactamente lo que se quiere.
"""

from __future__ import annotations

from collections.abc import Callable
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
from pysifen.pki.cadena import ListaDeConfianza
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
        gOpeDE=Operacion(iTipEmi=1, dDesTipEmi="Normal", dCodSeg="587326098"),
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


@pytest.fixture
def verificar(anclas_de_prueba: ListaDeConfianza) -> Callable[..., Verificacion]:
    """Verifica contra la jerarquía de prueba en vez de contra la real."""

    def _verificar(xml: object, **extras: object) -> Verificacion:
        return verificar_documento(xml, lista=anclas_de_prueba, **extras)  # type: ignore[arg-type]

    return _verificar


class TestVerificacionDeLaFirma:
    """Lo que detecta que un documento fue alterado."""

    def test_una_firma_propia_verifica(
        self, firmante: FirmantePkcs12, verificar: Callable[..., Verificacion]
    ) -> None:
        arbol = etree.fromstring(_documento_firmado(firmante))
        resultado = verificar_firma(arbol)
        assert resultado.valida
        assert resultado.certificado is not None

    def test_detecta_un_solo_caracter_cambiado(
        self, firmante: FirmantePkcs12, verificar: Callable[..., Verificacion]
    ) -> None:
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

    def test_una_firma_incompleta(
        self, firmante: FirmantePkcs12, verificar: Callable[..., Verificacion]
    ) -> None:
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

    def test_el_informe_declara_las_tolerancias(
        self, firmante: FirmantePkcs12, verificar: Callable[..., Verificacion]
    ) -> None:
        arbol = etree.fromstring(_documento_firmado(firmante))
        indentado = etree.tostring(arbol, pretty_print=True)

        resultado = verificar(indentado)
        assert resultado.tolerancias
        assert "tolerancias" in resultado.resumir()
        assert any("estrictamente conforme" in o for o in resultado.observaciones)


class TestInformeCompleto:
    def test_reune_todas_las_comprobaciones(
        self, firmante: FirmantePkcs12, verificar: Callable[..., Verificacion]
    ) -> None:
        resultado = verificar(_documento_firmado(firmante))
        assert resultado.firma_valida is True
        assert resultado.cdc == CDC
        assert resultado.cdc_coherente is True

    def test_el_prestador_sale_de_la_cadena_y_no_del_nombre(
        self, firmante: FirmantePkcs12, verificar: Callable[..., Verificacion]
    ) -> None:
        # El prestador que se informa es el que EMITIÓ el certificado según la
        # lista de confianza, comprobando su firma en cada eslabón. No el nombre
        # que el certificado declara, que es texto que cualquiera escribe.
        resultado = verificar(_documento_firmado(firmante))
        assert resultado.cadena_valida
        assert resultado.prestador == "PRESTADOR DE PRUEBA S.A."
        assert resultado.cadena is not None
        assert resultado.cadena.cadena[-1] == "Autoridad Certificadora Raíz de Prueba"

    def test_un_certificado_que_dice_ser_de_un_prestador_no_alcanza(
        self, verificar: Callable[..., Verificacion]
    ) -> None:
        # Es el ataque que la validación de cadena cierra: un certificado
        # AUTOFIRMADO que declara "DOCUMENTA S.A." como emisor. El nombre es
        # texto libre; la firma de DOCUMENTA sobre él, no. Antes esto pasaba
        # como confiable.
        from pysifen.security.secretos import Secreto

        impostor = construir_certificado(
            ruc_en_subject="RUC80012345-6", emisor="DOCUMENTA S.A."
        )
        with pytest.warns(UserWarning, match="custodia"):
            firmante = FirmantePkcs12.desde_bytes(
                construir_pkcs12(impostor),
                Secreto("prueba"),
                permitir_clave_en_memoria=True,
            )
        resultado = verificar(_documento_firmado(firmante))
        assert resultado.firma_valida is True  # la firma cierra: es su clave
        assert resultado.cadena_valida is False  # pero no encadena con nadie
        assert resultado.prestador is None
        assert resultado.confiable is False
        assert any("cadena de confianza" in o for o in resultado.observaciones)

    def test_el_resumen_declara_su_propio_limite(
        self, firmante: FirmantePkcs12, verificar: Callable[..., Verificacion]
    ) -> None:
        # Un modelo que lea esto tiene que enterarse de qué NO se verificó. Lo
        # único que queda afuera es la revocación, que necesita red.
        resumen = verificar(_documento_firmado(firmante)).resumir()
        assert "revocados" in resumen["limite_de_la_verificacion"]
        assert resumen["verificacion"]["cadena_de_confianza"] is True

    def test_detecta_el_certificado_vencido_al_firmar(
        self, verificar: Callable[..., Verificacion]
    ) -> None:
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
        resultado = verificar(_documento_firmado(firmante))
        assert resultado.certificado_vigente_a_la_firma is False
        assert any("vigente" in o for o in resultado.observaciones)

    def test_un_xml_roto_no_lanza(self, verificar: Callable[..., Verificacion]) -> None:
        resultado = verificar(b"<esto no es xml")
        assert resultado.confiable is False
        assert resultado.observaciones

    def test_acepta_un_lote(
        self, firmante: FirmantePkcs12, verificar: Callable[..., Verificacion]
    ) -> None:
        lote = etree.Element("rLoteDE")
        lote.append(etree.fromstring(_documento_firmado(firmante)))
        assert verificar(lote).firma_valida is True

    def test_avisa_si_el_lote_trae_varios(
        self, firmante: FirmantePkcs12, verificar: Callable[..., Verificacion]
    ) -> None:
        lote = etree.Element("rLoteDE")
        for _ in range(2):
            lote.append(etree.fromstring(_documento_firmado(firmante)))
        resultado = verificar(lote)
        assert any("2 documentos" in o for o in resultado.observaciones)


class TestResumenParaModelos:
    """La representación compacta, que es la que consume un modelo."""

    def test_es_mucho_mas_chico_que_el_xml(
        self, firmante: FirmantePkcs12, verificar: Callable[..., Verificacion]
    ) -> None:
        # Sin validar el esquema a proposito: el documento de prueba es minimo
        # y no valida, asi que su resumen se llenaria del volcado de errores y
        # se estaria midiendo eso en vez del resumen. Sobre documentos reales la
        # relacion es de 8 a 11 veces.
        firmado = _documento_firmado(firmante)
        resumen = verificar(firmado, validar_esquema=False).resumir()
        import json

        texto = json.dumps(resumen, ensure_ascii=False)
        assert len(texto) < len(firmado) / 3

    def test_el_veredicto_va_primero(
        self, firmante: FirmantePkcs12, verificar: Callable[..., Verificacion]
    ) -> None:
        resumen = verificar(_documento_firmado(firmante)).resumir()
        assert next(iter(resumen)) == "confiable"

    def test_omite_lo_que_no_tiene_valor(
        self, firmante: FirmantePkcs12, verificar: Callable[..., Verificacion]
    ) -> None:
        resumen = verificar(_documento_firmado(firmante)).resumir()
        assert None not in resumen.values()

    def test_es_serializable_a_json(
        self, firmante: FirmantePkcs12, verificar: Callable[..., Verificacion]
    ) -> None:
        import json

        json.dumps(verificar(_documento_firmado(firmante)).resumir())


class TestLote:
    def test_procesa_varios_archivos(
        self,
        firmante: FirmantePkcs12,
        tmp_path: Path,
        anclas_de_prueba: ListaDeConfianza,
    ) -> None:
        rutas = []
        for indice in range(3):
            archivo = tmp_path / f"documento{indice}.xml"
            archivo.write_bytes(_documento_firmado(firmante))
            rutas.append(archivo)
        informes = leer_documentos(rutas, lista=anclas_de_prueba)
        assert len(informes) == 3
        assert all(i.firma_valida and i.cadena_valida for i in informes)

    def test_un_archivo_que_no_existe_no_frena_el_lote(self, tmp_path: Path) -> None:
        informes = leer_documentos([tmp_path / "no-existe.xml"])
        assert len(informes) == 1
        assert informes[0].confiable is False


class TestInformeLegible:
    def test_incluye_el_veredicto(
        self, firmante: FirmantePkcs12, verificar: Callable[..., Verificacion]
    ) -> None:
        texto = verificar(_documento_firmado(firmante)).informe()
        assert CDC in texto
        assert "firma" in texto

    def test_un_informe_vacio_no_rompe(self) -> None:
        assert Verificacion().informe()


#: Un rDE con los grupos que la lectura mira: emisor, totales, items y QR.
#:
#: Se arma como texto y no con los modelos porque lo que se prueba es la
#: LECTURA: hace falta poder desalinear el QR del documento a mano, que es
#: justo lo que los modelos impiden.
DOCUMENTO_CON_QR = """<?xml version="1.0" encoding="UTF-8"?>
<rDE xmlns="http://ekuatia.set.gov.py/sifen/xsd">
  <dVerFor>150</dVerFor>
  <DE Id="{cdc}">
    <dDVId>8</dDVId>
    <dFecFirma>2026-09-10T10:00:00</dFecFirma>
    <dSisFact>1</dSisFact>
    <gTimb><iTiDE>1</iTiDE></gTimb>
    <gDatGralOpe>
      <dFeEmiDE>2026-09-10T09:55:00</dFeEmiDE>
      <gEmis>
        <dRucEm>80012345</dRucEm>
        <dDVEmi>6</dDVEmi>
        <dNomEmi>CONTRIBUYENTE DE PRUEBA S.A.</dNomEmi>
      </gEmis>
    </gDatGralOpe>
    <gDtipDE><gCamItem><dCodInt>1</dCodInt></gCamItem></gDtipDE>
    <gTotSub>
      <dTotGralOpe>36500.00000000</dTotGralOpe>
      <dTotIVA>3318.18181818</dTotIVA>
    </gTotSub>
  </DE>
  <gCamFuFD><dCarQR>{qr}</dCarQR></gCamFuFD>
</rDE>
"""

#: Los parámetros que el QR publica, coherentes con el documento de arriba.
QR_COHERENTE = (
    "https://ekuatia.set.gov.py/consultas/qr?nVersion=150&Id={cdc}"
    "&dFeEmiDE=32303236&dRucRec=80054321&dTotGralOpe=36500.00000000"
    "&dTotIVA=3318.18181818&cItems=1&DigestValue=61626364&IdCSC=0001"
)


def _con_qr(**cambios: str) -> bytes:
    """Arma el documento de arriba, con el QR alterado si se pide."""
    qr = QR_COHERENTE.format(cdc=CDC)
    for clave, valor in cambios.items():
        viejo = f"{clave}=" + qr.split(f"{clave}=")[1].split("&")[0]
        qr = qr.replace(viejo, f"{clave}={valor}")
    # El QR va dentro de un elemento XML: sus "&" tienen que ir escapados, tal
    # como los escribe un emisor real.
    return DOCUMENTO_CON_QR.format(cdc=CDC, qr=qr.replace("&", "&amp;")).encode()


class TestDatosDelDocumento:
    """Lo que se extrae de un documento con todos sus grupos."""

    def test_extrae_lo_que_identifica_al_documento(
        self, verificar: Callable[..., Verificacion]
    ) -> None:
        resultado = verificar(_con_qr(), validar_esquema=False)

        assert resultado.cdc == CDC
        assert resultado.ruc_emisor == "80012345-6"
        assert resultado.razon_social_emisor == "CONTRIBUYENTE DE PRUEBA S.A."
        assert resultado.total == "36500.00000000"
        assert resultado.tipo_documento is not None
        assert resultado.tipo_documento.descripcion == "Factura electrónica"

    def test_el_resumen_no_repite_el_xml(
        self, verificar: Callable[..., Verificacion]
    ) -> None:
        import json

        crudo = _con_qr()
        resumen = verificar(crudo, validar_esquema=False).resumir()

        assert len(json.dumps(resumen, ensure_ascii=False)) < len(crudo)
        assert resumen["emisor"] == "CONTRIBUYENTE DE PRUEBA S.A."

    def test_un_cdc_inventado_no_es_coherente(
        self, verificar: Callable[..., Verificacion]
    ) -> None:
        # El último dígito del CDC es su verificador: cambiarlo lo delata sin
        # necesidad de consultar nada.
        adulterado = DOCUMENTO_CON_QR.format(cdc=CDC[:-1] + "0", qr="").encode()

        resultado = verificar(adulterado, validar_esquema=False)

        assert resultado.cdc_coherente is False
        assert any("CDC" in o for o in resultado.observaciones)


class TestCoherenciaDelQr:
    """Un QR pegado de otro comprobante.

    El ``cHashQR`` no se puede recalcular sin el Código de Seguridad del
    Contribuyente, que sólo conocen el emisor y la DNIT. Pero los parámetros que
    el QR publica sí se pueden contrastar con el documento, y eso ya alcanza
    para detectar el copiado.
    """

    def test_un_qr_que_corresponde(
        self, verificar: Callable[..., Verificacion]
    ) -> None:
        assert verificar(_con_qr(), validar_esquema=False).qr_coherente is True

    def test_un_qr_con_otro_total(self, verificar: Callable[..., Verificacion]) -> None:
        resultado = verificar(
            _con_qr(dTotGralOpe="99999.00000000"), validar_esquema=False
        )

        assert resultado.qr_coherente is False
        assert resultado.confiable is False
        assert any("el QR no corresponde" in o for o in resultado.observaciones)

    def test_un_qr_de_otro_documento(
        self, verificar: Callable[..., Verificacion]
    ) -> None:
        otro = "01800140664044002007120322026082317377733681"
        resultado = verificar(_con_qr(Id=otro), validar_esquema=False)

        assert resultado.qr_coherente is False

    def test_un_documento_sin_qr_no_se_juzga(
        self, verificar: Callable[..., Verificacion]
    ) -> None:
        # Sin QR no hay nada que contrastar. Eso es None, no False: no se pudo
        # comprobar es distinto de no cierra.
        sin_qr = DOCUMENTO_CON_QR.format(cdc=CDC, qr="").replace(
            "<dCarQR></dCarQR>", ""
        )

        assert verificar(sin_qr.encode(), validar_esquema=False).qr_coherente is None


class TestRucDelCertificado:
    """El documento tiene que estar firmado por el contribuyente que declara."""

    def test_un_documento_firmado_por_otro_contribuyente(
        self, firmante: FirmantePkcs12, verificar: Callable[..., Verificacion]
    ) -> None:
        # El certificado de prueba es del RUC 80012345-6. Este documento dice
        # ser de otro: la firma cierra, pero no es de quien dice.
        firmado = _documento_firmado(firmante).replace(
            b"<dDVId>8</dDVId>",
            b"<dDVId>8</dDVId><gDatGralOpe><gEmis><dRucEm>80099999</dRucEm>"
            b"<dDVEmi>1</dDVEmi></gEmis></gDatGralOpe>",
        )

        resultado = verificar(firmado, validar_esquema=False)

        assert resultado.ruc_coincide is False
        assert resultado.confiable is False
        assert any("RUC" in o for o in resultado.observaciones)


class TestRevocacion:
    """La única comprobación que sale a la red, y por eso hay que pedirla.

    Acá no se sale a la red: se sustituye el resultado de la consulta y se
    comprueba qué hace el informe con cada veredicto.
    """

    def test_por_omision_no_se_consulta(
        self, firmante: FirmantePkcs12, verificar: Callable[..., Verificacion]
    ) -> None:
        # Lo importante es que NO haya llamada de red sin pedirlo.
        resultado = verificar(_documento_firmado(firmante), validar_esquema=False)

        assert resultado.revocacion is None
        assert resultado.certificado_revocado is False
        assert "no se consultó" in resultado.resumir()["limite_de_la_verificacion"]

    def test_un_certificado_revocado_no_es_confiable(
        self,
        firmante: FirmantePkcs12,
        anclas_de_prueba: ListaDeConfianza,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from datetime import UTC

        from pysifen.pki.revocacion import EstadoDeRevocacion, ResultadoDeRevocacion

        monkeypatch.setattr(
            "pysifen.lectura.consultar_revocacion",
            lambda *a, **k: ResultadoDeRevocacion(
                EstadoDeRevocacion.REVOCADO,
                fuente="OCSP",
                revocado_el=datetime(2026, 1, 1, tzinfo=UTC),
                razon="KEY_COMPROMISE",
            ),
        )

        resultado = verificar_documento(
            _documento_firmado(firmante),
            lista=anclas_de_prueba,
            validar_esquema=False,
            revocacion=True,
        )

        assert resultado.certificado_revocado is True
        assert resultado.confiable is False
        assert any("revocó el certificado" in o for o in resultado.observaciones)
        assert resultado.resumir()["verificacion"]["revocacion"] == "revocado"
        assert "revocación" in resultado.informe()

    def test_una_consulta_que_no_se_pudo_hacer_se_declara(
        self,
        firmante: FirmantePkcs12,
        anclas_de_prueba: ListaDeConfianza,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # No poder comprobar no es comprobar que está bien: el resumen lo dice.
        from pysifen.pki.revocacion import EstadoDeRevocacion, ResultadoDeRevocacion

        monkeypatch.setattr(
            "pysifen.lectura.consultar_revocacion",
            lambda *a, **k: ResultadoDeRevocacion(
                EstadoDeRevocacion.DESCONOCIDO, motivo="el respondedor no contesta"
            ),
        )

        resultado = verificar_documento(
            _documento_firmado(firmante),
            lista=anclas_de_prueba,
            validar_esquema=False,
            revocacion=True,
        )

        assert resultado.certificado_revocado is False
        assert (
            "no se pudo averiguar" in resultado.resumir()["limite_de_la_verificacion"]
        )
        assert any("no se pudo consultar" in o for o in resultado.observaciones)

    def test_un_lote_tambien_puede_consultarla(
        self,
        firmante: FirmantePkcs12,
        anclas_de_prueba: ListaDeConfianza,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from pysifen.pki.revocacion import EstadoDeRevocacion, ResultadoDeRevocacion

        monkeypatch.setattr(
            "pysifen.lectura.consultar_revocacion",
            lambda *a, **k: ResultadoDeRevocacion(
                EstadoDeRevocacion.VIGENTE, fuente="OCSP"
            ),
        )
        archivo = tmp_path / "documento.xml"
        archivo.write_bytes(_documento_firmado(firmante))

        informes = leer_documentos([archivo], lista=anclas_de_prueba, revocacion=True)

        assert informes[0].revocacion is not None
        assert informes[0].revocacion.estado is EstadoDeRevocacion.VIGENTE
