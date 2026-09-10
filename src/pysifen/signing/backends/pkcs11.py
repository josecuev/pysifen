"""Firma con la clave dentro de un token o HSM, o sea un certificado F2.

La clave se genera dentro del dispositivo y está marcada como no exportable. El
dispositivo firma; la clave no sale. Si el servidor se ve comprometido, lo que
se pierde es el acceso a firmar mientras dure el compromiso, no la clave.

Requiere el extra ``pkcs11``:

.. code-block:: bash

   pip install "pysifen[pkcs11]"

Y el módulo PKCS#11 del fabricante del token, que es un ``.so`` o ``.dll`` que
se instala aparte. La ruta de ese módulo es el primer argumento.

.. note::
   Este backend no se puede ejercitar en integración continua sin un
   dispositivo. Sus tests están marcados con ``@pytest.mark.certificado`` y
   quedan fuera de la corrida por omisión. Lo que sí se verifica siempre es que
   respeta el contrato del puerto y que no expone material de clave.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pysifen.exceptions import ConfiguracionError, FirmaError
from pysifen.pki.certificado import Certificado
from pysifen.signing.ports import NivelDeCustodia

if TYPE_CHECKING:  # pragma: no cover
    from pysifen.security.secretos import Secreto

__all__ = ["FirmantePkcs11"]

_FALTA_LA_DEPENDENCIA = (
    "Para firmar con un token o HSM hace falta el extra pkcs11: "
    'pip install "pysifen[pkcs11]"'
)


class FirmantePkcs11:
    """Firmante que delega la operación en un token o HSM vía PKCS#11.

    Cumple el protocolo :class:`~pysifen.signing.ports.Firmante`.

    La sesión con el dispositivo queda abierta mientras viva el firmante. Se
    puede usar como gestor de contexto para cerrarla de forma determinista.

    Example:
        >>> with FirmantePkcs11.abrir(  # doctest: +SKIP
        ...     modulo="/usr/lib/libeToken.so",
        ...     pin=Secreto("...", nombre="PIN del token"),
        ...     etiqueta_token="MI TOKEN",
        ... ) as firmante:
        ...     firmado = firmar_documento(xml, firmante)
    """

    __slots__ = ("_certificado", "_clave", "_sesion")

    def __init__(
        self,
        sesion: Any,
        clave: Any,
        certificado: Certificado,
    ) -> None:
        """Construye el firmante sobre una sesión ya abierta.

        Normalmente no se llama de forma directa: usar :meth:`abrir`.

        Args:
            sesion: la sesión PKCS#11 abierta.
            clave: el objeto de clave privada dentro del dispositivo. Es un
                *handle*, no material de clave.
            certificado: el certificado correspondiente.
        """
        self._sesion = sesion
        self._clave = clave
        self._certificado = certificado

    @classmethod
    def abrir(
        cls,
        modulo: str,
        pin: Secreto,
        *,
        etiqueta_token: str | None = None,
        etiqueta_clave: str | None = None,
    ) -> FirmantePkcs11:
        """Abre una sesión con el dispositivo y ubica la clave y el certificado.

        Args:
            modulo: ruta del módulo PKCS#11 del fabricante (``.so`` o ``.dll``).
            pin: PIN del token, envuelto en
                :class:`~pysifen.security.secretos.Secreto`.
            etiqueta_token: etiqueta del token, si hay más de uno conectado.
            etiqueta_clave: etiqueta de la clave dentro del token, si hay más de
                una.

        Returns:
            El firmante listo para usar.

        Raises:
            ConfiguracionError: si falta el extra ``pkcs11``.
            FirmaError: si no se puede abrir el dispositivo, el PIN no sirve, o
                no se encuentra la clave o el certificado.
        """
        try:
            import pkcs11
            from pkcs11 import ObjectClass
        except ImportError as exc:
            raise ConfiguracionError(_FALTA_LA_DEPENDENCIA) from exc

        try:
            biblioteca = pkcs11.lib(modulo)
            token = (
                biblioteca.get_token(token_label=etiqueta_token)
                if etiqueta_token
                else next(iter(biblioteca.get_tokens()))
            )
            sesion = token.open(user_pin=pin.revelar())
        except StopIteration:
            raise FirmaError(
                "no encontré ningún token conectado en el módulo indicado"
            ) from None
        except Exception:
            # El detalle del error puede incluir el PIN en algunos módulos.
            raise FirmaError(
                "no pude abrir sesión con el dispositivo: revisá la ruta del "
                "módulo, la etiqueta del token y el PIN"
            ) from None

        try:
            filtros: dict[str, Any] = {"object_class": ObjectClass.PRIVATE_KEY}
            if etiqueta_clave:
                filtros["label"] = etiqueta_clave
            clave = sesion.get_key(**filtros)

            filtros_cert: dict[str, Any] = {"object_class": ObjectClass.CERTIFICATE}
            if etiqueta_clave:
                filtros_cert["label"] = etiqueta_clave
            objeto = next(iter(sesion.get_objects(filtros_cert)))
            certificado = Certificado.desde_der(bytes(objeto[pkcs11.Attribute.VALUE]))
        except Exception as exc:
            sesion.close()
            raise FirmaError(
                f"no encontré la clave o el certificado en el dispositivo: {exc}"
            ) from exc

        return cls(sesion, clave, certificado)

    @property
    def certificado(self) -> Certificado:
        """El certificado del contribuyente. Sólo la parte pública."""
        return self._certificado

    @property
    def nivel_de_custodia(self) -> NivelDeCustodia:
        """La clave no sale del dispositivo."""
        return NivelDeCustodia.CLAVE_EN_DISPOSITIVO

    def firmar(self, datos: bytes) -> bytes:
        """Pide al dispositivo que firme los bytes con RSA y SHA-256.

        El resumen lo calcula el propio dispositivo: los bytes se le entregan
        enteros y el mecanismo ``SHA256_RSA_PKCS`` se encarga del resto.

        Args:
            datos: los bytes a firmar, ya canonicalizados por quien llama.

        Returns:
            La firma en crudo.

        Raises:
            FirmaError: si el dispositivo rechaza la operación.
        """
        try:
            import pkcs11
        except ImportError as exc:  # pragma: no cover - ya se validó al abrir
            raise ConfiguracionError(_FALTA_LA_DEPENDENCIA) from exc

        try:
            return bytes(
                self._clave.sign(datos, mechanism=pkcs11.Mechanism.SHA256_RSA_PKCS)
            )
        except Exception as exc:
            raise FirmaError(f"el dispositivo rechazó la firma: {exc}") from exc

    def cerrar(self) -> None:
        """Cierra la sesión con el dispositivo."""
        if self._sesion is not None:
            self._sesion.close()

    def __enter__(self) -> FirmantePkcs11:
        """Permite usarlo como gestor de contexto."""
        return self

    def __exit__(self, *_: object) -> None:
        """Cierra la sesión al salir del bloque."""
        self.cerrar()

    def __repr__(self) -> str:
        """Representación que no revela nada del dispositivo ni de la clave."""
        return f"FirmantePkcs11(titular={self._certificado.titular!r})"

    def __getstate__(self) -> object:
        """Impide serializar el firmante.

        Raises:
            TypeError: siempre.
        """
        raise TypeError("un firmante no se puede serializar")
