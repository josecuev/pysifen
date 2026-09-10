"""Lectura y verificación de documentos electrónicos recibidos.

El otro lado del negocio. Una empresa recibe muchos más documentos de los que
emite, y de cada uno necesita saber dos cosas: qué dice, y si se puede confiar
en él.

Para verificar **no hace falta ningún certificado propio ni estar habilitado
como facturador**: el documento trae adentro el certificado de quien lo firmó.

Qué se comprueba
----------------

=========================  =========================================
Comprobación               Qué detecta
=========================  =========================================
Esquema                    Un documento mal formado o incompleto
Firma                      Cualquier alteración del contenido firmado
Prestador cualificado      Un certificado de origen desconocido
Vigencia a la firma        Un certificado vencido *cuando se firmó*
RUC del certificado        Un documento firmado por otro contribuyente
Coherencia del CDC         Un CDC inventado o mal calculado
Coherencia del QR          Un QR que no corresponde al documento
Revocación (opcional)      Un certificado que el prestador dio de baja
=========================  =========================================

Sobre la vigencia: lo que importa es que el certificado estuviera vigente **al
momento de la firma**, no hoy. Un certificado que venció el mes pasado no
invalida los documentos que firmó cuando estaba vigente. El apartado 7.8 del
Manual Técnico lo dice así.

La consulta de revocación
-------------------------

Es la única comprobación que necesita **salir a la red** del prestador, así que
no se hace por omisión: una llamada de red silenciosa dentro de lo que parece
una función local es una sorpresa desagradable. Se pide explícitamente::

    verificar_documento(recibido, revocacion=True)

Con eso el informe queda completo y ``confiable`` no tiene ningún hueco. Sin
eso, un certificado revocado con todo lo demás en orden se informa como
confiable, y el resumen lo declara en ``limite_de_la_verificacion``.

Lo que importa es si el certificado estaba revocado **cuando se firmó**, no si
lo está hoy: un certificado dado de baja el mes pasado no invalida lo que firmó
antes. Se evalúa contra la fecha de firma del documento.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final
from urllib.parse import parse_qs, urlparse

from lxml import etree

from pysifen.cdc import Cdc
from pysifen.enums import TipoDocumento
from pysifen.pki.cadena import (
    ListaDeConfianza,
    ResultadoDeCadena,
    lista_de_confianza,
    validar_cadena,
)
from pysifen.pki.certificado import Certificado
from pysifen.pki.revocacion import (
    EstadoDeRevocacion,
    ResultadoDeRevocacion,
    consultar_revocacion,
)
from pysifen.signing.verificacion import ResultadoDeFirma, verificar_firma
from pysifen.validacion import validar_documento

__all__ = [
    "Verificacion",
    "leer_documentos",
    "verificar_documento",
]

NS_SIFEN: Final = "http://ekuatia.set.gov.py/sifen/xsd"


def _texto(raiz: etree._Element, camino: str) -> str | None:
    """Devuelve el texto de un elemento por su camino, o ``None``."""
    nodo = raiz.find(camino.replace("/", f"/{{{NS_SIFEN}}}")[1:])
    return nodo.text if nodo is not None and nodo.text else None


@dataclass(frozen=True, slots=True)
class Verificacion:
    """Informe de lo que se pudo determinar sobre un documento recibido.

    Ningún campo miente por omisión: cuando algo no se pudo comprobar vale
    ``None``, que es distinto de ``False``. Un documento cuyo certificado no se
    pudo leer no es lo mismo que uno con la firma adulterada.
    """

    cdc: str | None = None
    tipo_documento: TipoDocumento | None = None
    fecha_de_emision: str | None = None
    ruc_emisor: str | None = None
    razon_social_emisor: str | None = None
    total: str | None = None

    esquema_valido: bool = False
    problemas_de_esquema: tuple[str, ...] = ()

    firma: ResultadoDeFirma | None = None
    cadena: ResultadoDeCadena | None = None
    prestador: str | None = None
    certificado_vigente_a_la_firma: bool | None = None
    ruc_del_certificado: str | None = None
    ruc_coincide: bool | None = None

    cdc_coherente: bool | None = None
    qr_coherente: bool | None = None

    revocacion: ResultadoDeRevocacion | None = None

    observaciones: tuple[str, ...] = field(default_factory=tuple)

    @property
    def tolerancias(self) -> tuple[str, ...]:
        """Desvíos del estándar que hubo que tolerar para validar la firma.

        Vacío significa estrictamente conforme. Ver
        :mod:`pysifen.signing.verificacion`.
        """
        return self.firma.tolerancias if self.firma else ()

    @property
    def cadena_valida(self) -> bool:
        """``True`` si el certificado encadena hasta una raíz reconocida."""
        return self.cadena is not None and self.cadena.valida

    @property
    def certificado_revocado(self) -> bool:
        """``True`` sólo si el prestador confirmó que lo dio de baja.

        ``False`` cuando no se consultó: no poder comprobar no es lo mismo que
        comprobar que está bien, y por eso el resumen declara si se consultó.
        """
        return self.revocacion is not None and self.revocacion.revocado

    @property
    def firma_valida(self) -> bool:
        """``True`` si la firma cierra: resumen y firma criptográfica."""
        return self.firma is not None and self.firma.valida

    @property
    def confiable(self) -> bool:
        """``True`` si el documento es auténtico.

        Exige que el esquema valide, que la firma cierre, que el certificado
        **encadene hasta la Autoridad Certificadora Raíz del Paraguay** por un
        prestador habilitado, que estuviera vigente al firmar, que el RUC del
        documento sea el del certificado, y que el CDC y el QR sean coherentes.

        Es deliberadamente estricto: un ``None`` en cualquier comprobación
        significa que no se pudo verificar, y lo que no se pudo verificar no se
        da por bueno.

        La revocación sólo se comprueba si se pidió, porque necesita red. Si
        se pidió y el certificado está revocado, esto es ``False``. Ver el
        encabezado del módulo.
        """
        return (
            self.esquema_valido
            and self.firma_valida
            and self.cadena_valida
            and self.certificado_vigente_a_la_firma is True
            and self.ruc_coincide is True
            and self.cdc_coherente is True
            and self.qr_coherente is not False
            and not self.certificado_revocado
        )

    def resumir(self) -> dict[str, Any]:
        """Devuelve el documento en la forma más compacta que sigue siendo fiel.

        Pensado para que un modelo de lenguaje lo lea gastando la menor
        cantidad de tokens posible: estructura plana, nombres en castellano, sin
        espacios de nombres XML, y **sin las claves que no tienen valor**. Un
        documento tributario en XML ocupa unos 11 KB; esto suele quedar bajo el
        kilobyte.

        La clave ``confiable`` va primero a propósito: es la que decide si el
        resto se puede usar.

        Returns:
            Un diccionario serializable a JSON, sin objetos de la librería.
        """
        resumen: dict[str, Any] = {
            "confiable": self.confiable,
            "cdc": self.cdc,
            "tipo": self.tipo_documento.descripcion if self.tipo_documento else None,
            "emitido": self.fecha_de_emision,
            "emisor": self.razon_social_emisor,
            "ruc_emisor": self.ruc_emisor,
            "total": self.total,
            "verificacion": {
                "esquema": self.esquema_valido,
                "firma": self.firma_valida,
                "prestador": self.prestador,
                "cadena_de_confianza": self.cadena_valida,
                "certificado_vigente_al_firmar": self.certificado_vigente_a_la_firma,
                "ruc_coincide_con_el_certificado": self.ruc_coincide,
                "cdc_coherente": self.cdc_coherente,
                "qr_coherente": self.qr_coherente,
                "revocacion": self.revocacion.estado.value
                if self.revocacion
                else "no consultada",
            },
        }
        if self.revocacion is None:
            resumen["limite_de_la_verificacion"] = (
                "no se consultó la lista de certificados revocados, que "
                "requiere red. Todo lo demás está verificado, incluida la "
                "cadena de confianza hasta la Autoridad Certificadora Raíz "
                "del Paraguay. Para cerrar también eso: "
                "verificar_documento(xml, revocacion=True)."
            )
        elif self.revocacion.estado is EstadoDeRevocacion.DESCONOCIDO:
            resumen["limite_de_la_verificacion"] = (
                f"se consultó la revocación y no se pudo averiguar: "
                f"{self.revocacion.motivo}"
            )
        if self.tolerancias:
            resumen["tolerancias"] = list(self.tolerancias)
        if self.observaciones:
            resumen["reparos"] = list(self.observaciones)
        if self.problemas_de_esquema:
            resumen["problemas_de_esquema"] = list(self.problemas_de_esquema)
        return {k: v for k, v in resumen.items() if v is not None}

    def informe(self) -> str:
        """Devuelve el resultado en texto, para mostrar o registrar."""
        marca = "confiable" if self.confiable else "CON REPAROS"
        lineas = [f"{self.cdc or 'sin CDC'}  [{marca}]"]
        if self.razon_social_emisor:
            lineas.append(
                f"  emisor        {self.razon_social_emisor} ({self.ruc_emisor})"
            )
        if self.tipo_documento:
            lineas.append(f"  documento     {self.tipo_documento.descripcion}")
        if self.total:
            lineas.append(f"  total         {self.total}")
        lineas.append(
            f"  esquema       {'válido' if self.esquema_valido else 'INVÁLIDO'}"
        )
        lineas.append(
            f"  firma         {'válida' if self.firma_valida else 'INVÁLIDA'}"
        )
        lineas.append(f"  prestador     {self.prestador or 'NO IDENTIFICADO'}")
        if self.revocacion is not None:
            lineas.append(f"  revocación    {self.revocacion.estado.value}")
        for tolerancia in self.tolerancias:
            lineas.append(f"  ~ toleró: {tolerancia}")
        for observacion in self.observaciones:
            lineas.append(f"  · {observacion}")
        return "\n".join(lineas)


def verificar_documento(
    xml: bytes | str | etree._Element,
    *,
    lista: ListaDeConfianza | None = None,
    validar_esquema: bool = True,
    revocacion: bool = False,
) -> Verificacion:
    """Lee un documento recibido y verifica todo lo que se pueda verificar.

    Args:
        xml: el documento, en bytes, texto o ya interpretado. Se acepta tanto un
            ``rDE`` suelto como un ``rLoteDE`` con uno adentro.
        lista: las anclas de confianza contra las que validar la cadena. Por
            omisión, la Lista de Confianza que trae la librería.
        validar_esquema: si comprobar el documento contra el XSD oficial. Se
            puede apagar al procesar lotes grandes donde ya se validó antes.
        revocacion: si consultar al prestador que el certificado no esté dado
            de baja. **Sale a la red**, por eso está apagado por omisión.

    Returns:
        El informe. No lanza por un documento adulterado o mal formado: eso es
        un resultado, no un error.

    Example:
        >>> resultado = verificar_documento(recibido)  # doctest: +SKIP
        >>> resultado.confiable  # doctest: +SKIP
        True
    """
    observaciones: list[str] = []
    raiz = _interpretar(xml, observaciones)
    if raiz is None:
        return Verificacion(observaciones=tuple(observaciones))

    problemas = tuple(validar_documento(raiz)) if validar_esquema else ()
    resultado_firma = verificar_firma(raiz)
    if resultado_firma.motivo:
        observaciones.append(resultado_firma.motivo)
    observaciones.extend(
        f"la firma verificó, pero no de forma estrictamente conforme: {t}"
        for t in resultado_firma.tolerancias
    )

    datos = _datos_del_documento(raiz)
    certificado = resultado_firma.certificado

    resultado_cadena = _validar_cadena(certificado, raiz, lista, observaciones)
    prestador = resultado_cadena.prestador if resultado_cadena else None

    vigente = _vigencia_a_la_firma(certificado, raiz, observaciones)
    ruc_certificado = certificado.ruc if certificado else None
    ruc_coincide = _comparar_rucs(datos.get("ruc"), ruc_certificado, observaciones)

    resultado_revocacion = (
        _consultar_revocacion(certificado, raiz, lista, observaciones)
        if revocacion
        else None
    )

    return Verificacion(
        cdc=datos.get("cdc"),
        tipo_documento=datos.get("tipo"),
        fecha_de_emision=datos.get("fecha"),
        ruc_emisor=datos.get("ruc"),
        razon_social_emisor=datos.get("razon_social"),
        total=datos.get("total"),
        esquema_valido=not problemas,
        problemas_de_esquema=problemas,
        firma=resultado_firma,
        cadena=resultado_cadena,
        prestador=prestador,
        certificado_vigente_a_la_firma=vigente,
        ruc_del_certificado=ruc_certificado,
        ruc_coincide=ruc_coincide,
        revocacion=resultado_revocacion,
        cdc_coherente=_coherencia_del_cdc(datos.get("cdc"), observaciones),
        qr_coherente=_coherencia_del_qr(raiz, datos, observaciones),
        observaciones=tuple(observaciones),
    )


def leer_documentos(
    rutas: list[Path] | list[str],
    *,
    lista: ListaDeConfianza | None = None,
    revocacion: bool = False,
) -> list[Verificacion]:
    """Verifica varios documentos reutilizando el esquema ya compilado.

    Compilar el esquema completo lleva del orden de un segundo; hacerlo una vez
    por documento haría inviable procesar un lote. Acá se compila una sola vez,
    igual que la lista de confianza.

    Args:
        rutas: los archivos a verificar.
        lista: las anclas de confianza. Por omisión se lee una vez y se
            reutiliza.
        revocacion: si consultar la revocación de cada certificado. **Sale a la
            red una vez por documento**, por eso está apagado por omisión.

    Returns:
        Un informe por documento, en el mismo orden.
    """
    anclas = lista or lista_de_confianza()
    informes: list[Verificacion] = []
    for ruta in rutas:
        camino = Path(ruta)
        try:
            contenido = camino.read_bytes()
        except OSError as exc:
            informes.append(
                Verificacion(observaciones=(f"no pude leer {camino}: {exc}",))
            )
            continue
        informes.append(
            verificar_documento(contenido, lista=anclas, revocacion=revocacion)
        )
    return informes


def _interpretar(
    xml: bytes | str | etree._Element, observaciones: list[str]
) -> etree._Element | None:
    """Normaliza la entrada y desenvuelve el lote si hace falta."""
    if isinstance(xml, etree._Element):
        raiz = xml
    else:
        crudo = xml.encode() if isinstance(xml, str) else xml
        analizador = etree.XMLParser(resolve_entities=False, no_network=True)
        try:
            raiz = etree.fromstring(crudo, parser=analizador)
        except etree.XMLSyntaxError as exc:
            observaciones.append(f"el documento no es XML válido: {exc}")
            return None

    if etree.QName(raiz).localname == "rLoteDE":
        hijos = list(raiz)
        if not hijos:
            observaciones.append("el lote no trae ningún documento")
            return None
        if len(hijos) > 1:
            observaciones.append(
                f"el lote trae {len(hijos)} documentos; se verificó el primero. "
                "Usar leer_documentos() para procesarlos todos"
            )
        return hijos[0]
    return raiz


def _datos_del_documento(raiz: etree._Element) -> dict[str, Any]:
    """Extrae los datos que identifican al documento."""
    de = raiz.find(f"{{{NS_SIFEN}}}DE")
    datos: dict[str, Any] = {}
    if de is None:
        return datos

    datos["cdc"] = de.get("Id")
    codigo = _texto(de, "/gTimb/iTiDE")
    if codigo and codigo.isdigit():
        with contextlib.suppress(ValueError):
            datos["tipo"] = TipoDocumento(int(codigo))
    datos["fecha"] = _texto(de, "/gDatGralOpe/dFeEmiDE")
    ruc = _texto(de, "/gDatGralOpe/gEmis/dRucEm")
    dv = _texto(de, "/gDatGralOpe/gEmis/dDVEmi")
    if ruc:
        datos["ruc"] = f"{ruc}-{dv}" if dv else ruc
    datos["razon_social"] = _texto(de, "/gDatGralOpe/gEmis/dNomEmi")
    datos["total"] = _texto(de, "/gTotSub/dTotGralOpe")
    datos["iva"] = _texto(de, "/gTotSub/dTotIVA")
    datos["items"] = str(
        len(de.findall(f"{{{NS_SIFEN}}}gDtipDE/{{{NS_SIFEN}}}gCamItem"))
    )
    return datos


def _validar_cadena(
    certificado: Certificado | None,
    raiz: etree._Element,
    lista: ListaDeConfianza | None,
    observaciones: list[str],
) -> ResultadoDeCadena | None:
    """Valida la cadena del certificado hasta una raíz reconocida.

    Se evalúa a la fecha de la firma, no a la de hoy: una autoridad que vence
    el mes que viene no invalida lo que firmó estando vigente.
    """
    if certificado is None:
        return None

    anclas = lista or lista_de_confianza()
    resultado = validar_cadena(certificado, lista=anclas, momento=_fecha_de_firma(raiz))
    if not resultado.valida and resultado.motivo:
        observaciones.append(f"la cadena de confianza no cierra: {resultado.motivo}")
    return resultado


def _consultar_revocacion(
    certificado: Certificado | None,
    raiz: etree._Element,
    lista: ListaDeConfianza | None,
    observaciones: list[str],
) -> ResultadoDeRevocacion | None:
    """Pregunta al prestador si el certificado seguía vigente al firmarse."""
    if certificado is None:
        return None

    resultado = consultar_revocacion(
        certificado, lista=lista, momento=_fecha_de_firma(raiz)
    )
    if resultado.revocado:
        cuando = (
            f" el {resultado.revocado_el:%d/%m/%Y}" if resultado.revocado_el else ""
        )
        observaciones.append(
            f"el prestador revocó el certificado{cuando}"
            + (f" por {resultado.razon}" if resultado.razon else "")
        )
    elif resultado.estado is EstadoDeRevocacion.DESCONOCIDO:
        observaciones.append(f"no se pudo consultar la revocación: {resultado.motivo}")
    return resultado


def _fecha_de_firma(raiz: etree._Element) -> datetime | None:
    """Devuelve la fecha declarada de la firma, si se puede interpretar."""
    de = raiz.find(f"{{{NS_SIFEN}}}DE")
    if de is None:
        return None
    crudo = _texto(de, "/dFecFirma")
    if not crudo:
        return None
    try:
        momento = datetime.fromisoformat(crudo)
    except ValueError:
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


def _vigencia_a_la_firma(
    certificado: Certificado | None,
    raiz: etree._Element,
    observaciones: list[str],
) -> bool | None:
    """Comprueba que el certificado estuviera vigente cuando se firmó."""
    if certificado is None:
        return None

    de = raiz.find(f"{{{NS_SIFEN}}}DE")
    momento: datetime | None = None
    if de is not None:
        crudo = _texto(de, "/dFecFirma")
        if crudo:
            try:
                momento = datetime.fromisoformat(crudo)
            except ValueError:
                observaciones.append(
                    f"la fecha de firma no se puede interpretar: {crudo}"
                )
    if momento is None:
        observaciones.append(
            "el documento no declara fecha de firma; se evaluó la vigencia a hoy"
        )
        momento = datetime.now(UTC)
    elif momento.tzinfo is None:
        momento = momento.replace(tzinfo=UTC)

    vigente = certificado.vigente(momento)
    if not vigente:
        observaciones.append(
            f"el certificado no estaba vigente al firmar: rige del "
            f"{certificado.valido_desde:%d/%m/%Y} al "
            f"{certificado.valido_hasta:%d/%m/%Y}"
        )
    return vigente


def _comparar_rucs(
    del_documento: Any, del_certificado: str | None, observaciones: list[str]
) -> bool | None:
    """Comprueba que el RUC del documento sea el del certificado."""
    if not isinstance(del_documento, str) or del_certificado is None:
        return None
    coincide = del_documento.replace(" ", "") == del_certificado.replace(" ", "")
    if not coincide:
        observaciones.append(
            f"el documento declara el RUC {del_documento} pero está firmado con "
            f"un certificado del RUC {del_certificado}"
        )
    return coincide


def _coherencia_del_cdc(valor: Any, observaciones: list[str]) -> bool | None:
    """Comprueba que el CDC sea consistente consigo mismo."""
    if not isinstance(valor, str) or not valor:
        return None
    try:
        Cdc.parse(valor)
    except Exception as exc:
        observaciones.append(f"el CDC no es coherente: {exc}")
        return False
    return True


def _coherencia_del_qr(
    raiz: etree._Element, datos: dict[str, object], observaciones: list[str]
) -> bool | None:
    """Comprueba que el QR declare lo mismo que el documento.

    No se puede recalcular el ``cHashQR`` porque depende del Código de Seguridad
    del Contribuyente, que sólo conocen el emisor y la DNIT. Pero sí se puede
    comprobar que los parámetros que el QR publica coincidan con el documento, y
    eso ya detecta un QR pegado de otro comprobante.
    """
    nodo = raiz.find(f"{{{NS_SIFEN}}}gCamFuFD/{{{NS_SIFEN}}}dCarQR")
    if nodo is None or not nodo.text:
        return None

    parametros = parse_qs(urlparse(nodo.text).query)

    def declarado(clave: str) -> str | None:
        valores = parametros.get(clave)
        return valores[0] if valores else None

    desacuerdos: list[str] = []
    for clave, esperado in (
        ("Id", datos.get("cdc")),
        ("dTotGralOpe", datos.get("total")),
        ("dTotIVA", datos.get("iva")),
        ("cItems", datos.get("items")),
    ):
        publicado = declarado(clave)
        if publicado is not None and esperado is not None and publicado != esperado:
            desacuerdos.append(
                f"{clave}: el QR dice {publicado} y el documento {esperado}"
            )

    if desacuerdos:
        observaciones.append(
            "el QR no corresponde al documento: " + "; ".join(desacuerdos)
        )
        return False
    return True
