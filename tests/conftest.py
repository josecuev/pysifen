"""Utilidades compartidas por los tests.

Los certificados de prueba se generan al vuelo. En el repositorio no entra nunca
un certificado real ni una clave privada real, ni siquiera de prueba: ver
`SECURITY.md`.

La jerarquía de prueba
----------------------

Desde que la librería valida la cadena de confianza de verdad, un certificado
suelto ya no alcanza para probar el camino feliz: hay que armar la jerarquía
entera, raíz incluida.

Así que acá se construye una réplica en miniatura de la del Paraguay —una raíz
que firma una autoridad intermedia, que a su vez firma el certificado del
contribuyente— y una :class:`ListaDeConfianza` que la declara. Cada eslabón
tiene **su propia clave**: si compartieran una, la comprobación de firma pasaría
sin probar nada.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from pysifen.pki.cadena import ESTADO_HABILITADO, Autoridad, ListaDeConfianza
from pysifen.pki.certificado import Certificado
from pysifen.security.secretos import Secreto
from pysifen.signing.backends.pkcs12 import AvisoDeCustodia, FirmantePkcs12

#: Generar claves RSA es caro. Se reutilizan por sesión.
_CLAVES: dict[tuple[int, str], rsa.RSAPrivateKey] = {}


def clave(bits: int = 2048, rol: str = "titular") -> rsa.RSAPrivateKey:
    """Devuelve una clave RSA de prueba, reutilizada por tamaño y rol.

    Args:
        bits: tamaño de la clave.
        rol: para qué es. Cada eslabón tiene la suya: una raíz que compartiera
            la clave del titular haría pasar la validación de cadena sin probar
            nada.
    """
    if (bits, rol) not in _CLAVES:
        _CLAVES[bits, rol] = rsa.generate_private_key(
            public_exponent=65537, key_size=bits
        )
    return _CLAVES[bits, rol]


@dataclass(frozen=True)
class AutoridadDePrueba:
    """Una autoridad certificadora de mentira, con su clave para firmar."""

    certificado: x509.Certificate
    clave: rsa.RSAPrivateKey


def construir_ca(
    nombre: str,
    *,
    firmada_por: AutoridadDePrueba | None = None,
    rol: str | None = None,
    valido_desde: datetime | None = None,
    valido_hasta: datetime | None = None,
) -> AutoridadDePrueba:
    """Arma una autoridad certificadora de prueba.

    Args:
        nombre: su nombre común.
        firmada_por: la autoridad que la emite. Si no se pasa, es una raíz
            autofirmada.
        rol: la clave a usar. Por omisión, una propia por nombre.
        valido_desde: inicio de la vigencia. Por omisión, hace un año.
        valido_hasta: fin de la vigencia. Por omisión, dentro de diez.

    Returns:
        La autoridad, con su certificado y su clave privada.
    """
    ahora = datetime.now(UTC)
    llave = clave(rol=rol or nombre)
    sujeto = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nombre)])
    emisora = firmada_por.certificado.subject if firmada_por else sujeto

    certificado = (
        x509.CertificateBuilder()
        .subject_name(sujeto)
        .issuer_name(emisora)
        .public_key(llave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(valido_desde or ahora - timedelta(days=365))
        .not_valid_after(valido_hasta or ahora + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(firmada_por.clave if firmada_por else llave, hashes.SHA256())
    )
    return AutoridadDePrueba(certificado=certificado, clave=llave)


@lru_cache(maxsize=1)
def jerarquia_de_prueba() -> tuple[AutoridadDePrueba, AutoridadDePrueba]:
    """Devuelve la raíz y la autoridad intermedia de prueba.

    Réplica en miniatura de la jerarquía real: una raíz nacional que firma la
    autoridad de un prestador cualificado.
    """
    raiz = construir_ca("Autoridad Certificadora Raíz de Prueba")
    intermedia = construir_ca("CA-PRESTADOR DE PRUEBA S.A.", firmada_por=raiz)
    return raiz, intermedia


def lista_de_prueba(
    *,
    estado_del_prestador: str = ESTADO_HABILITADO,
    tipo_de_servicio: str = "QC",
) -> ListaDeConfianza:
    """Arma una lista de confianza que declara la jerarquía de prueba.

    Args:
        estado_del_prestador: el estado del servicio del prestador. Cambiarlo
            permite probar qué pasa cuando el MIC le retira la habilitación.
        tipo_de_servicio: el tipo del servicio. Cambiarlo permite probar que una
            jerarquía ajena a los documentos tributarios —la de firma de
            funcionarios públicos, por ejemplo— no se acepta.

    Returns:
        La lista, lista para pasarle a las funciones de verificación.
    """
    raiz, intermedia = jerarquia_de_prueba()
    return ListaDeConfianza(
        [
            Autoridad(
                prestador="Ministerio de Prueba",
                certificado=raiz.certificado,
                estado="recognisedatnationallevel",
                tipo_de_servicio="NationalRootCA-QC",
            ),
            Autoridad(
                prestador="PRESTADOR DE PRUEBA S.A.",
                certificado=intermedia.certificado,
                estado=estado_del_prestador,
                tipo_de_servicio=tipo_de_servicio,
            ),
        ]
    )


def construir_certificado(
    *,
    ruc_en_subject: str | None = None,
    ruc_en_san: str | None = None,
    titular: str = "CONTRIBUYENTE DE PRUEBA S.A.",
    emisor: str = "DOCUMENTA S.A.",
    firmada_por: AutoridadDePrueba | None = None,
    client_auth: bool = True,
    firma_digital: bool = True,
    con_key_usage: bool = True,
    valido_desde: datetime | None = None,
    valido_hasta: datetime | None = None,
    bits: int = 2048,
) -> Certificado:
    """Arma un certificado autofirmado con las características pedidas.

    Args:
        ruc_en_subject: si se pasa, va como ``SerialNumber`` del ``Subject``,
            que es donde lo lleva el certificado de persona jurídica.
        ruc_en_san: si se pasa, va como ``SerialNumber`` dentro de un
            ``DirectoryName`` del ``SubjectAlternativeName``, que es donde lo
            lleva el certificado de persona física.
        titular: nombre común del titular.
        emisor: nombre común del emisor, cuando el certificado es autofirmado.
        firmada_por: la autoridad que lo emite. Sin esto queda autofirmado,
            que es justo lo que la validación de cadena rechaza.
        client_auth: si incluir ``clientAuth`` en ``Extended Key Usage``.
        firma_digital: si habilitar la firma en ``Key Usage``.
        con_key_usage: si incluir la extensión ``Key Usage``.
        valido_desde: inicio de la vigencia. Por omisión, ayer.
        valido_hasta: fin de la vigencia. Por omisión, dentro de un año.
        bits: tamaño de la clave RSA.

    Returns:
        El certificado ya envuelto en :class:`Certificado`.
    """
    llave = clave(bits)
    ahora = datetime.now(UTC)
    emisora = (
        firmada_por.certificado.subject
        if firmada_por
        else x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, emisor)])
    )

    atributos_subject = [x509.NameAttribute(NameOID.COMMON_NAME, titular)]
    if ruc_en_subject:
        atributos_subject.append(
            x509.NameAttribute(NameOID.SERIAL_NUMBER, ruc_en_subject)
        )

    constructor = (
        x509.CertificateBuilder()
        .subject_name(x509.Name(atributos_subject))
        .issuer_name(emisora)
        .public_key(llave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(valido_desde or ahora - timedelta(days=1))
        .not_valid_after(valido_hasta or ahora + timedelta(days=365))
    )

    if ruc_en_san:
        constructor = constructor.add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DirectoryName(
                        x509.Name(
                            [
                                x509.NameAttribute(NameOID.SERIAL_NUMBER, ruc_en_san),
                                x509.NameAttribute(
                                    NameOID.ORGANIZATION_NAME, "EMPLEADORA S.A."
                                ),
                            ]
                        )
                    )
                ]
            ),
            critical=False,
        )

    if client_auth:
        constructor = constructor.add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        )
    else:
        constructor = constructor.add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]),
            critical=False,
        )

    if con_key_usage:
        constructor = constructor.add_extension(
            x509.KeyUsage(
                digital_signature=firma_digital,
                content_commitment=firma_digital,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )

    return Certificado(
        constructor.sign(firmada_por.clave if firmada_por else llave, hashes.SHA256())
    )


@pytest.fixture(scope="session")
def certificado_juridica() -> Certificado:
    """Certificado de persona jurídica, con el RUC en el ``Subject``.

    Emitido por la autoridad intermedia de prueba, así que encadena hasta la
    raíz igual que uno real.
    """
    _, intermedia = jerarquia_de_prueba()
    return construir_certificado(ruc_en_subject="RUC80012345-6", firmada_por=intermedia)


@pytest.fixture(scope="session")
def anclas_de_prueba() -> ListaDeConfianza:
    """La lista de confianza que declara la jerarquía de prueba."""
    return lista_de_prueba()


@pytest.fixture(scope="session")
def certificado_fisica() -> Certificado:
    """Certificado de persona física, con el RUC en el ``SubjectAltName``."""
    return construir_certificado(
        titular="JUAN PEREZ",
        ruc_en_san="RUC80012345-6",
    )


#: CDC del ejemplo del apartado 10.1 del Manual Tecnico v150.
CDC_DEL_MANUAL = "01444444017001001001452822017012515873260988"

#: Un rDE minimo, con la estructura que muestra el manual en el apartado 7.6.
RDE_SIN_FIRMAR = f"""<?xml version="1.0" encoding="UTF-8"?>
<rDE xmlns="http://ekuatia.set.gov.py/sifen/xsd"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dVerFor>150</dVerFor>
  <DE Id="{CDC_DEL_MANUAL}">
    <dDVId>8</dDVId>
    <dFecFirma>2026-09-10T10:00:00</dFecFirma>
    <dSisFact>1</dSisFact>
    <gOpeDE>
      <iTipEmi>1</iTipEmi>
      <dDesTipEmi>Normal</dDesTipEmi>
      <dCodSeg>587326098</dCodSeg>
    </gOpeDE>
  </DE>
</rDE>
"""


def construir_pkcs12(
    certificado: Certificado, contrasena: str = "prueba", bits: int = 2048
) -> bytes:
    """Empaqueta un certificado de prueba y su clave en un PKCS#12."""
    return serialization.pkcs12.serialize_key_and_certificates(
        name=b"prueba",
        key=clave(bits),
        cert=certificado.x509,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(contrasena.encode()),
    )


@pytest.fixture
def firmante(certificado_juridica: Certificado) -> FirmantePkcs12:
    """Firmante de prueba respaldado por un PKCS#12 en memoria."""
    datos = construir_pkcs12(certificado_juridica)
    with pytest.warns(AvisoDeCustodia, match="custodia"):
        return FirmantePkcs12.desde_bytes(
            datos,
            Secreto("prueba", nombre="contraseña del keystore"),
            permitir_clave_en_memoria=True,
        )
