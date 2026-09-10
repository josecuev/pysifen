"""Pruebas del código de seguridad y del envoltorio de secretos."""

from __future__ import annotations

import copy
import itertools
import pickle

import pytest

from pysifen.exceptions import ValidacionError
from pysifen.security import (
    LARGO_CODIGO_SEGURIDAD,
    Secreto,
    generar_codigo_seguridad,
    validar_codigo_seguridad,
)


class TestGenerarCodigoSeguridad:
    def test_tiene_nueve_digitos(self) -> None:
        codigo = generar_codigo_seguridad()
        assert len(codigo) == LARGO_CODIGO_SEGURIDAD
        assert codigo.isdigit()

    def test_esta_en_el_rango_normado(self) -> None:
        for _ in range(200):
            assert 1 <= int(generar_codigo_seguridad()) <= 999_999_999

    def test_no_repite(self) -> None:
        # El manual exige un valor distinto por documento. Con 500 muestras
        # sobre 10^9 valores, una colisión indicaría un generador degenerado.
        muestras = {generar_codigo_seguridad() for _ in range(500)}
        assert len(muestras) == 500

    def test_no_es_secuencial(self) -> None:
        seguidos = [int(generar_codigo_seguridad()) for _ in range(20)]
        diferencias = {b - a for a, b in itertools.pairwise(seguidos)}
        assert len(diferencias) > 1

    def test_evita_el_numero_de_documento(self) -> None:
        # Se fuerza el caso pidiendo que evite todos los valores menos uno no es
        # práctico; se verifica el contrato con un valor concreto repetido.
        for _ in range(100):
            assert generar_codigo_seguridad(distinto_de="000000001") != "000000001"


class TestValidarCodigoSeguridad:
    def test_acepta_uno_valido(self) -> None:
        assert validar_codigo_seguridad("587326098") == "587326098"

    def test_rellena_con_ceros(self) -> None:
        assert validar_codigo_seguridad("123") == "000000123"

    def test_rechaza_no_numerico(self) -> None:
        with pytest.raises(ValidacionError, match="dígitos"):
            validar_codigo_seguridad("12345678x")

    def test_rechaza_demasiado_largo(self) -> None:
        with pytest.raises(ValidacionError, match="exceder"):
            validar_codigo_seguridad("1234567890")

    def test_rechaza_cero(self) -> None:
        with pytest.raises(ValidacionError, match="positivo"):
            validar_codigo_seguridad("000000000")

    def test_rechaza_igual_al_numero_de_documento(self) -> None:
        with pytest.raises(ValidacionError, match="número de documento"):
            validar_codigo_seguridad("000014528", distinto_de="14528")


class TestSecreto:
    def test_no_muestra_el_valor_en_repr(self) -> None:
        secreto = Secreto("ABCD0000000000000000000000000000", nombre="CSC")
        assert "ABCD" not in repr(secreto)
        assert "ABCD" not in str(secreto)
        assert "ABCD" not in f"{secreto}"
        assert repr(secreto) == "Secreto(CSC=***)"

    def test_revelar_devuelve_el_valor(self) -> None:
        assert Secreto("valor").revelar() == "valor"

    def test_rechaza_vacio(self) -> None:
        with pytest.raises(ValueError, match="vacío"):
            Secreto("")

    def test_compara_por_valor(self) -> None:
        assert Secreto("uno") == Secreto("uno")
        assert Secreto("uno") != Secreto("dos")

    def test_no_compara_contra_texto_plano(self) -> None:
        assert Secreto("uno") != "uno"

    def test_no_se_puede_serializar(self) -> None:
        with pytest.raises(TypeError, match="serializar"):
            pickle.dumps(Secreto("valor", nombre="CSC"))

    def test_no_se_duplica_al_copiar(self) -> None:
        secreto = Secreto("valor")
        assert copy.copy(secreto) is secreto
        assert copy.deepcopy(secreto) is secreto

    def test_largo_sin_revelar(self) -> None:
        assert len(Secreto("abcd")) == 4

    def test_siempre_es_verdadero(self) -> None:
        assert bool(Secreto("x")) is True

    def test_hash_no_depende_del_valor(self) -> None:
        # Si el hash derivara del valor, un diccionario podría filtrarlo.
        assert hash(Secreto("mismo")) != hash(Secreto("mismo"))
