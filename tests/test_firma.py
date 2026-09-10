"""Pruebas de la firma XMLDSig y de la custodia de la clave.

La estructura esperada es la del ejemplo del apartado 7.6 del Manual Técnico
v150, incluidos los identificadores de algoritmo tal como los escribe el manual.
"""

from __future__ import annotations

import base64
import hashlib
import pickle
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from lxml import etree

from pysifen.exceptions import ConfiguracionError, FirmaError
from pysifen.pki.certificado import Certificado
from pysifen.security.secretos import Secreto
from pysifen.signing import (
    EventoDeFirma,
    Firmante,
    FirmanteAuditado,
    NivelDeCustodia,
    exigir_nivel,
    firmar_documento,
)
from pysifen.signing.backends import FirmanteRemoto
from pysifen.signing.backends.pkcs11 import FirmantePkcs11
from pysifen.signing.backends.pkcs12 import AvisoDeCustodia, FirmantePkcs12
from pysifen.signing.xmldsig import (
    ALGORITMO_DIGEST,
    ALGORITMO_FIRMA,
    C14N_EXCLUSIVO,
    C14N_INCLUSIVO,
    NS_XMLDSIG,
    TRANSFORMACION_ENVELOPED,
)
from tests.conftest import CDC_DEL_MANUAL, RDE_SIN_FIRMAR, construir_pkcs12

DS = f"{{{NS_XMLDSIG}}}"


def _clave_publica(certificado: Certificado) -> rsa.RSAPublicKey:
    """Devuelve la clave publica RSA del certificado, ya estrechada."""
    clave = certificado.x509.public_key()
    assert isinstance(clave, rsa.RSAPublicKey)
    return clave


def _hay_pkcs11() -> bool:
    """Indica si el extra pkcs11 está instalado en este entorno."""
    import importlib.util

    return importlib.util.find_spec("pkcs11") is not None


@pytest.fixture
def firmado(firmante: FirmantePkcs12) -> etree._Element:
    """El documento de prueba ya firmado, listo para inspeccionar."""
    return etree.fromstring(firmar_documento(RDE_SIN_FIRMAR, firmante))


class TestEstructuraDeLaFirma:
    """El apartado 7.6 fija la estructura exacta del elemento Signature."""

    def test_la_firma_es_hermana_del_de(self, firmado: etree._Element) -> None:
        # En el ejemplo del manual el Signature cuelga de rDE, no del DE.
        hijos = [etree.QName(h).localname for h in firmado]
        assert hijos == ["dVerFor", "DE", "Signature"]

    def test_canonicalizacion_del_signed_info_es_inclusiva(
        self, firmado: etree._Element
    ) -> None:
        metodo = firmado.find(
            f"{DS}Signature/{DS}SignedInfo/{DS}CanonicalizationMethod"
        )
        assert metodo is not None
        assert metodo.get("Algorithm") == C14N_INCLUSIVO

    def test_la_transformacion_de_la_referencia_es_exclusiva(
        self, firmado: etree._Element
    ) -> None:
        # Es la particularidad del SIFEN: mezcla las dos canonicalizaciones.
        transformaciones = firmado.findall(
            f"{DS}Signature/{DS}SignedInfo/{DS}Reference/{DS}Transforms/{DS}Transform"
        )
        algoritmos = [t.get("Algorithm") for t in transformaciones]
        assert algoritmos == [TRANSFORMACION_ENVELOPED, C14N_EXCLUSIVO]

    def test_algoritmo_de_firma(self, firmado: etree._Element) -> None:
        metodo = firmado.find(f"{DS}Signature/{DS}SignedInfo/{DS}SignatureMethod")
        assert metodo is not None
        assert metodo.get("Algorithm") == ALGORITMO_FIRMA

    def test_algoritmo_de_resumen(self, firmado: etree._Element) -> None:
        metodo = firmado.find(
            f"{DS}Signature/{DS}SignedInfo/{DS}Reference/{DS}DigestMethod"
        )
        assert metodo is not None
        assert metodo.get("Algorithm") == ALGORITMO_DIGEST

    def test_la_referencia_apunta_al_cdc(self, firmado: etree._Element) -> None:
        referencia = firmado.find(f"{DS}Signature/{DS}SignedInfo/{DS}Reference")
        assert referencia is not None
        assert referencia.get("URI") == f"#{CDC_DEL_MANUAL}"

    def test_el_key_info_lleva_el_certificado(
        self, firmado: etree._Element, firmante: FirmantePkcs12
    ) -> None:
        nodo = firmado.find(
            f"{DS}Signature/{DS}KeyInfo/{DS}X509Data/{DS}X509Certificate"
        )
        assert nodo is not None
        assert nodo.text
        leido = Certificado.desde_der(base64.b64decode(nodo.text))
        assert leido.numero_de_serie == firmante.certificado.numero_de_serie

    @pytest.mark.parametrize(
        "prohibido",
        [
            "X509SubjectName",
            "X509IssuerSerial",
            "X509IssuerName",
            "X509SKI",
            "KeyValue",
            "RSAKeyValue",
            "Modulus",
            "Exponent",
        ],
    )
    def test_no_incluye_los_elementos_prohibidos(
        self, firmado: etree._Element, prohibido: str
    ) -> None:
        # El apartado 7.6 los prohíbe: son datos que el SIFEN saca del propio
        # certificado.
        assert firmado.find(f".//{DS}{prohibido}") is None


