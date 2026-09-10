"""Utilidades compartidas por los tests.

Los certificados de prueba se generan al vuelo y son autofirmados. En el
repositorio no entra nunca un certificado real ni una clave privada real, ni
siquiera de prueba: ver `SECURITY.md`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from pysifen.pki.certificado import Certificado

#: Generar claves RSA es caro. Se reutilizan por sesión.
_CLAVES: dict[int, rsa.RSAPrivateKey] = {}


def clave(bits: int = 2048) -> rsa.RSAPrivateKey:
    """Devuelve una clave RSA de prueba, reutilizada por tamaño."""
    if bits not in _CLAVES:
        _CLAVES[bits] = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    return _CLAVES[bits]


def construir_certificado(
    *,
    ruc_en_subject: str | None = None,
    ruc_en_san: str | None = None,
    titular: str = "CONTRIBUYENTE DE PRUEBA S.A.",
    emisor: str = "DOCUMENTA S.A.",
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
        emisor: nombre común del emisor, para simular a cada prestador.
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

    atributos_subject = [x509.NameAttribute(NameOID.COMMON_NAME, titular)]
    if ruc_en_subject:
        atributos_subject.append(
            x509.NameAttribute(NameOID.SERIAL_NUMBER, ruc_en_subject)
        )

    constructor = (
        x509.CertificateBuilder()
        .subject_name(x509.Name(atributos_subject))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, emisor)]))
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

    return Certificado(constructor.sign(llave, hashes.SHA256()))


@pytest.fixture(scope="session")
def certificado_juridica() -> Certificado:
    """Certificado de persona jurídica, con el RUC en el ``Subject``."""
    return construir_certificado(ruc_en_subject="RUC80012345-6")


@pytest.fixture(scope="session")
def certificado_fisica() -> Certificado:
    """Certificado de persona física, con el RUC en el ``SubjectAltName``."""
    return construir_certificado(
        titular="JUAN PEREZ",
        ruc_en_san="RUC80012345-6",
    )
