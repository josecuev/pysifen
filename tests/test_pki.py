"""Pruebas de la capa de infraestructura de clave pública."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.serialization import Encoding

from pysifen.enums import TipoContribuyente
from pysifen.exceptions import PkiError
from pysifen.pki import (
    Certificado,
    DatosPrestador,
    PrestadorCualificado,
    PrestadorPorEmisor,
    RegistroDePrestadores,
    TipoCertificado,
)
from pysifen.pki import prestadores as catalogo
from tests.conftest import construir_certificado


class TestLecturaDelCertificado:
    def test_lee_pem(self, certificado_juridica: Certificado) -> None:
        pem = certificado_juridica.x509.public_bytes(Encoding.PEM)
        assert Certificado.desde_pem(pem).ruc == "80012345-6"

    def test_lee_pem_desde_texto(self, certificado_juridica: Certificado) -> None:
        pem = certificado_juridica.x509.public_bytes(Encoding.PEM).decode()
        assert Certificado.desde_pem(pem).ruc == "80012345-6"

    def test_lee_der(self, certificado_juridica: Certificado) -> None:
        der = certificado_juridica.x509.public_bytes(Encoding.DER)
        assert Certificado.desde_der(der).ruc == "80012345-6"

    def test_detecta_pem_o_der_en_archivo(
        self, certificado_juridica: Certificado, tmp_path: Path
    ) -> None:
        pem = tmp_path / "cert.pem"
        pem.write_bytes(certificado_juridica.x509.public_bytes(Encoding.PEM))
        der = tmp_path / "cert.der"
        der.write_bytes(certificado_juridica.x509.public_bytes(Encoding.DER))

        assert Certificado.desde_archivo(pem).ruc == "80012345-6"
        assert Certificado.desde_archivo(der).ruc == "80012345-6"

    def test_rechaza_basura(self) -> None:
        with pytest.raises(PkiError, match="PEM"):
            Certificado.desde_pem(b"esto no es un certificado")

    def test_rechaza_der_invalido(self) -> None:
        with pytest.raises(PkiError, match="DER"):
            Certificado.desde_der(b"\x00\x01\x02")

    def test_avisa_si_el_archivo_no_existe(self, tmp_path: Path) -> None:
        with pytest.raises(PkiError, match="no pude abrir"):
            Certificado.desde_archivo(tmp_path / "no-existe.pem")


class TestExtraccionDelRuc:
    """El apartado 7.5 fija dónde va el RUC según el tipo de titular."""

    def test_persona_juridica_lo_lleva_en_el_subject(
        self, certificado_juridica: Certificado
    ) -> None:
        assert certificado_juridica.ruc == "80012345-6"
        assert (
            certificado_juridica.tipo_contribuyente
            is TipoContribuyente.PERSONA_JURIDICA
        )

    def test_persona_fisica_lo_lleva_en_el_subject_alternative_name(
        self, certificado_fisica: Certificado
    ) -> None:
        assert certificado_fisica.ruc == "80012345-6"
        assert certificado_fisica.tipo_contribuyente is TipoContribuyente.PERSONA_FISICA

    def test_sin_ruc_no_deduce_tipo(self) -> None:
        cert = construir_certificado()
        assert cert.ruc is None
        assert cert.tipo_contribuyente is None

    def test_ignora_un_serial_number_que_no_sea_ruc(self) -> None:
        cert = construir_certificado(ruc_en_subject="CI1234567")
        assert cert.ruc is None

    @pytest.mark.parametrize(
        ("dentro_del_certificado", "esperado"),
        [
            ("RUC80012345-6", "80012345-6"),
            ("RUC1234567-8", "1234567-8"),
            ("RUC1-0", "1-0"),
        ],
    )
    def test_formatos_de_ruc(self, dentro_del_certificado: str, esperado: str) -> None:
        cert = construir_certificado(ruc_en_subject=dentro_del_certificado)
        assert cert.ruc == esperado

    def test_el_subject_tiene_prioridad_sobre_el_san(self) -> None:
        cert = construir_certificado(
            ruc_en_subject="RUC80012345-6", ruc_en_san="RUC99999999-1"
        )
        assert cert.ruc == "80012345-6"


class TestVigencia:
    def test_vigente_ahora(self, certificado_juridica: Certificado) -> None:
        assert certificado_juridica.vigente() is True

    def test_no_vigente_antes_de_empezar(
        self, certificado_juridica: Certificado
    ) -> None:
        antes = certificado_juridica.valido_desde - timedelta(days=1)
        assert certificado_juridica.vigente(antes) is False

    def test_no_vigente_despues_de_vencer(
        self, certificado_juridica: Certificado
    ) -> None:
        despues = certificado_juridica.valido_hasta + timedelta(days=1)
        assert certificado_juridica.vigente(despues) is False

    def test_exige_zona_horaria(self, certificado_juridica: Certificado) -> None:
        with pytest.raises(PkiError, match="zona horaria"):
            certificado_juridica.vigente(datetime(2026, 1, 1))  # noqa: DTZ001


class TestAptitudParaSifen:
    def test_certificado_correcto_no_tiene_problemas(
        self, certificado_juridica: Certificado
    ) -> None:
        assert certificado_juridica.problemas_para_sifen() == []

    def test_detecta_la_falta_de_client_auth(self) -> None:
        cert = construir_certificado(ruc_en_subject="RUC80012345-6", client_auth=False)
        assert cert.sirve_para_autenticacion_tls is False
        problemas = cert.problemas_para_sifen()
        assert any("clientAuth" in p for p in problemas)

    def test_detecta_la_falta_de_ruc(self) -> None:
        problemas = construir_certificado().problemas_para_sifen()
        assert any("RUC" in p for p in problemas)

    def test_detecta_el_vencimiento(self) -> None:
        ahora = datetime.now(UTC)
        cert = construir_certificado(
            ruc_en_subject="RUC80012345-6",
            valido_desde=ahora - timedelta(days=800),
            valido_hasta=ahora - timedelta(days=400),
        )
        problemas = cert.problemas_para_sifen()
        assert any("no está vigente" in p for p in problemas)

    def test_detecta_que_no_habilita_la_firma(self) -> None:
        cert = construir_certificado(
            ruc_en_subject="RUC80012345-6", firma_digital=False
        )
        assert cert.sirve_para_firmar is False
        problemas = cert.problemas_para_sifen()
        assert any("firma digital" in p for p in problemas)

    def test_sin_key_usage_no_se_restringe(self) -> None:
        cert = construir_certificado(
            ruc_en_subject="RUC80012345-6", con_key_usage=False
        )
        assert cert.sirve_para_firmar is True

    @pytest.mark.lento
    def test_detecta_clave_demasiado_corta(self) -> None:
        # El apartado 7.7 exige RSA de 2048 como mínimo por software.
        cert = construir_certificado(ruc_en_subject="RUC80012345-6", bits=1024)
        assert cert.bits_de_clave == 1024
        problemas = cert.problemas_para_sifen()
        assert any("2048" in p for p in problemas)

    def test_informa_los_bits_de_la_clave(
        self, certificado_juridica: Certificado
    ) -> None:
        assert certificado_juridica.bits_de_clave == 2048


class TestDatosDelCertificado:
    def test_titular(self, certificado_juridica: Certificado) -> None:
        assert certificado_juridica.titular == "CONTRIBUYENTE DE PRUEBA S.A."

    def test_numero_de_serie_en_hexadecimal(
        self, certificado_juridica: Certificado
    ) -> None:
        assert int(certificado_juridica.numero_de_serie, 16) > 0

    def test_repr_no_vuelca_el_certificado(
        self, certificado_juridica: Certificado
    ) -> None:
        texto = repr(certificado_juridica)
        assert "80012345-6" in texto
        assert "BEGIN CERTIFICATE" not in texto


class TestTipoCertificado:
    def test_solo_el_f1_tiene_clave_exportable(self) -> None:
        assert TipoCertificado.F1.clave_exportable is True
        assert TipoCertificado.F2.clave_exportable is False
        assert TipoCertificado.F3.clave_exportable is False

    def test_todos_tienen_descripcion(self) -> None:
        for tipo in TipoCertificado:
            assert tipo.descripcion


class TestCatalogoDePrestadores:
    def test_hay_siete_habilitados(self) -> None:
        # Registro de la Autoridad Certificadora Raíz al 10/09/2026.
        assert len(catalogo.todos()) == 7

    def test_los_identificadores_no_se_repiten(self) -> None:
        identificadores = [p.datos.identificador for p in catalogo.todos()]
        assert len(identificadores) == len(set(identificadores))

    def test_identificaciones_solo_emite_f2(self) -> None:
        assert catalogo.identificaciones().datos.tipos == frozenset(
            {TipoCertificado.F2}
        )

    def test_itti_no_emite_f2(self) -> None:
        assert TipoCertificado.F2 not in catalogo.itti().datos.tipos

    def test_todos_cumplen_el_protocolo(self) -> None:
        for prestador in catalogo.todos():
            assert isinstance(prestador, PrestadorCualificado)


class TestReconocimientoDelEmisor:
    @pytest.mark.parametrize(
        ("emisor", "identificador"),
        [
            ("DOCUMENTA S.A.", "documenta"),
            ("Documenta Certificacion Digital", "documenta"),
            ("CODE100 S.A.", "code100"),
            ("VIT S.A.", "vit"),
            ("CONFIRMA S.A.", "confirma"),
            ("ITTI S.A.E.C.A.", "itti"),
            ("Ministerio del Interior - Policia Nacional", "identificaciones"),
            ("SOS Tecnologia y Gestion de Informacion", "sos"),
        ],
    )
    def test_identifica_al_prestador(self, emisor: str, identificador: str) -> None:
        registro = RegistroDePrestadores(catalogo.todos())
        cert = construir_certificado(ruc_en_subject="RUC80012345-6", emisor=emisor)
        encontrado = registro.identificar(cert)
        assert encontrado is not None
        assert encontrado.datos.identificador == identificador

    def test_la_comparacion_ignora_acentos_y_mayusculas(self) -> None:
        registro = RegistroDePrestadores(catalogo.todos())
        cert = construir_certificado(emisor="documenta certificación digital")
        encontrado = registro.identificar(cert)
        assert encontrado is not None
        assert encontrado.datos.identificador == "documenta"

    def test_un_emisor_desconocido_devuelve_none(self) -> None:
        registro = RegistroDePrestadores(catalogo.todos())
        cert = construir_certificado(emisor="CERTIFICADORA IMAGINARIA S.A.")
        assert registro.identificar(cert) is None


class TestRegistro:
    def test_arranca_vacio(self) -> None:
        assert len(RegistroDePrestadores()) == 0

    def test_registra_y_recupera(self) -> None:
        registro = RegistroDePrestadores()
        registro.registrar(catalogo.vit())
        assert len(registro) == 1
        assert "vit" in registro
        assert registro.obtener("vit") is not None

    def test_obtener_uno_que_no_esta_devuelve_none(self) -> None:
        assert RegistroDePrestadores().obtener("inexistente") is None

    def test_rechaza_identificadores_duplicados(self) -> None:
        registro = RegistroDePrestadores([catalogo.vit()])
        with pytest.raises(ValueError, match="ya está registrado"):
            registro.registrar(catalogo.vit())

    def test_es_iterable(self) -> None:
        registro = RegistroDePrestadores(catalogo.todos())
        assert len(list(registro)) == 7

    def test_repr_dice_cuantos_hay(self) -> None:
        assert "7 prestadores" in repr(RegistroDePrestadores(catalogo.todos()))

    def test_descubre_por_entry_points(self) -> None:
        # Es el mecanismo de extensión: los siete se declaran en el
        # pyproject.toml y se descubren sin que el núcleo los nombre.
        registro = RegistroDePrestadores.desde_entry_points()
        assert len(registro) >= 7
        assert "documenta" in registro

    def test_se_puede_sumar_un_prestador_de_terceros(self) -> None:
        # Principio abierto/cerrado: no hace falta tocar el núcleo.
        nuevo = PrestadorPorEmisor(
            datos=DatosPrestador(
                identificador="futuro",
                nombre="CERTIFICADORA FUTURA S.A.",
                resolucion="999/2027",
                tipos=frozenset({TipoCertificado.F3}),
                sitio="https://ejemplo.com.py",
            ),
            patrones=("CERTIFICADORA FUTURA",),
        )
        registro = RegistroDePrestadores(catalogo.todos())
        registro.registrar(nuevo)

        cert = construir_certificado(emisor="CERTIFICADORA FUTURA S.A.")
        encontrado = registro.identificar(cert)
        assert encontrado is not None
        assert encontrado.datos.identificador == "futuro"

    def test_un_prestador_sin_patrones_no_reconoce_nada(self) -> None:
        vacio = PrestadorPorEmisor(
            datos=DatosPrestador(
                identificador="vacio",
                nombre="SIN PATRONES",
                resolucion="0/2026",
                tipos=frozenset({TipoCertificado.F1}),
                sitio="https://ejemplo.com.py",
            )
        )
        assert vacio.emitio(construir_certificado(emisor="CUALQUIERA")) is False
