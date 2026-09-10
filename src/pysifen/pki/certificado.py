"""Lectura del certificado digital del contribuyente.

Implementa los apartados 7.5, 7.7 y 7.9 del Manual Técnico SIFEN v150 en lo que
hace a la **lectura** del certificado. Acá no se firma nada ni se toca material
de clave privada: este módulo sólo mira la parte pública.

El manual exige que el RUC del contribuyente viaje dentro del certificado, y el
lugar depende del tipo de titular:

- **Persona jurídica** → atributo ``SerialNumber`` (OID 2.5.4.5) del ``Subject``.
- **Persona física** → ``SerialNumber`` dentro del ``SubjectAlternativeName``.
  Además el certificado debe llevar el nombre y el RUC de la entidad donde
  presta servicio el titular.

En los dos casos el formato es ``RUCXXXXXXXXX-X``: la palabra ``RUC`` en
mayúsculas, el número, un guion y el dígito verificador, sin espacios.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from pysifen.enums import TipoContribuyente
from pysifen.exceptions import PkiError

__all__ = ["Certificado"]

#: Patrón del RUC dentro del certificado, según el apartado 7.5.
_PATRON_RUC: Final = re.compile(r"RUC(\d{1,8})-(\d)")

#: Tamaño mínimo de clave RSA que admite el manual para firma por software.
_BITS_MINIMOS: Final = 2048


@dataclass(frozen=True, slots=True)
class Certificado:
    """Un certificado X.509 leído desde el punto de vista del SIFEN.

    Envuelve un certificado de :mod:`cryptography` y expone lo que el Manual
    Técnico necesita saber de él. Es inmutable y no contiene clave privada.
    """

    x509: x509.Certificate

    # -- construcción ------------------------------------------------------

    @classmethod
    def desde_pem(cls, datos: bytes | str) -> Certificado:
        """Lee un certificado en formato PEM.

        Args:
            datos: contenido PEM, en texto o en bytes.

        Returns:
            El certificado leído.

        Raises:
            PkiError: si el contenido no es un certificado PEM válido.
        """
        crudo = datos.encode() if isinstance(datos, str) else datos
        try:
            return cls(x509.load_pem_x509_certificate(crudo))
        except Exception as exc:
            raise PkiError(f"no pude leer el certificado PEM: {exc}") from exc

    @classmethod
    def desde_der(cls, datos: bytes) -> Certificado:
        """Lee un certificado en formato DER.

        Args:
            datos: contenido DER.

        Returns:
            El certificado leído.

        Raises:
            PkiError: si el contenido no es un certificado DER válido.
        """
        try:
            return cls(x509.load_der_x509_certificate(datos))
        except Exception as exc:
            raise PkiError(f"no pude leer el certificado DER: {exc}") from exc

    @classmethod
    def desde_archivo(cls, ruta: str | Path) -> Certificado:
        """Lee un certificado desde un archivo, detectando PEM o DER.

        Args:
            ruta: ruta del archivo.

        Returns:
            El certificado leído.

        Raises:
            PkiError: si el archivo no existe o no contiene un certificado.
        """
        camino = Path(ruta)
        try:
            datos = camino.read_bytes()
        except OSError as exc:
            raise PkiError(f"no pude abrir {camino}: {exc}") from exc

        if b"-----BEGIN" in datos:
            return cls.desde_pem(datos)
        return cls.desde_der(datos)

    # -- identidad ---------------------------------------------------------

    @property
    def ruc(self) -> str | None:
        """RUC del contribuyente, con formato ``12345678-9``.

        Lo busca primero en el ``Subject``, que es donde va en el certificado de
        persona jurídica, y después en el ``SubjectAlternativeName``, que es
        donde va en el de persona física.

        Returns:
            El RUC sin el prefijo ``RUC``, o ``None`` si el certificado no lo
            informa en ninguno de los dos lugares.
        """
        for texto in self._textos_con_posible_ruc():
            encontrado = _PATRON_RUC.search(texto)
            if encontrado:
                return f"{encontrado.group(1)}-{encontrado.group(2)}"
        return None

    @property
    def tipo_contribuyente(self) -> TipoContribuyente | None:
        """Deduce si el titular es persona física o jurídica.

        La deducción sale de **dónde** aparece el RUC, que es justamente lo que
        distingue a los dos casos según el apartado 7.5.

        Returns:
            El tipo, o ``None`` si el certificado no informa el RUC.
        """
        if _PATRON_RUC.search(self._texto_del_subject()):
            return TipoContribuyente.PERSONA_JURIDICA
        if _PATRON_RUC.search(self._texto_del_san()):
            return TipoContribuyente.PERSONA_FISICA
        return None

    @property
    def titular(self) -> str:
        """Nombre común del titular, o el ``Subject`` completo si no lo hay."""
        return _atributo(self.x509.subject, NameOID.COMMON_NAME) or (
            self.x509.subject.rfc4514_string()
        )

    @property
    def emisor(self) -> str:
        """Representación textual del emisor, para identificar al prestador."""
        return self.x509.issuer.rfc4514_string()

    @property
    def numero_de_serie(self) -> str:
        """Número de serie del certificado, en hexadecimal."""
        return format(self.x509.serial_number, "x")

    # -- vigencia ----------------------------------------------------------

    @property
    def valido_desde(self) -> datetime:
        """Inicio de la vigencia, en UTC."""
        return self.x509.not_valid_before_utc

    @property
    def valido_hasta(self) -> datetime:
        """Fin de la vigencia, en UTC."""
        return self.x509.not_valid_after_utc

    def vigente(self, momento: datetime | None = None) -> bool:
        """Indica si el certificado está vigente en un momento dado.

        No consulta la lista de revocados: la vigencia y la revocación son cosas
        distintas. El apartado 7.6 aclara que el SIFEN consulta la revocación
        por su cuenta al validar.

        Args:
            momento: instante a evaluar. Por omisión, ahora en UTC.

        Returns:
            ``True`` si el momento cae dentro del período de validez.

        Raises:
            PkiError: si ``momento`` no trae zona horaria.
        """
        instante = momento or datetime.now(UTC)
        if instante.tzinfo is None:
            raise PkiError("el momento a evaluar debe traer zona horaria")
        return self.valido_desde <= instante <= self.valido_hasta

    # -- aptitud para el SIFEN --------------------------------------------

    @property
    def sirve_para_autenticacion_tls(self) -> bool:
        """Indica si el certificado sirve para la autenticación mutua TLS.

        El apartado 7.5 exige que, para establecer la conexión con los servicios
        del SIFEN, el certificado tenga la extensión ``Extended Key Usage`` con
        el permiso ``clientAuth``. Es un requisito que se olvida seguido y que
        se manifiesta recién al intentar transmitir.
        """
        try:
            extension = self.x509.extensions.get_extension_for_class(
                x509.ExtendedKeyUsage
            )
        except x509.ExtensionNotFound:
            return False
        return ExtendedKeyUsageOID.CLIENT_AUTH in extension.value

    @property
    def sirve_para_firmar(self) -> bool:
        """Indica si el certificado habilita la firma digital.

        Un certificado sin ``Key Usage`` no se rechaza: la extensión es
        opcional, y su ausencia no restringe el uso.
        """
        try:
            extension = self.x509.extensions.get_extension_for_class(x509.KeyUsage)
        except x509.ExtensionNotFound:
            return True
        uso = extension.value
        return uso.digital_signature or uso.content_commitment

    @property
    def bits_de_clave(self) -> int | None:
        """Tamaño de la clave pública en bits, o ``None`` si no es RSA."""
        clave = self.x509.public_key()
        tamano = getattr(clave, "key_size", None)
        return tamano if isinstance(tamano, int) else None

    def problemas_para_sifen(self, momento: datetime | None = None) -> list[str]:
        """Enumera lo que impediría usar este certificado contra el SIFEN.

        Reúne en un solo lugar las condiciones de los apartados 7.5, 7.7 y 7.9,
        de modo que el problema se detecte al configurar y no al transmitir.

        Args:
            momento: instante a evaluar la vigencia. Por omisión, ahora.

        Returns:
            Lista de problemas en castellano. Vacía si el certificado sirve.
        """
        problemas: list[str] = []

        if self.ruc is None:
            problemas.append(
                "el certificado no informa el RUC del contribuyente; el manual "
                "lo exige en el SerialNumber del Subject para persona jurídica "
                "o en el SubjectAlternativeName para persona física (7.5)"
            )

        if not self.vigente(momento):
            problemas.append(
                f"el certificado no está vigente: rige del "
                f"{self.valido_desde:%d/%m/%Y} al {self.valido_hasta:%d/%m/%Y}"
            )

        if not self.sirve_para_autenticacion_tls:
            problemas.append(
                "el certificado no tiene clientAuth en Extended Key Usage, así "
                "que no sirve para la autenticación mutua TLS de los servicios "
                "web (7.5)"
            )

        if not self.sirve_para_firmar:
            problemas.append(
                "el Key Usage del certificado no habilita la firma digital"
            )

        bits = self.bits_de_clave
        if bits is not None and bits < _BITS_MINIMOS:
            problemas.append(
                f"la clave es de {bits} bits y el manual exige RSA de al menos "
                f"{_BITS_MINIMOS} (7.7)"
            )

        return problemas

    # -- internos ----------------------------------------------------------

    def _texto_del_subject(self) -> str:
        """Devuelve el ``Subject`` como texto plano."""
        return self.x509.subject.rfc4514_string()

    def _texto_del_san(self) -> str:
        """Devuelve el ``SubjectAlternativeName`` como texto plano.

        Recorre los nombres de directorio y los ``otherName``, que es donde los
        prestadores paraguayos colocan el RUC en los certificados de persona
        física.
        """
        try:
            extension = self.x509.extensions.get_extension_for_class(
                x509.SubjectAlternativeName
            )
        except x509.ExtensionNotFound:
            return ""

        partes: list[str] = []
        for nombre in extension.value:
            if isinstance(nombre, x509.DirectoryName):
                partes.append(nombre.value.rfc4514_string())
            elif isinstance(nombre, x509.OtherName):
                partes.append(nombre.value.decode("utf-8", errors="ignore"))
            elif isinstance(nombre, x509.RFC822Name | x509.UniformResourceIdentifier):
                partes.append(nombre.value)
        return " ".join(partes)

    def _textos_con_posible_ruc(self) -> tuple[str, str]:
        """Los dos lugares donde el manual admite el RUC, en orden."""
        return (self._texto_del_subject(), self._texto_del_san())

    def __repr__(self) -> str:
        """Representación con titular y vigencia, sin volcar el certificado."""
        return (
            f"Certificado(titular={self.titular!r}, ruc={self.ruc!r}, "
            f"vence={self.valido_hasta:%d/%m/%Y})"
        )


def _atributo(nombre: x509.Name, oid: x509.ObjectIdentifier) -> str | None:
    """Devuelve el primer valor textual de un atributo de un nombre X.509.

    Vive a nivel de módulo a propósito: dentro de :class:`Certificado` el campo
    ``x509`` sombrea al módulo homónimo y las anotaciones no resolverían.
    """
    for atributo in nombre.get_attributes_for_oid(oid):
        if isinstance(atributo.value, str):
            return atributo.value
    return None