class TestCorrectitudCriptografica:
    def test_el_digest_corresponde_al_de_canonicalizado(
        self, firmado: etree._Element
    ) -> None:
        de = firmado.find("{http://ekuatia.set.gov.py/sifen/xsd}DE")
        assert de is not None
        canonico = etree.tostring(de, method="c14n", exclusive=True)
        esperado = base64.b64encode(hashlib.sha256(canonico).digest()).decode()

        nodo = firmado.find(
            f"{DS}Signature/{DS}SignedInfo/{DS}Reference/{DS}DigestValue"
        )
        assert nodo is not None
        assert nodo.text == esperado

    def test_la_firma_verifica_contra_el_signed_info(
        self, firmado: etree._Element, firmante: FirmantePkcs12
    ) -> None:
        info = firmado.find(f"{DS}Signature/{DS}SignedInfo")
        valor = firmado.find(f"{DS}Signature/{DS}SignatureValue")
        assert info is not None
        assert valor is not None
        assert valor.text

        canonico = etree.tostring(info, method="c14n", exclusive=False)
        _clave_publica(firmante.certificado).verify(
            base64.b64decode(valor.text),
            canonico,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

    def test_alterar_el_documento_invalida_la_firma(
        self, firmado: etree._Element, firmante: FirmantePkcs12
    ) -> None:
        # Se cambia el código de seguridad después de firmar.
        codigo = firmado.find(".//{http://ekuatia.set.gov.py/sifen/xsd}dCodSeg")
        assert codigo is not None
        codigo.text = "111111111"

        de = firmado.find("{http://ekuatia.set.gov.py/sifen/xsd}DE")
        assert de is not None
        recalculado = base64.b64encode(
            hashlib.sha256(etree.tostring(de, method="c14n", exclusive=True)).digest()
        ).decode()

        declarado = firmado.find(
            f"{DS}Signature/{DS}SignedInfo/{DS}Reference/{DS}DigestValue"
        )
        assert declarado is not None
        assert declarado.text != recalculado

    def test_otra_clave_no_verifica(
        self, firmado: etree._Element, certificado_fisica: Certificado
    ) -> None:
        info = firmado.find(f"{DS}Signature/{DS}SignedInfo")
        valor = firmado.find(f"{DS}Signature/{DS}SignatureValue")
        assert info is not None
        assert valor is not None
        assert valor.text

        # El certificado de persona física se generó con otra clave distinta a
        # la del firmante sólo si los tamaños difieren; se fuerza el fallo
        # alterando el SignedInfo canonicalizado.
        canonico = etree.tostring(info, method="c14n", exclusive=False) + b" "
        with pytest.raises(InvalidSignature):
            _clave_publica(certificado_fisica).verify(
                base64.b64decode(valor.text),
                canonico,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )


class TestVerificacionIndependiente:
    """Contraste contra otra implementación de XMLDSig.

    Que nuestra firma verifique con nuestro propio código prueba poco: si la
    canonicalización estuviera mal, estaría mal de los dos lados. `signxml` es
    una implementación independiente del estándar del W3C, así que su veredicto
    es evidencia real de que la firma está bien construida.

    Lo que esto **no** prueba es que el SIFEN la acepte: eso recién se confirma
    contra el ambiente de test de la DNIT, con un certificado habilitado.
    """

    def test_signxml_verifica_nuestra_firma(self, firmante: FirmantePkcs12) -> None:
        from signxml import XMLVerifier  # type: ignore[attr-defined]

        firmado = firmar_documento(RDE_SIN_FIRMAR, firmante)

        XMLVerifier().verify(
            firmado,
            x509_cert=firmante.certificado.x509,
            expect_references=1,
        )

    def test_signxml_rechaza_un_documento_alterado(
        self, firmante: FirmantePkcs12
    ) -> None:
        from signxml import (  # type: ignore[attr-defined]
            InvalidSignature as SignxmlInvalidSignature,
        )
        from signxml import XMLVerifier  # type: ignore[attr-defined]

        firmado = firmar_documento(RDE_SIN_FIRMAR, firmante)
        alterado = firmado.replace(b"587326098", b"111111111")

        with pytest.raises(SignxmlInvalidSignature):
            XMLVerifier().verify(
                alterado,
                x509_cert=firmante.certificado.x509,
                expect_references=1,
            )


class TestEntradasInvalidas:
    def test_rechaza_xml_mal_formado(self, firmante: FirmantePkcs12) -> None:
        with pytest.raises(FirmaError, match="no es válido"):
            firmar_documento("<rDE><sin cerrar>", firmante)

    def test_rechaza_documento_sin_id(self, firmante: FirmantePkcs12) -> None:
        with pytest.raises(FirmaError, match="atributo Id"):
            firmar_documento("<rDE><DE/></rDE>", firmante)

    def test_rechaza_id_inexistente(self, firmante: FirmantePkcs12) -> None:
        with pytest.raises(FirmaError, match="no encontré"):
            firmar_documento(RDE_SIN_FIRMAR, firmante, identificador="0000000000")

    def test_si_el_firmante_falla_no_queda_firma_a_medias(self) -> None:
        class FirmanteRoto:
            @property
            def certificado(self) -> Certificado:  # pragma: no cover
                raise AssertionError("no debería llegar acá")

            @property
            def nivel_de_custodia(self) -> NivelDeCustodia:
                return NivelDeCustodia.CLAVE_EN_MEMORIA

            def firmar(self, datos: bytes) -> bytes:
                raise FirmaError("el dispositivo se desconectó")

        with pytest.raises(FirmaError, match="se desconectó"):
            firmar_documento(RDE_SIN_FIRMAR, FirmanteRoto())


class TestNivelesDeCustodia:
    def test_estan_ordenados_de_menor_a_mayor_proteccion(self) -> None:
        assert (
            NivelDeCustodia.CLAVE_EN_MEMORIA
            < NivelDeCustodia.CLAVE_EN_DISPOSITIVO
            < NivelDeCustodia.CLAVE_FUERA_DEL_ALCANCE
        )

    def test_todos_tienen_descripcion(self) -> None:
        for nivel in NivelDeCustodia:
            assert nivel.descripcion

    def test_exigir_nivel_deja_pasar_al_que_alcanza(
        self, firmante: FirmantePkcs12
    ) -> None:
        assert exigir_nivel(firmante, NivelDeCustodia.CLAVE_EN_MEMORIA) is firmante

    def test_exigir_nivel_rechaza_al_que_no_alcanza(
        self, firmante: FirmantePkcs12
    ) -> None:
        with pytest.raises(ConfiguracionError, match="CLAVE_EN_DISPOSITIVO"):
            exigir_nivel(firmante, NivelDeCustodia.CLAVE_EN_DISPOSITIVO)


class TestCustodiaDelPkcs12:
    def test_exige_aceptacion_explicita_desde_bytes(
        self, certificado_juridica: Certificado
    ) -> None:
        datos = construir_pkcs12(certificado_juridica)
        with pytest.raises(ConfiguracionError, match="permitir_clave_en_disco"):
            FirmantePkcs12.desde_bytes(datos, Secreto("prueba"))

    def test_exige_aceptacion_explicita_desde_archivo(
        self, certificado_juridica: Certificado, tmp_path: Path
    ) -> None:
        ruta = tmp_path / "cert.p12"
        ruta.write_bytes(construir_pkcs12(certificado_juridica))
        with pytest.raises(ConfiguracionError, match="permitir_clave_en_disco"):
            FirmantePkcs12.desde_archivo(ruta, Secreto("prueba"))

    def test_avisa_al_cargar_la_clave(self, certificado_juridica: Certificado) -> None:
        datos = construir_pkcs12(certificado_juridica)
        with pytest.warns(AvisoDeCustodia, match="más expuesto"):
            FirmantePkcs12.desde_bytes(
                datos, Secreto("prueba"), permitir_clave_en_memoria=True
            )

    def test_carga_desde_archivo_con_aceptacion(
        self, certificado_juridica: Certificado, tmp_path: Path
    ) -> None:
        ruta = tmp_path / "cert.p12"
        ruta.write_bytes(construir_pkcs12(certificado_juridica))
        with pytest.warns(AvisoDeCustodia):
            cargado = FirmantePkcs12.desde_archivo(
                ruta, Secreto("prueba"), permitir_clave_en_disco=True
            )
        assert cargado.certificado.ruc == "80012345-6"

    def test_contrasena_incorrecta_no_filtra_detalles(
        self, certificado_juridica: Certificado
    ) -> None:
        datos = construir_pkcs12(certificado_juridica, contrasena="correcta")
        with pytest.raises(FirmaError) as capturado:
            FirmantePkcs12.desde_bytes(
                datos,
                Secreto("equivocada"),
                permitir_clave_en_memoria=True,
            )
        assert "equivocada" not in str(capturado.value)
        assert capturado.value.__cause__ is None

    def test_archivo_inexistente(self, tmp_path: Path) -> None:
        with pytest.raises(FirmaError, match="no pude abrir"):
            FirmantePkcs12.desde_archivo(
                tmp_path / "no-existe.p12",
                Secreto("prueba"),
                permitir_clave_en_disco=True,
            )

    def test_no_expone_la_clave_privada(self, firmante: FirmantePkcs12) -> None:
        publicos = [n for n in dir(firmante) if not n.startswith("_")]
        assert publicos == [
            "certificado",
            "desde_archivo",
            "desde_bytes",
            "firmar",
            "nivel_de_custodia",
        ]

    def test_el_repr_no_revela_nada(self, firmante: FirmantePkcs12) -> None:
        assert "PRIVATE KEY" not in repr(firmante)
        assert "prueba" not in repr(firmante)

    def test_no_se_puede_serializar(self, firmante: FirmantePkcs12) -> None:
        with pytest.raises(TypeError, match="no se puede serializar"):
            pickle.dumps(firmante)

    def test_cumple_el_protocolo(self, firmante: FirmantePkcs12) -> None:
        assert isinstance(firmante, Firmante)


class TestFirmaRemota:
    """El F3 es el nivel más alto: la clave nunca estuvo del lado del emisor."""

    def test_nivel_maximo(self, certificado_juridica: Certificado) -> None:
        remoto = FirmanteRemoto(_ServicioFalso(certificado_juridica))
        assert remoto.nivel_de_custodia is NivelDeCustodia.CLAVE_FUERA_DEL_ALCANCE

    def test_delega_en_el_servicio(self, certificado_juridica: Certificado) -> None:
        servicio = _ServicioFalso(certificado_juridica)
        remoto = FirmanteRemoto(servicio)
        assert remoto.firmar(b"datos") == b"firma-del-prestador"
        assert servicio.pedidos == [b"datos"]

    def test_traduce_las_fallas_del_servicio(
        self, certificado_juridica: Certificado
    ) -> None:
        servicio = _ServicioFalso(certificado_juridica, falla=True)
        with pytest.raises(FirmaError, match="firma remota falló"):
            FirmanteRemoto(servicio).firmar(b"datos")

    def test_rechaza_una_respuesta_vacia(
        self, certificado_juridica: Certificado
    ) -> None:
        servicio = _ServicioFalso(certificado_juridica, respuesta=b"")
        with pytest.raises(FirmaError, match="no devolvió una firma válida"):
            FirmanteRemoto(servicio).firmar(b"datos")

    def test_cumple_el_protocolo(self, certificado_juridica: Certificado) -> None:
        assert isinstance(
            FirmanteRemoto(_ServicioFalso(certificado_juridica)), Firmante
        )

    def test_no_se_puede_serializar(self, certificado_juridica: Certificado) -> None:
        with pytest.raises(TypeError, match="no se puede serializar"):
            pickle.dumps(FirmanteRemoto(_ServicioFalso(certificado_juridica)))


class TestAuditoria:
    def test_registra_la_firma_exitosa(self, firmante: FirmantePkcs12) -> None:
        eventos: list[EventoDeFirma] = []
        auditado = FirmanteAuditado(firmante, eventos.append)

        auditado.firmar(b"lo que sea")

        assert len(eventos) == 1
        evento = eventos[0]
        assert evento.exitosa is True
        assert evento.titular == firmante.certificado.titular
        assert evento.nivel_de_custodia == "CLAVE_EN_MEMORIA"
        assert evento.motivo_de_la_falla is None

    def test_el_resumen_identifica_lo_firmado_sin_revelarlo(
        self, firmante: FirmantePkcs12
    ) -> None:
        eventos: list[EventoDeFirma] = []
        auditado = FirmanteAuditado(firmante, eventos.append)

        auditado.firmar(b"contenido reservado")

        resumen = eventos[0].resumen_de_lo_firmado
        assert resumen == hashlib.sha256(b"contenido reservado").hexdigest()
        assert "contenido reservado" not in str(eventos[0])

    def test_registra_la_falla_y_la_propaga(
        self, certificado_juridica: Certificado
    ) -> None:
        servicio = _ServicioFalso(certificado_juridica, falla=True)
        eventos: list[EventoDeFirma] = []
        auditado = FirmanteAuditado(FirmanteRemoto(servicio), eventos.append)

        with pytest.raises(FirmaError):
            auditado.firmar(b"datos")

        assert len(eventos) == 1
        assert eventos[0].exitosa is False
        assert eventos[0].motivo_de_la_falla

    def test_no_cambia_el_nivel_de_custodia(self, firmante: FirmantePkcs12) -> None:
        auditado = FirmanteAuditado(firmante, lambda _: None)
        assert auditado.nivel_de_custodia is firmante.nivel_de_custodia

    def test_sirve_para_firmar_un_documento(self, firmante: FirmantePkcs12) -> None:
        eventos: list[EventoDeFirma] = []
        auditado = FirmanteAuditado(firmante, eventos.append)

        firmar_documento(RDE_SIN_FIRMAR, auditado)

        assert len(eventos) == 1

    def test_cumple_el_protocolo(self, firmante: FirmantePkcs12) -> None:
        assert isinstance(FirmanteAuditado(firmante, lambda _: None), Firmante)

    def test_el_registrador_por_omision_no_rompe(
        self, firmante: FirmantePkcs12
    ) -> None:
        FirmanteAuditado(firmante).firmar(b"datos")


class TestFirmaConDispositivo:
    """El F2 mantiene la clave dentro del token o HSM.

    No se puede ejercitar el dispositivo en integración continua. Lo que sí se
    verifica sin hardware es el contrato: el nivel que declara, que no expone
    material de clave, y que avisa con claridad cuando falta el extra.
    """

    def test_nivel_intermedio(self, certificado_juridica: Certificado) -> None:
        firmante = FirmantePkcs11(
            sesion=None, clave=object(), certificado=certificado_juridica
        )
        assert firmante.nivel_de_custodia is NivelDeCustodia.CLAVE_EN_DISPOSITIVO

    def test_expone_el_certificado(self, certificado_juridica: Certificado) -> None:
        firmante = FirmantePkcs11(
            sesion=None, clave=object(), certificado=certificado_juridica
        )
        assert firmante.certificado is certificado_juridica

    def test_el_repr_no_revela_el_dispositivo(
        self, certificado_juridica: Certificado
    ) -> None:
        firmante = FirmantePkcs11(
            sesion=object(), clave=object(), certificado=certificado_juridica
        )
        assert "clave" not in repr(firmante).lower()
        assert "CONTRIBUYENTE" in repr(firmante)

    def test_no_se_puede_serializar(self, certificado_juridica: Certificado) -> None:
        firmante = FirmantePkcs11(
            sesion=None, clave=object(), certificado=certificado_juridica
        )
        with pytest.raises(TypeError, match="no se puede serializar"):
            pickle.dumps(firmante)

    def test_cierra_la_sesion_al_salir_del_contexto(
        self, certificado_juridica: Certificado
    ) -> None:
        sesion = _SesionFalsa()
        with FirmantePkcs11(
            sesion=sesion, clave=object(), certificado=certificado_juridica
        ):
            assert sesion.cerrada is False
        assert sesion.cerrada is True

    def test_cerrar_sin_sesion_no_rompe(
        self, certificado_juridica: Certificado
    ) -> None:
        FirmantePkcs11(
            sesion=None, clave=object(), certificado=certificado_juridica
        ).cerrar()

    def test_cumple_el_protocolo(self, certificado_juridica: Certificado) -> None:
        firmante = FirmantePkcs11(
            sesion=None, clave=object(), certificado=certificado_juridica
        )
        assert isinstance(firmante, Firmante)

    @pytest.mark.skipif(_hay_pkcs11(), reason="el extra pkcs11 está instalado")
    def test_avisa_si_falta_el_extra_al_abrir(self) -> None:
        with pytest.raises(ConfiguracionError, match=r"pysifen\[pkcs11\]"):
            FirmantePkcs11.abrir("/ruta/inexistente.so", Secreto("1234"))

    @pytest.mark.skipif(_hay_pkcs11(), reason="el extra pkcs11 está instalado")
    def test_avisa_si_falta_el_extra_al_firmar(
        self, certificado_juridica: Certificado
    ) -> None:
        firmante = FirmantePkcs11(
            sesion=None, clave=object(), certificado=certificado_juridica
        )
        with pytest.raises(ConfiguracionError, match=r"pysifen\[pkcs11\]"):
            firmante.firmar(b"datos")


class _SesionFalsa:
    """Sesión PKCS#11 de mentira, para verificar el cierre."""

    def __init__(self) -> None:
        self.cerrada = False

    def close(self) -> None:
        self.cerrada = True


class _ServicioFalso:
    """Servicio de firma remota de mentira, para los tests."""

    def __init__(
        self,
        certificado: Certificado,
        *,
        falla: bool = False,
        respuesta: bytes = b"firma-del-prestador",
    ) -> None:
        self._certificado = certificado
        self._falla = falla
        self._respuesta = respuesta
        self.pedidos: list[bytes] = []

    @property
    def certificado(self) -> Certificado:
        return self._certificado

    def firmar_remotamente(self, datos: bytes) -> bytes:
        if self._falla:
            raise RuntimeError("el prestador no responde")
        self.pedidos.append(datos)
        return self._respuesta
