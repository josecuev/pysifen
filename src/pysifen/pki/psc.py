"""Prestadores cualificados de servicios de confianza.

En el Paraguay los certificados digitales los emiten prestadores habilitados por
el Ministerio de Industria y Comercio, en su carácter de administrador de la
Autoridad Certificadora Raíz. El Manual Técnico SIFEN v150 (§7.5) exige que el
certificado del contribuyente provenga de uno de ellos.

El marco vigente es la **Ley n.° 6822/2021** de servicios de confianza y su
Decreto n.° 7576/2022, que es la que define la figura de *prestador cualificado*.
El manual todavía cita la Ley 4017/2010, anterior.

Diseño
------

La lista de prestadores cambia: entre 2014 y 2025 se habilitaron siete, y se
seguirán habilitando. Por eso acá no hay una cadena de ``if``: hay un protocolo
:class:`PrestadorCualificado` y un :class:`RegistroDePrestadores` que los
descubre por *entry points*.

Agregar un prestador nuevo no requiere modificar este módulo ni ningún otro del
núcleo. Alcanza con publicar una clase que cumpla el protocolo y declararla en
el grupo ``pysifen.psc`` del ``pyproject.toml``, sea en esta librería o en un
paquete de terceros.

Esto **no** decide en quién confiar
------------------------------------

Importa no confundirse: lo que hay acá son *datos* sobre los prestadores —cómo
se llaman, qué tipos de certificado emiten, dónde publican sus servicios—. Nada
de eso prueba nada sobre un certificado concreto.

Identificar a un prestador comparando el nombre del emisor contra esta lista
**clasifica, no prueba**: ese nombre es texto que cualquiera escribe en un
certificado autofirmado. Quien decide si un certificado es de un prestador
cualificado habilitado es :mod:`pysifen.pki.cadena`, verificando la firma de
cada eslabón contra la Lista de Confianza oficial del MIC.

La utilidad de este registro es la otra: una vez que la cadena probó de quién
es el certificado, acá está lo que hay que saber sobre ese prestador. Es el
lugar natural para los puntos de consulta de revocación cuando se implementen.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover
    from pysifen.pki.certificado import Certificado

__all__ = [
    "GRUPO_ENTRY_POINTS",
    "DatosPrestador",
    "PrestadorCualificado",
    "PrestadorPorEmisor",
    "RegistroDePrestadores",
    "TipoCertificado",
]

#: Grupo de *entry points* donde se declaran los prestadores.
GRUPO_ENTRY_POINTS = "pysifen.psc"


class TipoCertificado(StrEnum):
    """Tipos de certificado que reconoce la Autoridad Certificadora Raíz.

    El Manual Técnico v150 (§7.5) contempla sólo F1 y F2. El F3 es posterior al
    manual: la firma que produce es igualmente XMLDSig válida, pero conviene
    confirmar con el prestador si el mismo certificado sirve para la
    autenticación mutua TLS que exige el apartado 7.9.
    """

    F1 = "F1"
    """Firma digital por software. El archivo ``.p12`` clásico."""

    F2 = "F2"
    """Firma digital por hardware. Token o HSM."""

    F3 = "F3"
    """Firma remota. La clave privada vive en el HSM del prestador."""

    @property
    def descripcion(self) -> str:
        """Descripción legible del tipo de certificado."""
        return {
            TipoCertificado.F1: "Firma digital por software",
            TipoCertificado.F2: "Firma digital por hardware",
            TipoCertificado.F3: "Firma digital remota",
        }[self]

    @property
    def clave_exportable(self) -> bool:
        """``True`` si la clave privada puede existir fuera de un dispositivo.

        Sólo el F1 tiene esa propiedad, y es la razón por la que exige el
        tratamiento de custodia más cuidadoso.
        """
        return self is TipoCertificado.F1


@dataclass(frozen=True, slots=True)
class DatosPrestador:
    """Datos de habilitación de un prestador.

    Attributes:
        identificador: nombre corto y estable, en minúsculas. Es el que se usa
            como clave del *entry point*.
        nombre: razón social tal como figura en el registro de la Autoridad
            Certificadora Raíz.
        resolucion: resolución del MIC que lo habilitó.
        tipos: tipos de certificado que está habilitado a emitir.
        sitio: sitio web publicado en el registro.
    """

    identificador: str
    nombre: str
    resolucion: str
    tipos: frozenset[TipoCertificado]
    sitio: str


@runtime_checkable
class PrestadorCualificado(Protocol):
    """Lo que la librería necesita saber de un prestador.

    El protocolo es deliberadamente chico: identificarse y decir si un
    certificado es suyo. Todo lo demás (validar vigencia, revisar la cadena,
    consultar revocación) es responsabilidad de otros módulos, que dependen de
    esta abstracción y no de un prestador concreto.
    """

    @property
    def datos(self) -> DatosPrestador:
        """Datos de habilitación del prestador."""
        ...

    def emitio(self, certificado: Certificado) -> bool:
        """Indica si el certificado fue emitido por este prestador.

        Args:
            certificado: el certificado a examinar.

        Returns:
            ``True`` si el emisor del certificado corresponde a este prestador.
        """
        ...


@dataclass(frozen=True, slots=True)
class PrestadorPorEmisor:
    """Prestador que se reconoce por el nombre de su emisor.

    Es la implementación base y alcanza para los prestadores del registro
    paraguayo, cuyos certificados llevan la razón social en el ``Issuer``. Un
    prestador con un criterio distinto puede implementar el protocolo por su
    cuenta sin heredar de acá.

    Attributes:
        datos: datos de habilitación.
        patrones: fragmentos que deben aparecer en el nombre del emisor. La
            comparación no distingue mayúsculas ni acentos. Basta con que
            coincida uno.
    """

    datos: DatosPrestador
    patrones: tuple[str, ...] = field(default=())

    def emitio(self, certificado: Certificado) -> bool:
        """Compara el emisor del certificado con los patrones del prestador."""
        emisor = _normalizar(certificado.emisor)
        if not emisor:
            return False
        return any(_normalizar(patron) in emisor for patron in self.patrones)


def _normalizar(texto: str) -> str:
    """Pasa a minúsculas, saca acentos y colapsa los espacios."""
    reemplazos = str.maketrans("áéíóúüñ", "aeiouun")
    return re.sub(r"\s+", " ", texto.lower().translate(reemplazos)).strip()


class RegistroDePrestadores:
    """Colección de prestadores conocidos.

    Se puede construir con una lista explícita, útil en tests, o descubrir los
    declarados por *entry points* con :meth:`desde_entry_points`.

    Example:
        >>> registro = RegistroDePrestadores.desde_entry_points()
        >>> len(registro) >= 7
        True
    """

    def __init__(self, prestadores: Iterable[PrestadorCualificado] = ()) -> None:
        self._prestadores: dict[str, PrestadorCualificado] = {}
        for prestador in prestadores:
            self.registrar(prestador)

    @classmethod
    def desde_entry_points(cls) -> RegistroDePrestadores:
        """Descubre los prestadores declarados en el grupo ``pysifen.psc``.

        Incluye los que declare cualquier paquete instalado, no sólo esta
        librería: así un tercero puede sumar un prestador sin tocar el núcleo.

        Returns:
            El registro con todos los prestadores encontrados.
        """
        registro = cls()
        for punto in entry_points(group=GRUPO_ENTRY_POINTS):
            fabrica = punto.load()
            registro.registrar(fabrica())
        return registro

    def registrar(self, prestador: PrestadorCualificado) -> None:
        """Agrega un prestador al registro.

        Args:
            prestador: cualquier objeto que cumpla el protocolo.

        Raises:
            ValueError: si ya hay uno con el mismo identificador.
        """
        identificador = prestador.datos.identificador
        if identificador in self._prestadores:
            raise ValueError(f"el prestador {identificador!r} ya está registrado")
        self._prestadores[identificador] = prestador

    def identificar(self, certificado: Certificado) -> PrestadorCualificado | None:
        """Busca al prestador que emitió un certificado.

        Args:
            certificado: el certificado a examinar.

        Returns:
            El prestador, o ``None`` si ninguno lo reconoce como propio. Un
            ``None`` no prueba que el certificado sea inválido: puede ser de un
            prestador habilitado después de esta versión de la librería.
        """
        for prestador in self._prestadores.values():
            if prestador.emitio(certificado):
                return prestador
        return None

    def obtener(self, identificador: str) -> PrestadorCualificado | None:
        """Devuelve un prestador por su identificador, o ``None``."""
        return self._prestadores.get(identificador)

    def __iter__(self) -> Iterator[PrestadorCualificado]:
        """Recorre los prestadores registrados."""
        return iter(self._prestadores.values())

    def __len__(self) -> int:
        """Cantidad de prestadores registrados."""
        return len(self._prestadores)

    def __contains__(self, identificador: object) -> bool:
        """Indica si hay un prestador con ese identificador."""
        return identificador in self._prestadores

    def __repr__(self) -> str:
        """Representación con la cantidad de prestadores."""
        return f"RegistroDePrestadores({len(self)} prestadores)"
