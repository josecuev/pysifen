"""Código bidimensional (QR) del KuDE.

Implementa el apartado 13.8 del Manual Técnico SIFEN v150.

El QR permite verificar un documento contra el portal de la Administración
Tributaria aun cuando el documento todavía no haya sido transmitido al SIFEN. Su
autenticidad descansa en un hash SHA-256 calculado sobre los parámetros del
documento **más el Código de Seguridad del Contribuyente (CSC)**, que es un
secreto compartido entre el contribuyente y la DNIT.

.. warning::
   El CSC participa del hash y **nunca** viaja en la URL. El manual es explícito:
   *"Por ningún motivo el contribuyente debe compartir su código de seguridad, ni
   enviar concatenado como parte de la URL del código QR"*. Por eso esta API
   recibe el CSC como :class:`~pysifen.security.secretos.Secreto` y no como
   ``str``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final

from pysifen.enums import Ambiente
from pysifen.exceptions import ValidacionError
from pysifen.security.secretos import Secreto

__all__ = [
    "ANCHO_MINIMO_MM",
    "URL_BASE",
    "DatosQr",
    "generar_url_qr",
]

#: URL de consulta del QR por ambiente (13.8.2).
URL_BASE: Final[dict[Ambiente, str]] = {
    Ambiente.PRODUCCION: "https://ekuatia.set.gov.py/consultas/qr?",
    Ambiente.TEST: "https://ekuatia.set.gov.py/consultas-test/qr?",
}

#: Ancho mínimo de impresión en milímetros: 22 de contenido más 3 de margen
#: seguro a cada lado (13.8.1).
ANCHO_MINIMO_MM: Final = 25


def _a_hexadecimal(texto: str) -> str:
    """Convierte un texto a su equivalente hexadecimal.

    El manual exige esta conversión para la fecha de emisión y para el
    ``DigestValue`` de la firma (13.8.3).

    Example:
        >>> _a_hexadecimal("2017-01-25T09:35:17")
        '323031372d30312d32355430393a33353a3137'
    """
    return texto.encode("utf-8").hex()


def _formatear_monto(valor: Decimal | float | int | str | None) -> str:
    """Formatea un importe para el QR, usando ``0`` cuando no hay valor.

    El manual indica que si ``dTotGralOpe`` o ``dTotIVA`` no se informan, se
    completa con cero (13.8.4.1).
    """
    if valor is None or valor == "":
        return "0"
    if isinstance(valor, Decimal):
        # Sin normalize: el importe tiene que salir tal como figura en el
        # DE, porque es sobre esa cadena que el SIFEN recalcula el hash.
        return format(valor, "f")
    return str(valor)


@dataclass(frozen=True, slots=True)
class DatosQr:
    """Parámetros del documento que componen el QR (13.8.2).

    Attributes:
        cdc: Código de Control del documento, campo ``A002``.
        fecha_emision: fecha y hora de emisión, campo ``D002``. Se acepta un
            :class:`~datetime.datetime` o el texto ya en formato
            ``AAAA-MM-DDThh:mm:ss``.
        digest_value: ``DigestValue`` de la firma digital, campo ``XS17``, tal
            como quedó en el XML, en base64.
        id_csc: identificador del CSC entregado por el SIFEN, cuatro dígitos.
        identificador_receptor: RUC del receptor (``dRucRec``, campo ``D206``) o
            número de identidad (``dNumIDRec``, campo ``D210``), según
            corresponda. ``None`` si el receptor es innominado.
        receptor_con_ruc: ``True`` si ``identificador_receptor`` es un RUC. Fija
            el nombre del parámetro en la URL.
        total_general: total general de la operación, campo ``F014``.
        total_iva: liquidación total del IVA, campo ``F017``.
        cantidad_items: cantidad de ocurrencias del campo ``E701``.
        version: versión del formato, campo ``dVerFor``.
    """

    cdc: str
    fecha_emision: datetime | str
    digest_value: str
    id_csc: str
    identificador_receptor: str | None = None
    receptor_con_ruc: bool = True
    total_general: Decimal | float | int | str | None = None
    total_iva: Decimal | float | int | str | None = None
    cantidad_items: int = 0
    version: int = 150

    def _fecha_iso(self) -> str:
        """Devuelve la fecha de emisión en ``AAAA-MM-DDThh:mm:ss``."""
        if isinstance(self.fecha_emision, datetime):
            return self.fecha_emision.isoformat(timespec="seconds")
        return self.fecha_emision

    def parametros(self) -> list[tuple[str, str]]:
        """Arma los parámetros en el orden exacto que fija el manual.

        Returns:
            Pares ``(nombre, valor)`` listos para concatenar. La fecha de
            emisión y el ``DigestValue`` ya vienen en hexadecimal.
        """
        nombre_receptor = "dRucRec" if self.receptor_con_ruc else "dNumIDRec"
        return [
            ("nVersion", str(self.version)),
            ("Id", self.cdc),
            ("dFeEmiDE", _a_hexadecimal(self._fecha_iso())),
            (nombre_receptor, self.identificador_receptor or "0"),
            ("dTotGralOpe", _formatear_monto(self.total_general)),
            ("dTotIVA", _formatear_monto(self.total_iva)),
            ("cItems", str(self.cantidad_items)),
            ("DigestValue", _a_hexadecimal(self.digest_value)),
            ("IdCSC", self.id_csc),
        ]

    def cadena_parametros(self) -> str:
        """Concatena los parámetros como ``clave=valor`` unidos por ``&``.

        Es el paso 1 del apartado 13.8.4.
        """
        return "&".join(f"{clave}={valor}" for clave, valor in self.parametros())


def generar_url_qr(
    datos: DatosQr,
    csc: Secreto,
    *,
    ambiente: Ambiente = Ambiente.PRODUCCION,
) -> str:
    """Arma la URL completa del QR, con su hash de autenticidad.

    Sigue los cuatro pasos del apartado 13.8.4:

    1. Concatenar los parámetros del documento.
    2. Concatenar el CSC al final de esa cadena.
    3. Calcular SHA-256 sobre el resultado y expresarlo en hexadecimal.
    4. Publicar la URL con los parámetros del paso 1 más ``cHashQR``.

    El CSC interviene sólo en el paso 2 y no aparece en la URL resultante.

    Args:
        datos: parámetros del documento.
        csc: Código de Seguridad del Contribuyente correspondiente a
            ``datos.id_csc``.
        ambiente: define la URL base de consulta.

    Returns:
        La URL a codificar en el QR.

    Raises:
        ValidacionError: si falta el CDC, el ``DigestValue`` o el ``IdCSC``.
    """
    if not datos.cdc:
        raise ValidacionError("el QR necesita el CDC del documento", campo="A002")
    if not datos.digest_value:
        raise ValidacionError(
            "el QR necesita el DigestValue de la firma; hay que firmar el "
            "documento antes de generar el QR",
            campo="XS17",
        )
    if not datos.id_csc:
        raise ValidacionError("el QR necesita el IdCSC", campo="IdCSC")

    cadena = datos.cadena_parametros()
    hash_qr = hashlib.sha256(f"{cadena}{csc.revelar()}".encode()).hexdigest()

    return f"{URL_BASE[ambiente]}{cadena}&cHashQR={hash_qr}"
