"""Firma con un archivo PKCS#12, o sea un certificado de tipo F1.

Es el nivel de custodia **más bajo** de los que soporta la librería: la clave
privada existe como archivo y se carga en memoria. Quien obtenga el ``.p12`` y
su contraseña puede emitir documentos tributarios a nombre del contribuyente.

Por eso este backend exige que el usuario declare de forma explícita que acepta
esa exposición. La fricción es deliberada: ver ``docs/seguridad/custodia.md``.

Para producción con volumen conviene un F2 con PKCS#11, donde la clave no sale
del dispositivo, o un F3 de firma remota, donde nunca estuvo del lado del
contribuyente.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12

from pysifen.exceptions import ConfiguracionError, FirmaError
from pysifen.pki.certificado import Certificado
from pysifen.signing.ports import NivelDeCustodia

if TYPE_CHECKING:  # pragma: no cover
    from pysifen.security.secretos import Secreto

__all__ = ["AvisoDeCustodia", "FirmantePkcs12"]


class AvisoDeCustodia(UserWarning):
    """Avisa que se está usando el nivel de custodia más expuesto."""


_EXPLICACION = (
    "Cargar la clave privada desde un archivo PKCS#12 la deja expuesta: quien "
    "obtenga el archivo y su contraseña puede emitir documentos tributarios a "
    "nombre del contribuyente. Si entendés y aceptás esa exposición, pasá "
    "permitir_clave_en_disco=True. Si podés evitarlo, usá un certificado F2 "
    "con PKCS#11, donde la clave no sale del dispositivo, o un F3 de firma "
    "remota. Ver docs/seguridad/custodia.md."
)


class FirmantePkcs12:
    """Firmante que usa la clave privada de un archivo PKCS#12.

    Cumple el protocolo :class:`~pysifen.signing.ports.Firmante`.

    La clave queda encapsulada y no se expone: no hay atributo público que la
    devuelva, ni aparece en el ``repr``.
    """

    __slots__ = ("_certificado", "_clave")

    def __init__(
        self,
        clave: rsa.RSAPrivateKey,
        certificado: Certificado,
    ) -> None:
        """Construye el firmante a partir de una clave ya cargada.

        Normalmente no se llama de forma directa: usar :meth:`desde_archivo` o
        :meth:`desde_bytes`.

        Args:
            clave: la clave privada RSA.
            certificado: el certificado correspondiente.
        """
        self._clave = clave
        self._certificado = certificado

    @classmethod
    def desde_bytes(
        cls,
        datos: bytes,
        contrasena: Secreto,
        *,
        permitir_clave_en_memoria: bool = False,
    ) -> FirmantePkcs12:
        """Carga un PKCS#12 que ya está en memoria.

        Args:
            datos: contenido del ``.p12``.
            contrasena: la contraseña del keystore, envuelta en
                :class:`~pysifen.security.secretos.Secreto`.
            permitir_clave_en_memoria: hay que pasarlo en ``True`` de forma
                explícita para aceptar el nivel de custodia.

        Returns:
            El firmante listo para usar.

        Raises:
            ConfiguracionError: si no se declaró la aceptación explícita.
            FirmaError: si el archivo no se puede abrir, la contraseña no sirve,
                o el contenido no trae clave RSA y certificado.
        """
        if not permitir_clave_en_memoria:
            raise ConfiguracionError(_EXPLICACION)

        try:
            clave, certificado, _ = pkcs12.load_key_and_certificates(
                datos, contrasena.revelar().encode()
            )
        except Exception:
            # El mensaje de la excepción original puede traer detalles del
            # keystore. Se corta la cadena con `from None` para que no llegue a
            # un log por accidente.
            raise FirmaError(
                "no pude abrir el PKCS#12: el archivo está dañado o la "
                "contraseña no corresponde"
            ) from None

        if certificado is None:
            raise FirmaError("el PKCS#12 no contiene ningún certificado")
        if not isinstance(clave, rsa.RSAPrivateKey):
            raise FirmaError(
                "el PKCS#12 no contiene una clave RSA; el apartado 7.7 del "
                "Manual Técnico exige RSA"
            )

        warnings.warn(
            "Firmando con la clave privada cargada en memoria desde un "
            "PKCS#12. Es el nivel de custodia más expuesto.",
            AvisoDeCustodia,
            stacklevel=2,
        )

        return cls(clave, Certificado(certificado))

    @classmethod
    def desde_archivo(
        cls,
        ruta: str | Path,
        contrasena: Secreto,
        *,
        permitir_clave_en_disco: bool = False,
    ) -> FirmantePkcs12:
        """Carga un PKCS#12 desde el sistema de archivos.

        Args:
            ruta: ubicación del ``.p12`` o ``.pfx``.
            contrasena: la contraseña del keystore.
            permitir_clave_en_disco: hay que pasarlo en ``True`` de forma
                explícita para aceptar el nivel de custodia.

        Returns:
            El firmante listo para usar.

        Raises:
            ConfiguracionError: si no se declaró la aceptación explícita.
            FirmaError: si el archivo no existe o no se puede abrir.
        """
        if not permitir_clave_en_disco:
            raise ConfiguracionError(_EXPLICACION)

        camino = Path(ruta)
        try:
            datos = camino.read_bytes()
        except OSError as exc:
            raise FirmaError(f"no pude abrir {camino}: {exc}") from exc

        return cls.desde_bytes(datos, contrasena, permitir_clave_en_memoria=True)

    @property
    def certificado(self) -> Certificado:
        """El certificado del contribuyente. Sólo la parte pública."""
        return self._certificado

    @property
    def nivel_de_custodia(self) -> NivelDeCustodia:
        """La clave está en memoria: es el nivel más expuesto."""
        return NivelDeCustodia.CLAVE_EN_MEMORIA

    def firmar(self, datos: bytes) -> bytes:
        """Firma bytes con RSA PKCS#1 v1.5 y SHA-256.

        Args:
            datos: los bytes a firmar, ya canonicalizados por quien llama.

        Returns:
            La firma en crudo.

        Raises:
            FirmaError: si la operación criptográfica falla.
        """
        try:
            return self._clave.sign(datos, padding.PKCS1v15(), hashes.SHA256())
        except Exception as exc:
            raise FirmaError(f"falló la operación de firma: {exc}") from exc

    def __repr__(self) -> str:
        """Representación que no revela nada de la clave privada."""
        return f"FirmantePkcs12(titular={self._certificado.titular!r})"

    def __getstate__(self) -> object:
        """Impide serializar el firmante junto con su clave.

        Raises:
            TypeError: siempre.
        """
        raise TypeError("un firmante no se puede serializar")
