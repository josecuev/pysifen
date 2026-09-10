"""Pruebas de la consulta de revocación.

La consulta sale a la red del prestador, pero acá **no se sale a la red**: se
arman una respuesta OCSP y una lista de revocados con la jerarquía de prueba de
``conftest``, y se comprueba qué hace el verificador con cada una.

No hay ninguna prueba contra un servidor real, y no por comodidad: haría falta
un certificado real de un contribuyente, y en el repositorio no entra ninguno.
El camino de red se comprobó a mano contra los respondedores de DOCUMENTA y de
ITTI, y lo que se puede probar acá —que es lo que importa— es qué hace la
librería con cada respuesta posible.

Porque lo que importa no es que sepa preguntar, sino que **no crea cualquier
respuesta**. Una respuesta OCSP sin verificar no vale nada: cualquiera que
intercepte la conexión puede contestar "vigente".
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509 import ocsp
from cryptography.x509.oid import (
    AuthorityInformationAccessOID,
    ExtendedKeyUsageOID,
    NameOID,
)

from pysifen.pki.certificado import Certificado
from pysifen.pki.revocacion import (
    EstadoDeRevocacion,
    ResultadoDeRevocacion,
    _direcciones_crl,
    _direcciones_ocsp,
    _leer_crl,
    _pedir,
    _por_crl,
    _por_ocsp,
    _verificar_firma,
    _verificar_respuesta_ocsp,
    consultar_revocacion,
)
from tests.conftest import (
    AutoridadDePrueba,
    clave,
    construir_ca,
    construir_certificado,
    jerarquia_de_prueba,
    lista_de_prueba,
)


@pytest.fixture(scope="session")
def titular() -> Certificado:
    """Un certificado emitido por la autoridad intermedia de prueba."""
    _, intermedia = jerarquia_de_prueba()
    return construir_certificado(ruc_en_subject="RUC80012345-6", firmada_por=intermedia)


def _respuesta_ocsp(
    certificado: Certificado,
    autoridad: AutoridadDePrueba,
    estado: ocsp.OCSPCertStatus,
    *,
    firmante: AutoridadDePrueba | None = None,
    delegado: x509.Certificate | None = None,
    revocado_el: datetime | None = None,
) -> ocsp.OCSPResponse:
    """Arma una respuesta OCSP firmada, como la daría un prestador."""
    quien = firmante or autoridad
    constructor = ocsp.OCSPResponseBuilder().add_response(
        cert=certificado.x509,
        issuer=autoridad.certificado,
        algorithm=hashes.SHA1(),  # noqa: S303 - lo que fija el RFC 6960
        cert_status=estado,
        this_update=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
        next_update=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
        revocation_time=revocado_el,
        revocation_reason=None,
    )
    constructor = constructor.responder_id(
        ocsp.OCSPResponderEncoding.HASH, quien.certificado
    )
    if delegado is not None:
        constructor = constructor.certificates([delegado])
    return constructor.sign(quien.clave, hashes.SHA256())


def _crl(
    autoridad: AutoridadDePrueba,
    revocados: list[tuple[int, datetime]],
    *,
    firmante: AutoridadDePrueba | None = None,
) -> x509.CertificateRevocationList:
    """Arma una lista de revocados firmada por la autoridad."""
    quien = firmante or autoridad
    ahora = datetime.now(UTC)
    constructor = (
        x509.CertificateRevocationListBuilder()
        .issuer_name(autoridad.certificado.subject)
        .last_update(ahora - timedelta(hours=1))
        .next_update(ahora + timedelta(days=1))
    )
    for serie, cuando in revocados:
        constructor = constructor.add_revoked_certificate(
            x509.RevokedCertificateBuilder()
            .serial_number(serie)
            .revocation_date(cuando)
            .build()
        )
    return constructor.sign(quien.clave, hashes.SHA256())


class TestLaRespuestaSeVerifica:
    """Una respuesta OCSP sin firma comprobada no prueba nada."""

    def test_una_respuesta_del_emisor_se_acepta(self, titular: Certificado) -> None:
        _, intermedia = jerarquia_de_prueba()

        respuesta = _respuesta_ocsp(titular, intermedia, ocsp.OCSPCertStatus.GOOD)

        assert _verificar_respuesta_ocsp(respuesta, intermedia.certificado) is None

    def test_una_respuesta_de_un_impostor_se_rechaza(
        self, titular: Certificado
    ) -> None:
        # El ataque: alguien contesta "vigente" por un certificado que no emitió.
        _, intermedia = jerarquia_de_prueba()
        impostor = construir_ca("CA IMPOSTORA", rol="ca-impostora")

        respuesta = _respuesta_ocsp(
            titular, intermedia, ocsp.OCSPCertStatus.GOOD, firmante=impostor
        )

        problema = _verificar_respuesta_ocsp(respuesta, intermedia.certificado)
        assert problema is not None
        assert "firma" in problema

    def test_un_respondedor_delegado_sin_habilitacion_se_rechaza(
        self, titular: Certificado
    ) -> None:
        # El emisor puede delegar, pero el delegado tiene que llevar
        # id-kp-OCSPSigning: es el apartado 4.2.2.2 del RFC 6960.
        _, intermedia = jerarquia_de_prueba()
        sin_permiso = _delegado(intermedia, con_habilitacion=False)

        respuesta = _respuesta_ocsp(
            titular,
            intermedia,
            ocsp.OCSPCertStatus.GOOD,
            firmante=sin_permiso,
            delegado=sin_permiso.certificado,
        )

        problema = _verificar_respuesta_ocsp(respuesta, intermedia.certificado)
        assert problema is not None
        assert "OCSP" in problema

    def test_un_respondedor_delegado_habilitado_se_acepta(
        self, titular: Certificado
    ) -> None:
        _, intermedia = jerarquia_de_prueba()
        con_permiso = _delegado(intermedia, con_habilitacion=True)

        respuesta = _respuesta_ocsp(
            titular,
            intermedia,
            ocsp.OCSPCertStatus.GOOD,
            firmante=con_permiso,
            delegado=con_permiso.certificado,
        )

        assert _verificar_respuesta_ocsp(respuesta, intermedia.certificado) is None


def _delegado(
    autoridad: AutoridadDePrueba, *, con_habilitacion: bool
) -> AutoridadDePrueba:
    """Arma un respondedor OCSP emitido por la autoridad."""
    ahora = datetime.now(UTC)
    llave = clave(rol=f"respondedor-{con_habilitacion}")
    constructor = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "RESPONDEDOR OCSP")])
        )
        .issuer_name(autoridad.certificado.subject)
        .public_key(llave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora - timedelta(days=1))
        .not_valid_after(ahora + timedelta(days=365))
    )
    if con_habilitacion:
        constructor = constructor.add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.OCSP_SIGNING]), critical=False
        )
    else:
        constructor = constructor.add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False
        )
    return AutoridadDePrueba(
        certificado=constructor.sign(autoridad.clave, hashes.SHA256()), clave=llave
    )


class TestQueSeConsulta:
    """Lo que hace con cada respuesta, sin salir a la red."""

    def test_vigente(
        self, titular: Certificado, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, intermedia = jerarquia_de_prueba()
        _responder(monkeypatch, titular, intermedia, ocsp.OCSPCertStatus.GOOD)

        resultado = _por_ocsp(
            titular.x509,
            intermedia.certificado,
            "https://ocsp.ejemplo",
            5,
            datetime.now(UTC),
        )

        assert resultado.estado is EstadoDeRevocacion.VIGENTE
        assert resultado.fuente == "OCSP"

    def test_revocado(
        self, titular: Certificado, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, intermedia = jerarquia_de_prueba()
        cuando = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)
        _responder(
            monkeypatch,
            titular,
            intermedia,
            ocsp.OCSPCertStatus.REVOKED,
            revocado_el=cuando,
        )

        resultado = _por_ocsp(
            titular.x509,
            intermedia.certificado,
            "https://ocsp.ejemplo",
            5,
            datetime.now(UTC),
        )

        assert resultado.estado is EstadoDeRevocacion.REVOCADO
        assert resultado.revocado is True
        assert resultado.revocado_el is not None

    def test_revocado_despues_de_la_firma_no_invalida_lo_firmado(
        self, titular: Certificado, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Un certificado dado de baja el mes pasado no invalida lo que firmó
        # cuando servía. Es el mismo criterio que para la vigencia.
        _, intermedia = jerarquia_de_prueba()
        revocado_el = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=10)
        _responder(
            monkeypatch,
            titular,
            intermedia,
            ocsp.OCSPCertStatus.REVOKED,
            revocado_el=revocado_el,
        )

        firmado_antes = datetime.now(UTC) - timedelta(days=90)
        resultado = _por_ocsp(
            titular.x509,
            intermedia.certificado,
            "https://ocsp.ejemplo",
            5,
            firmado_antes,
        )

        assert resultado.estado is EstadoDeRevocacion.VIGENTE
        assert resultado.motivo is not None
        assert "después del momento evaluado" in resultado.motivo

    def test_un_servidor_caido_no_lanza(
        self, titular: Certificado, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def caido(*_a: object, **_k: object) -> bytes:
            raise TimeoutError("no contesta")

        monkeypatch.setattr("pysifen.pki.revocacion._pedir", caido)
        _, intermedia = jerarquia_de_prueba()

        resultado = _por_ocsp(
            titular.x509,
            intermedia.certificado,
            "https://ocsp.ejemplo",
            5,
            datetime.now(UTC),
        )

        assert resultado.estado is EstadoDeRevocacion.DESCONOCIDO
        assert resultado.comprobado is False

    def test_sin_emisor_conocido_no_se_inventa_un_veredicto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Sin el certificado del emisor no hay contra qué verificar la
        # respuesta, así que no se consulta: se informa desconocido.
        suelto = construir_certificado(ruc_en_subject="RUC80012345-6")

        resultado = consultar_revocacion(suelto, lista=lista_de_prueba())

        assert resultado.estado is EstadoDeRevocacion.DESCONOCIDO
        assert resultado.motivo is not None
        assert "autoridad" in resultado.motivo


def _responder(
    monkeypatch: pytest.MonkeyPatch,
    titular: Certificado,
    autoridad: AutoridadDePrueba,
    estado: ocsp.OCSPCertStatus,
    revocado_el: datetime | None = None,
) -> None:
    """Hace que la consulta devuelva la respuesta armada acá, sin red."""
    respuesta = _respuesta_ocsp(titular, autoridad, estado, revocado_el=revocado_el)
    crudo = respuesta.public_bytes(serialization.Encoding.DER)
    monkeypatch.setattr("pysifen.pki.revocacion._pedir", lambda *a, **k: crudo)


class TestPorLaListaDeRevocados:
    """El respaldo cuando OCSP no está o no contesta."""

    def test_un_certificado_que_no_esta_en_la_lista(
        self, titular: Certificado, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, intermedia = jerarquia_de_prueba()
        lista = _crl(intermedia, [(999, datetime.now(UTC) - timedelta(days=5))])
        monkeypatch.setattr(
            "pysifen.pki.revocacion._pedir",
            lambda *a, **k: lista.public_bytes(serialization.Encoding.DER),
        )

        resultado = _por_crl(
            titular.x509,
            intermedia.certificado,
            "https://crl.ejemplo",
            5,
            datetime.now(UTC),
        )

        assert resultado.estado is EstadoDeRevocacion.VIGENTE
        assert resultado.fuente == "CRL"

    def test_un_certificado_revocado(
        self, titular: Certificado, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, intermedia = jerarquia_de_prueba()
        lista = _crl(
            intermedia,
            [(titular.x509.serial_number, datetime.now(UTC) - timedelta(days=5))],
        )
        monkeypatch.setattr(
            "pysifen.pki.revocacion._pedir",
            lambda *a, **k: lista.public_bytes(serialization.Encoding.DER),
        )

        resultado = _por_crl(
            titular.x509,
            intermedia.certificado,
            "https://crl.ejemplo",
            5,
            datetime.now(UTC),
        )

        assert resultado.revocado is True

    def test_una_lista_firmada_por_otro_se_rechaza(
        self, titular: Certificado, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Sin comprobar la firma, cualquiera podría publicar una lista vacía y
        # hacer pasar por vigente a un certificado revocado.
        _, intermedia = jerarquia_de_prueba()
        impostor = construir_ca("CA IMPOSTORA CRL", rol="ca-impostora-crl")
        lista = _crl(intermedia, [], firmante=impostor)
        monkeypatch.setattr(
            "pysifen.pki.revocacion._pedir",
            lambda *a, **k: lista.public_bytes(serialization.Encoding.DER),
        )

        resultado = _por_crl(
            titular.x509,
            intermedia.certificado,
            "https://crl.ejemplo",
            5,
            datetime.now(UTC),
        )

        assert resultado.estado is EstadoDeRevocacion.DESCONOCIDO
        assert resultado.motivo is not None
        assert "firmada" in resultado.motivo


class TestElResultado:
    """La forma del resultado."""

    def test_desconocido_no_es_vigente(self) -> None:
        resultado = ResultadoDeRevocacion(EstadoDeRevocacion.DESCONOCIDO)

        assert resultado.revocado is False
        assert resultado.comprobado is False


class TestDondePreguntar:
    """Las direcciones salen del certificado, no de una tabla."""

    def test_un_certificado_que_no_declara_nada(self) -> None:
        # Los certificados de prueba de conftest no llevan AIA ni CDP.
        suelto = construir_certificado(ruc_en_subject="RUC80012345-6")

        assert _direcciones_ocsp(suelto.x509) == []
        assert _direcciones_crl(suelto.x509) == []

    def test_se_leen_las_extensiones_estandar(self) -> None:
        _, intermedia = jerarquia_de_prueba()
        con_puntos = _con_puntos_de_consulta(intermedia)

        assert _direcciones_ocsp(con_puntos) == ["https://ocsp.ejemplo/"]
        assert _direcciones_crl(con_puntos) == [
            "https://crl1.ejemplo/ca.crl",
            "https://crl2.ejemplo/ca.crl",
        ]


def _con_puntos_de_consulta(autoridad: AutoridadDePrueba) -> x509.Certificate:
    """Un certificado que declara OCSP y dos CRL, como los reales."""
    ahora = datetime.now(UTC)
    llave = clave(rol="con-puntos")
    return (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "CON PUNTOS S.A.")])
        )
        .issuer_name(autoridad.certificado.subject)
        .public_key(llave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora - timedelta(days=1))
        .not_valid_after(ahora + timedelta(days=365))
        .add_extension(
            x509.AuthorityInformationAccess(
                [
                    x509.AccessDescription(
                        AuthorityInformationAccessOID.OCSP,
                        x509.UniformResourceIdentifier("https://ocsp.ejemplo/"),
                    ),
                    x509.AccessDescription(
                        AuthorityInformationAccessOID.CA_ISSUERS,
                        x509.UniformResourceIdentifier("https://ejemplo/ca.crt"),
                    ),
                ]
            ),
            critical=False,
        )
        .add_extension(
            x509.CRLDistributionPoints(
                [
                    x509.DistributionPoint(
                        full_name=[
                            x509.UniformResourceIdentifier(
                                "https://crl1.ejemplo/ca.crl"
                            ),
                            x509.UniformResourceIdentifier(
                                "https://crl2.ejemplo/ca.crl"
                            ),
                        ],
                        relative_name=None,
                        reasons=None,
                        crl_issuer=None,
                    )
                ]
            ),
            critical=False,
        )
        .sign(autoridad.clave, hashes.SHA256())
    )


class TestElOrden:
    """OCSP primero, la lista de revocados como respaldo."""

    def test_si_ocsp_contesta_no_se_baja_la_lista(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, intermedia = jerarquia_de_prueba()
        con_puntos = _con_puntos_de_consulta(intermedia)
        titular = Certificado(con_puntos)
        respuesta = _respuesta_ocsp(titular, intermedia, ocsp.OCSPCertStatus.GOOD)
        pedidos: list[str] = []

        def responder(url: str, *_a: object, **_k: object) -> bytes:
            pedidos.append(url)
            return respuesta.public_bytes(serialization.Encoding.DER)

        monkeypatch.setattr("pysifen.pki.revocacion._pedir", responder)

        resultado = consultar_revocacion(titular, emisor=intermedia.certificado)

        assert resultado.estado is EstadoDeRevocacion.VIGENTE
        assert resultado.fuente == "OCSP"
        assert pedidos == ["https://ocsp.ejemplo/"]

    def test_si_ocsp_no_contesta_se_usa_la_lista(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Es lo que pasó de verdad con un prestador: su respondedor devolvió un
        # 403 transitorio y la consulta se resolvió igual por la CRL.
        _, intermedia = jerarquia_de_prueba()
        con_puntos = _con_puntos_de_consulta(intermedia)
        titular = Certificado(con_puntos)
        lista = _crl(intermedia, [])
        pedidos: list[str] = []

        def responder(url: str, *_a: object, **_k: object) -> bytes:
            pedidos.append(url)
            if "ocsp" in url:
                raise TimeoutError("no contesta")
            return lista.public_bytes(serialization.Encoding.DER)

        monkeypatch.setattr("pysifen.pki.revocacion._pedir", responder)

        resultado = consultar_revocacion(titular, emisor=intermedia.certificado)

        assert resultado.estado is EstadoDeRevocacion.VIGENTE
        assert resultado.fuente == "CRL"
        assert pedidos[0] == "https://ocsp.ejemplo/"

    def test_si_no_contesta_nadie_queda_desconocido(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, intermedia = jerarquia_de_prueba()
        titular = Certificado(_con_puntos_de_consulta(intermedia))

        def caido(*_a: object, **_k: object) -> bytes:
            raise TimeoutError("no contesta")

        monkeypatch.setattr("pysifen.pki.revocacion._pedir", caido)

        resultado = consultar_revocacion(titular, emisor=intermedia.certificado)

        assert resultado.estado is EstadoDeRevocacion.DESCONOCIDO
        assert resultado.motivo is not None
        assert "OCSP" in resultado.motivo
        assert "CRL" in resultado.motivo

    def test_un_certificado_sin_puntos_de_consulta(self, titular: Certificado) -> None:
        _, intermedia = jerarquia_de_prueba()

        resultado = consultar_revocacion(titular, emisor=intermedia.certificado)

        assert resultado.estado is EstadoDeRevocacion.DESCONOCIDO
        assert resultado.motivo is not None
        assert "no declara" in resultado.motivo


class TestRespuestasQueNoSirven:
    """Lo que se rechaza sin llegar a mirar el veredicto."""

    def test_una_respuesta_sobre_otro_certificado(
        self, titular: Certificado, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # El respondedor contesta, pero por un número de serie que no es el que
        # se preguntó. Aceptarlo sería dar por vigente cualquier cosa.
        _, intermedia = jerarquia_de_prueba()
        otro = construir_certificado(
            ruc_en_subject="RUC80099999-1", firmada_por=intermedia
        )
        respuesta = _respuesta_ocsp(otro, intermedia, ocsp.OCSPCertStatus.GOOD)
        monkeypatch.setattr(
            "pysifen.pki.revocacion._pedir",
            lambda *a, **k: respuesta.public_bytes(serialization.Encoding.DER),
        )

        resultado = _por_ocsp(
            titular.x509,
            intermedia.certificado,
            "https://ocsp.ejemplo",
            5,
            datetime.now(UTC),
        )

        assert resultado.estado is EstadoDeRevocacion.DESCONOCIDO
        assert resultado.motivo is not None
        assert "otro certificado" in resultado.motivo

    def test_un_respondedor_que_no_conoce_el_certificado(
        self, titular: Certificado, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, intermedia = jerarquia_de_prueba()
        _responder(monkeypatch, titular, intermedia, ocsp.OCSPCertStatus.UNKNOWN)

        resultado = _por_ocsp(
            titular.x509,
            intermedia.certificado,
            "https://ocsp.ejemplo",
            5,
            datetime.now(UTC),
        )

        assert resultado.estado is EstadoDeRevocacion.DESCONOCIDO
        assert resultado.motivo is not None
        assert "no conoce" in resultado.motivo

    def test_una_respuesta_sin_exito(
        self, titular: Certificado, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fallida = ocsp.OCSPResponseBuilder.build_unsuccessful(
            ocsp.OCSPResponseStatus.TRY_LATER
        )
        monkeypatch.setattr(
            "pysifen.pki.revocacion._pedir",
            lambda *a, **k: fallida.public_bytes(serialization.Encoding.DER),
        )
        _, intermedia = jerarquia_de_prueba()

        resultado = _por_ocsp(
            titular.x509,
            intermedia.certificado,
            "https://ocsp.ejemplo",
            5,
            datetime.now(UTC),
        )

        assert resultado.estado is EstadoDeRevocacion.DESCONOCIDO
        assert resultado.motivo is not None
        assert "TRY_LATER" in resultado.motivo


class TestLaConsultaEnSi:
    """El transporte, que también tiene bordes."""

    def test_no_se_admite_cualquier_esquema(self) -> None:
        # Un certificado podría declarar ldap:// o file://. Salir a buscarlo
        # sería seguir una dirección que la escribió quien firmó el documento.
        with pytest.raises(ValueError, match="esquema no admitido"):
            _pedir("ftp://ejemplo/ca.crl", 5)

    def test_una_lista_en_pem_tambien_se_lee(self) -> None:
        _, intermedia = jerarquia_de_prueba()
        lista = _crl(intermedia, [])

        vuelta = _leer_crl(lista.public_bytes(serialization.Encoding.PEM))

        assert vuelta.issuer == intermedia.certificado.subject

    def test_una_clave_que_no_se_maneja(self) -> None:
        from cryptography.hazmat.primitives.asymmetric import ed25519

        with pytest.raises(Exception, match="tipo de clave"):
            _verificar_firma(
                ed25519.Ed25519PrivateKey.generate().public_key(),
                b"firma",
                b"contenido",
                hashes.SHA256(),
            )

    def test_una_respuesta_sin_algoritmo_declarado(self) -> None:
        with pytest.raises(Exception, match="algoritmo"):
            _verificar_firma(
                ec.generate_private_key(ec.SECP256R1()).public_key(),
                b"firma",
                b"contenido",
                None,
            )
