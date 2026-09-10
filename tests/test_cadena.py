"""Pruebas de la cadena de confianza.

Lo que se prueba acá es la diferencia entre *decir* y *ser*: un certificado que
declara "DOCUMENTA S.A." en su campo de emisor y uno que DOCUMENTA firmó de
verdad se parecen en todo salvo en lo único que importa.

La jerarquía de prueba —raíz, autoridad intermedia y titular, cada uno con su
clave— la arma ``conftest``. Contra la Lista de Confianza real sólo se prueban
las propiedades que tiene que cumplir, nunca un documento de prueba: si un
certificado de mentira validara contra la lista real, la lista real no serviría.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509

from pysifen.exceptions import PkiError
from pysifen.pki.cadena import (
    SERVICIOS_TRIBUTARIOS,
    Autoridad,
    ListaDeConfianza,
    lista_de_confianza,
    validar_cadena,
)
from tests.conftest import (
    construir_ca,
    construir_certificado,
    jerarquia_de_prueba,
    lista_de_prueba,
)


class TestCadenaQueCierra:
    """El camino feliz: el certificado llega hasta la raíz."""

    def test_llega_hasta_la_raiz(self) -> None:
        _, intermedia = jerarquia_de_prueba()
        titular = construir_certificado(
            ruc_en_subject="RUC80012345-6", firmada_por=intermedia
        )

        resultado = validar_cadena(titular, lista=lista_de_prueba())

        assert resultado.valida
        assert resultado.cadena == (
            "CONTRIBUYENTE DE PRUEBA S.A.",
            "CA-PRESTADOR DE PRUEBA S.A.",
            "Autoridad Certificadora Raíz de Prueba",
        )
        assert resultado.motivo is None

    def test_el_prestador_es_el_de_la_lista_no_el_del_certificado(self) -> None:
        # El certificado no dice en ningún lado "PRESTADOR DE PRUEBA S.A.": ese
        # nombre sale de la lista de confianza, que es la fuente autoritativa.
        _, intermedia = jerarquia_de_prueba()
        titular = construir_certificado(
            ruc_en_subject="RUC80012345-6", firmada_por=intermedia
        )

        resultado = validar_cadena(titular, lista=lista_de_prueba())

        assert resultado.prestador == "PRESTADOR DE PRUEBA S.A."
        assert resultado.habilitado_al_firmar is True


class TestCadenaQueNoCierra:
    """Los casos que la validación tiene que rechazar."""

    def test_un_autofirmado_que_dice_ser_de_un_prestador(self) -> None:
        # El ataque que esto cierra. El campo de emisor es texto libre: se puede
        # escribir "DOCUMENTA S.A." sin que DOCUMENTA intervenga. Lo que no se
        # puede falsificar es su firma sobre el certificado.
        impostor = construir_certificado(
            ruc_en_subject="RUC80012345-6", emisor="CA-PRESTADOR DE PRUEBA S.A."
        )

        resultado = validar_cadena(impostor, lista=lista_de_prueba())

        assert resultado.valida is False
        assert resultado.prestador is None
        assert resultado.motivo is not None
        assert "no encontré" in resultado.motivo

    def test_un_prestador_al_que_le_retiraron_la_habilitacion(self) -> None:
        _, intermedia = jerarquia_de_prueba()
        titular = construir_certificado(
            ruc_en_subject="RUC80012345-6", firmada_por=intermedia
        )

        resultado = validar_cadena(
            titular, lista=lista_de_prueba(estado_del_prestador="withdrawn")
        )

        assert resultado.valida is False
        assert resultado.habilitado_al_firmar is False
        assert resultado.motivo is not None
        assert "withdrawn" in resultado.motivo

    def test_una_autoridad_que_no_estaba_vigente_al_firmar(self) -> None:
        ahora = datetime.now(UTC)
        raiz = construir_ca("Raíz Vencida", rol="raiz-vencida")
        vencida = construir_ca(
            "CA Vencida",
            firmada_por=raiz,
            rol="ca-vencida",
            valido_desde=ahora - timedelta(days=900),
            valido_hasta=ahora - timedelta(days=500),
        )
        titular = construir_certificado(
            ruc_en_subject="RUC80012345-6", firmada_por=vencida
        )
        lista = lista_de_prueba()
        anclas = ListaDeConfianza(
            [
                *lista,
                *_como_autoridades(raiz.certificado, vencida.certificado),
            ]
        )

        resultado = validar_cadena(titular, lista=anclas)

        assert resultado.valida is False
        assert resultado.motivo is not None
        assert "vigente" in resultado.motivo

    def test_la_vigencia_se_evalua_a_la_fecha_de_la_firma(self) -> None:
        # Una autoridad que venció el mes pasado no invalida lo que firmó
        # cuando estaba vigente. Es el criterio del apartado 7.8 del manual.
        ahora = datetime.now(UTC)
        raiz = construir_ca(
            "Raíz de Ayer",
            rol="raiz-ayer",
            valido_desde=ahora - timedelta(days=3650),
        )
        ca = construir_ca(
            "CA de Ayer",
            firmada_por=raiz,
            rol="ca-ayer",
            valido_desde=ahora - timedelta(days=900),
            valido_hasta=ahora - timedelta(days=500),
        )
        titular = construir_certificado(ruc_en_subject="RUC80012345-6", firmada_por=ca)
        anclas = ListaDeConfianza(
            list(_como_autoridades(raiz.certificado, ca.certificado))
        )

        assert validar_cadena(titular, lista=anclas).valida is False
        entonces = ahora - timedelta(days=600)
        assert validar_cadena(titular, lista=anclas, momento=entonces).valida


class TestAlcanceTributario:
    """Sólo la jerarquía que firma documentos tributarios sirve acá."""

    def test_una_jerarquia_ajena_no_se_acepta(self) -> None:
        # La lista trae también la AC RAIZ MITIC, que es la de firma de
        # funcionarios públicos: otra raíz y otro propósito. Un certificado de
        # esa jerarquía encadena perfecto contra su raíz, y eso no habilita a
        # nadie a facturar.
        _, intermedia = jerarquia_de_prueba()
        titular = construir_certificado(
            ruc_en_subject="RUC80012345-6", firmada_por=intermedia
        )

        resultado = validar_cadena(
            titular, lista=lista_de_prueba(tipo_de_servicio="PKC")
        )

        assert resultado.valida is False

    def test_se_puede_ampliar_el_alcance_a_proposito(self) -> None:
        # Acotar por omisión no es cerrar la puerta: quien necesite validar otra
        # jerarquía lo pide explícitamente, y queda escrito en su código.
        _, intermedia = jerarquia_de_prueba()
        titular = construir_certificado(
            ruc_en_subject="RUC80012345-6", firmada_por=intermedia
        )

        resultado = validar_cadena(
            titular,
            lista=lista_de_prueba(tipo_de_servicio="PKC"),
            servicios=frozenset({"PKC", "NationalRootCA-QC"}),
        )

        assert resultado.valida


class TestListaOficial:
    """Propiedades que la Lista de Confianza del MIC tiene que cumplir."""

    def test_trae_a_los_prestadores_cualificados(self) -> None:
        lista = lista_de_confianza()
        prestadores = {a.prestador for a in lista if a.habilitada}

        assert {"Documenta SA", "ITTI S.A.E.C.A", "CODE 100 S.A."} <= prestadores

    def test_tiene_una_sola_raiz_para_documentos_tributarios(self) -> None:
        # La lista trae dos raíces nacionales. La del SIFEN es una sola.
        raices = {
            a.certificado.subject.rfc4514_string()
            for a in lista_de_confianza()
            if a.es_raiz and a.tipo_de_servicio in SERVICIOS_TRIBUTARIOS
        }

        assert len(raices) == 1
        assert "Autoridad Certificadora Ra" in next(iter(raices))

    def test_deja_afuera_la_jerarquia_de_funcionarios_publicos(self) -> None:
        de_mitic = [a for a in lista_de_confianza() if "MITIC" in a.prestador.upper()]

        assert de_mitic, "la lista trae la jerarquía del MITIC"
        assert all(a.tipo_de_servicio not in SERVICIOS_TRIBUTARIOS for a in de_mitic)

    def test_se_lee_una_sola_vez(self) -> None:
        assert lista_de_confianza() is lista_de_confianza()

    def test_un_archivo_que_no_existe_se_reporta(self, tmp_path: Path) -> None:
        with pytest.raises(PkiError, match="no pude leer"):
            ListaDeConfianza.desde_archivo(tmp_path / "no-existe.xml")

    def test_un_archivo_sin_autoridades_se_reporta(self, tmp_path: Path) -> None:
        vacio = tmp_path / "vacia.xml"
        vacio.write_text("<TrustServiceStatusList/>", encoding="utf-8")
        with pytest.raises(PkiError, match="ninguna autoridad"):
            ListaDeConfianza.desde_archivo(vacio)

    def test_se_puede_inspeccionar(self) -> None:
        lista = lista_de_confianza()

        assert len(lista) == len(list(lista))
        assert "autoridades" in repr(lista)


def _como_autoridades(
    raiz: x509.Certificate, intermedia: x509.Certificate
) -> list[Autoridad]:
    """Envuelve dos certificados como autoridades habilitadas de la lista."""
    return [
        Autoridad(
            prestador="Ministerio de Prueba",
            certificado=raiz,
            estado="recognisedatnationallevel",
            tipo_de_servicio="NationalRootCA-QC",
        ),
        Autoridad(
            prestador="PRESTADOR VENCIDO S.A.",
            certificado=intermedia,
            estado="granted",
            tipo_de_servicio="QC",
        ),
    ]
