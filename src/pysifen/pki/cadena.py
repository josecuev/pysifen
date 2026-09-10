"""Cadena de confianza: de un certificado hasta la Autoridad Certificadora Raíz.

Esto es lo que convierte "el certificado dice ser de DOCUMENTA" en "el
certificado **es** de DOCUMENTA". Comparar el nombre del emisor contra una lista
no prueba nada: ese nombre es texto que cualquiera escribe en un certificado
autofirmado. Lo que prueba es que la firma del emisor sobre el certificado
verifique, y así hasta llegar a una raíz reconocida.

De dónde salen las anclas de confianza
--------------------------------------

De la **Lista de Confianza (TSL)** que publica el Ministerio de Industria y
Comercio en ``https://www.acraiz.gov.py/tsl/tsl_Py.xml``, en el formato
ETSI TS 119 612. Es la fuente oficial: el MIC administra la Autoridad
Certificadora Raíz del Paraguay y la ley obliga a que los prestadores
cualificados publiquen su cadena.

La lista trae, por cada prestador, los certificados de sus autoridades
certificadoras y el **estado de cada servicio**. Un servicio en estado
``granted`` está habilitado; cualquier otro estado no lo está, y esta librería
lo trata como no confiable.

Que el prestador salga de ahí y no de una lista escrita a mano tiene una
consecuencia buena: cuando el MIC habilita a un prestador nuevo o le retira la
habilitación a uno, se refleja al actualizar la lista, sin tocar código.

No toda la lista sirve acá
--------------------------

La lista trae **más de una jerarquía**, y no todas firman documentos
tributarios:

- ``QC`` bajo la **Autoridad Certificadora Raíz del Paraguay**: certificados
  cualificados de firma. Es la jerarquía del SIFEN, y la única que esta
  librería acepta.
- ``PKC`` bajo la **AC RAIZ MITIC**: otra raíz, la de la firma de funcionarios
  públicos. No emite certificados de facturación electrónica.
- ``QTST``: autoridades de sello de tiempo. Sellan, no firman documentos.

Aceptar cualquiera de las tres sería aceptar de más: un certificado de
funcionario público encadena perfecto contra su raíz y no por eso habilita a
nadie a facturar. Por eso :data:`SERVICIOS_TRIBUTARIOS` acota las anclas, y la
cadena tiene que terminar en la Raíz del Paraguay.

Qué no se hace acá
------------------

No se consulta la lista de certificados revocados. Es la única comprobación que
necesita red, así que va aparte y nunca por omisión.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Final

from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from lxml import etree

from pysifen.exceptions import PkiError
from pysifen.pki.certificado import Certificado
from pysifen.tiempo import ahora, con_zona

__all__ = [
    "ARCHIVO_DE_LA_LISTA",
    "ESTADO_HABILITADO",
    "SERVICIOS_TRIBUTARIOS",
    "URL_DE_LA_LISTA",
    "Autoridad",
    "ListaDeConfianza",
    "ResultadoDeCadena",
    "lista_de_confianza",
    "validar_cadena",
]

#: Espacio de nombres del formato ETSI TS 119 612.
_TSL: Final = "{http://uri.etsi.org/02231/v2#}"

#: Dónde publica el MIC la lista de confianza.
URL_DE_LA_LISTA: Final = "https://www.acraiz.gov.py/tsl/tsl_Py.xml"

#: La copia que viaja con la librería.
ARCHIVO_DE_LA_LISTA: Final = Path(__file__).parent.parent / "confianza" / "tsl_Py.xml"

#: Estado de un servicio habilitado, en la nomenclatura de la TSL.
ESTADO_HABILITADO: Final = "granted"

#: Estados que la lista usa para una raíz nacional reconocida.
_ESTADOS_DE_RAIZ: Final = frozenset({"recognisedatnationallevel"})

#: Los servicios de la lista que sirven para firmar documentos tributarios.
#:
#: ``QC`` son los certificados cualificados de firma y ``NationalRootCA-QC`` es
#: la raíz que los ancla. Queda afuera a propósito la jerarquía ``PKC`` de la AC
#: RAIZ MITIC —firma de funcionarios públicos, otra raíz y otro propósito— y los
#: servicios ``QTST`` de sello de tiempo.
SERVICIOS_TRIBUTARIOS: Final = frozenset({"QC", "NationalRootCA-QC"})

#: Hasta dónde seguir buscando emisores antes de darse por vencido.
_PROFUNDIDAD_MAXIMA: Final = 8


@dataclass(frozen=True, slots=True)
class Autoridad:
    """Una autoridad certificadora tal como la declara la lista de confianza.

    Attributes:
        prestador: nombre del prestador que la opera, según la lista.
        certificado: el certificado de la autoridad.
        estado: estado del servicio en la lista. ``granted`` es habilitado.
        tipo_de_servicio: qué presta, por ejemplo ``QC`` para certificados
            cualificados o ``QTST`` para sellos de tiempo.
    """

    prestador: str
    certificado: x509.Certificate
    estado: str
    tipo_de_servicio: str

    @property
    def habilitada(self) -> bool:
        """``True`` si el servicio está habilitado o es una raíz reconocida."""
        return self.estado in {ESTADO_HABILITADO, *_ESTADOS_DE_RAIZ}

    @property
    def es_raiz(self) -> bool:
        """``True`` si el certificado es autofirmado."""
        return self.certificado.subject == self.certificado.issuer


@dataclass(frozen=True, slots=True)
class ResultadoDeCadena:
    """Lo que se pudo determinar sobre la cadena de un certificado.

    Attributes:
        valida: si la cadena llega hasta una raíz reconocida, con cada eslabón
            firmado por el siguiente.
        prestador: el prestador que emitió el certificado, según la lista. Es
            el dato autoritativo, no el nombre que el certificado declara.
        cadena: los nombres de los eslabones, de la hoja a la raíz.
        habilitado_al_firmar: si el servicio del prestador estaba habilitado.
        motivo: por qué no se pudo completar, cuando no se pudo.
    """

    valida: bool
    prestador: str | None = None
    cadena: tuple[str, ...] = field(default_factory=tuple)
    habilitado_al_firmar: bool | None = None
    motivo: str | None = None


class ListaDeConfianza:
    """Las autoridades certificadoras reconocidas por el MIC.

    Se construye desde la copia de la lista que viaja con la librería.
    """

    def __init__(self, autoridades: list[Autoridad]) -> None:
        self._autoridades = autoridades
        self._por_sujeto: dict[str, list[Autoridad]] = {}
        for autoridad in autoridades:
            clave = autoridad.certificado.subject.rfc4514_string()
            self._por_sujeto.setdefault(clave, []).append(autoridad)

    @classmethod
    def desde_archivo(cls, ruta: Path | None = None) -> ListaDeConfianza:
        """Lee la lista de confianza desde un archivo en formato ETSI.

        Args:
            ruta: la lista a leer. Por omisión, la que trae la librería.

        Returns:
            La lista, con todas sus autoridades.

        Raises:
            PkiError: si el archivo no existe o no se puede interpretar.
        """
        archivo = ruta or ARCHIVO_DE_LA_LISTA
        try:
            analizador = etree.XMLParser(resolve_entities=False, no_network=True)
            raiz = etree.parse(str(archivo), parser=analizador).getroot()
        except (OSError, etree.XMLSyntaxError) as exc:
            raise PkiError(f"no pude leer la lista de confianza: {exc}") from exc

        autoridades: list[Autoridad] = []
        for proveedor in raiz.iter(f"{_TSL}TrustServiceProvider"):
            nombre = proveedor.findtext(
                f"{_TSL}TSPInformation/{_TSL}TSPName/{_TSL}Name"
            )
            for servicio in proveedor.iter(f"{_TSL}TSPService"):
                informacion = servicio.find(f"{_TSL}ServiceInformation")
                if informacion is None:
                    continue
                estado = (informacion.findtext(f"{_TSL}ServiceStatus") or "").rsplit(
                    "/", 1
                )[-1]
                tipo = (
                    informacion.findtext(f"{_TSL}ServiceTypeIdentifier") or ""
                ).rsplit("/", 1)[-1]
                for nodo in informacion.iter(f"{_TSL}X509Certificate"):
                    if not nodo.text:
                        continue
                    try:
                        certificado = x509.load_der_x509_certificate(
                            base64.b64decode(nodo.text)
                        )
                    except (ValueError, TypeError, binascii.Error):
                        # Un certificado ilegible en la lista no invalida los
                        # demas: se omite y se sigue.
                        continue
                    autoridades.append(
                        Autoridad(
                            prestador=nombre or "?",
                            certificado=certificado,
                            estado=estado,
                            tipo_de_servicio=tipo,
                        )
                    )
        if not autoridades:
            raise PkiError("la lista de confianza no trae ninguna autoridad")
        return cls(autoridades)

    def emisores_de(
        self,
        certificado: x509.Certificate,
        tipos: frozenset[str] | None = None,
    ) -> list[Autoridad]:
        """Devuelve las autoridades cuyo sujeto coincide con el emisor.

        Args:
            certificado: el certificado cuyo emisor se busca.
            tipos: si se pasa, sólo se consideran los servicios de esos tipos.
                Ver :data:`SERVICIOS_TRIBUTARIOS`.
        """
        candidatas = self._por_sujeto.get(certificado.issuer.rfc4514_string(), [])
        if tipos is None:
            return candidatas
        return [a for a in candidatas if a.tipo_de_servicio in tipos]

    def __len__(self) -> int:
        """Cantidad de autoridades en la lista."""
        return len(self._autoridades)

    def __iter__(self) -> Iterator[Autoridad]:
        """Recorre las autoridades."""
        return iter(self._autoridades)

    def __repr__(self) -> str:
        """Representación con la cantidad de autoridades."""
        return f"ListaDeConfianza({len(self)} autoridades)"


@lru_cache(maxsize=1)
def lista_de_confianza() -> ListaDeConfianza:
    """Devuelve la lista de confianza que trae la librería, ya interpretada.

    Se lee una sola vez y se reutiliza.
    """
    return ListaDeConfianza.desde_archivo()


def _nombre(sujeto: x509.Name) -> str:
    """Devuelve el nombre común de un sujeto, o su forma completa."""
    for atributo in sujeto:
        if atributo.oid._name == "commonName" and isinstance(atributo.value, str):
            return atributo.value
    return sujeto.rfc4514_string()


def validar_cadena(
    certificado: Certificado,
    *,
    lista: ListaDeConfianza | None = None,
    momento: datetime | None = None,
    servicios: frozenset[str] = SERVICIOS_TRIBUTARIOS,
) -> ResultadoDeCadena:
    """Construye y valida la cadena de un certificado hasta una raíz reconocida.

    En cada eslabón se comprueba que el certificado esté **realmente firmado**
    por el siguiente, no que los nombres coincidan.

    Args:
        certificado: el certificado a validar, normalmente el que viene dentro
            de un documento recibido.
        lista: las anclas de confianza. Por omisión, la lista que trae la
            librería.
        momento: instante para evaluar la vigencia de las autoridades. Por
            omisión, ahora. Para un documento recibido conviene pasar la fecha
            de su firma.
        servicios: qué servicios de la lista se aceptan como anclas. Por
            omisión, sólo los que firman documentos tributarios.

    Returns:
        El resultado, con la cadena encontrada y el prestador autoritativo.

    Example:
        >>> resultado = validar_cadena(certificado)  # doctest: +SKIP
        >>> resultado.valida, resultado.prestador  # doctest: +SKIP
        (True, 'Documenta SA')
    """
    anclas = lista or lista_de_confianza()
    instante = con_zona(momento) if momento else ahora()

    cadena = [_nombre(certificado.x509.subject)]
    actual = certificado.x509
    prestador: str | None = None
    habilitado: bool | None = None

    for _ in range(_PROFUNDIDAD_MAXIMA):
        emisor = _buscar_emisor(actual, anclas, servicios)
        if emisor is None:
            return ResultadoDeCadena(
                valida=False,
                prestador=prestador,
                cadena=tuple(cadena),
                habilitado_al_firmar=habilitado,
                motivo=(
                    f"no encontré, entre las autoridades que la lista habilita "
                    f"para documentos tributarios, ninguna que haya firmado "
                    f"{_nombre(actual.subject)!r}"
                ),
            )

        if prestador is None:
            prestador = emisor.prestador
            habilitado = emisor.habilitada

        cadena.append(_nombre(emisor.certificado.subject))

        if not emisor.habilitada:
            return ResultadoDeCadena(
                valida=False,
                prestador=prestador,
                cadena=tuple(cadena),
                habilitado_al_firmar=False,
                motivo=(
                    f"el servicio de {emisor.prestador} figura en la lista con "
                    f"estado {emisor.estado!r}, que no es habilitado"
                ),
            )

        if not _vigente(emisor.certificado, instante):
            return ResultadoDeCadena(
                valida=False,
                prestador=prestador,
                cadena=tuple(cadena),
                habilitado_al_firmar=habilitado,
                motivo=(
                    f"el certificado de {_nombre(emisor.certificado.subject)} no "
                    f"estaba vigente en el momento evaluado"
                ),
            )

        if emisor.es_raiz:
            return ResultadoDeCadena(
                valida=True,
                prestador=prestador,
                cadena=tuple(cadena),
                habilitado_al_firmar=habilitado,
            )

        actual = emisor.certificado

    return ResultadoDeCadena(
        valida=False,
        prestador=prestador,
        cadena=tuple(cadena),
        habilitado_al_firmar=habilitado,
        motivo="la cadena es más larga de lo razonable; se cortó la búsqueda",
    )


def _buscar_emisor(
    certificado: x509.Certificate,
    anclas: ListaDeConfianza,
    servicios: frozenset[str] | None = None,
) -> Autoridad | None:
    """Encuentra la autoridad que firmó el certificado, comprobando la firma."""
    for candidata in anclas.emisores_de(certificado, servicios):
        try:
            certificado.verify_directly_issued_by(candidata.certificado)
        except (InvalidSignature, UnsupportedAlgorithm, ValueError, TypeError):
            # No lo firmo esta: se prueba con la siguiente que tenga el mismo
            # nombre. Que dos autoridades compartan nombre es normal cuando una
            # renueva su certificado.
            continue
        return candidata
    return None


def _vigente(certificado: x509.Certificate, momento: datetime) -> bool:
    """Indica si un certificado estaba vigente en un momento dado."""
    return (
        certificado.not_valid_before_utc <= momento <= certificado.not_valid_after_utc
    )
