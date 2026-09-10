"""Código de Control (CDC) de los documentos electrónicos.

Implementa el apartado 10.1 (estructura del CDC) y 10.2 (dígito verificador) del
Manual Técnico SIFEN v150.

El CDC identifica unívocamente a cada documento electrónico dentro del SIFEN. Es
una cadena de 44 dígitos que además viaja como atributo ``Id`` del elemento
``DE`` y como ``Reference URI`` de la firma digital.

Estructura, según la tabla del apartado 10.1:

===========  ======  ====================================
Posición     Largo   Campo
===========  ======  ====================================
1            2       Tipo de documento electrónico
3            8       RUC del emisor sin dígito verificador
11           1       Dígito verificador del RUC
12           3       Establecimiento
15           3       Punto de expedición
18           7       Número del documento
25           1       Tipo de contribuyente
26           8       Fecha de emisión ``AAAAMMDD``
34           1       Tipo de emisión
35           9       Código de seguridad
44           1       Dígito verificador del CDC
===========  ======  ====================================
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date
from typing import Final

from pysifen.enums import TipoContribuyente, TipoDocumento, TipoEmision
from pysifen.exceptions import CdcError

__all__ = [
    "LARGO_CDC",
    "Cdc",
    "calcular_dv_mod11",
    "dv_ruc",
]

#: Largo total del CDC, incluido su dígito verificador.
LARGO_CDC: Final = 44

#: Peso máximo del módulo 11 usado por la Administración Tributaria.
_PESO_MAXIMO: Final = 11

_SOLO_DIGITOS: Final = re.compile(r"^\d+$")

#: Dígitos del RUC dentro del CDC, sin el verificador.
_LARGO_RUC_BASE: Final = 8


def calcular_dv_mod11(numero: str, peso_maximo: int = _PESO_MAXIMO) -> int:
    """Calcula el dígito verificador por módulo 11.

    Es el algoritmo que la Administración Tributaria usa tanto para el dígito
    verificador del RUC como para el del CDC (Manual Técnico v150, 10.2).

    Los pesos se aplican de derecha a izquierda, arrancando en 2 y volviendo a 2
    después de ``peso_maximo``. Sobre la suma ponderada se toma el resto de la
    división por 11: si es mayor que 1 el dígito es ``11 - resto``, y si no es
    cero.

    Args:
        numero: cadena de dígitos, sin el dígito verificador.
        peso_maximo: tope del ciclo de pesos. El valor normado es 11.

    Returns:
        El dígito verificador, entre 0 y 9.

    Raises:
        CdcError: si ``numero`` está vacío o tiene algo que no sea un dígito.

    Example:
        >>> calcular_dv_mod11("44444401")
        7
    """
    if not numero or not _SOLO_DIGITOS.match(numero):
        raise CdcError(f"se esperaban sólo dígitos, se recibió {numero!r}")

    total = 0
    peso = 2
    for caracter in reversed(numero):
        total += int(caracter) * peso
        peso = 2 if peso >= peso_maximo else peso + 1

    resto = total % 11
    return 11 - resto if resto > 1 else 0


def dv_ruc(ruc: str) -> int:
    """Devuelve el dígito verificador de un RUC.

    Args:
        ruc: número de RUC sin dígito verificador. Se admiten puntos y espacios,
            que se descartan.

    Returns:
        El dígito verificador del RUC.

    Example:
        >>> dv_ruc("44444401")
        7
    """
    return calcular_dv_mod11(_solo_digitos(ruc))


def _solo_digitos(valor: str) -> str:
    """Descarta todo lo que no sea dígito."""
    return re.sub(r"\D", "", valor)


def _rellenar(valor: str | int, largo: int, campo: str) -> str:
    """Normaliza un componente numérico a un largo fijo, con ceros a izquierda.

    Raises:
        CdcError: si el valor no es numérico o no entra en el largo pedido.
    """
    texto = _solo_digitos(str(valor))
    if not texto:
        raise CdcError(f"{campo} no puede estar vacío", campo=campo)
    if len(texto) > largo:
        raise CdcError(
            f"{campo} tiene {len(texto)} dígitos y el máximo es {largo}",
            campo=campo,
        )
    return texto.rjust(largo, "0")


@dataclass(frozen=True, slots=True)
class Cdc:
    """Un Código de Control ya armado y validado.

    Es inmutable. Se construye con :meth:`crear`, que calcula el dígito
    verificador, o con :meth:`parse`, que valida uno existente.
    """

    tipo_documento: TipoDocumento
    ruc_emisor: str
    dv_ruc: int
    establecimiento: str
    punto_expedicion: str
    numero: str
    tipo_contribuyente: TipoContribuyente
    fecha_emision: date
    tipo_emision: TipoEmision
    codigo_seguridad: str
    dv: int

    @property
    def valor(self) -> str:
        """El CDC completo, 44 dígitos."""
        return f"{self._base()}{self.dv}"

    @property
    def formateado(self) -> str:
        """El CDC en grupos de cuatro, como exige el KuDE (10.1).

        Example:
            >>> cdc = Cdc.parse("01444444017001001001452822017012515873260988")
            >>> cdc.formateado
            '0144 4444 0170 0100 1001 4528 2201 7012 5158 7326 0988'
        """
        valor = self.valor
        return " ".join(valor[i : i + 4] for i in range(0, LARGO_CDC, 4))

    @property
    def numero_documento(self) -> str:
        """Número de documento con formato ``EEE-PPP-NNNNNNN``."""
        return f"{self.establecimiento}-{self.punto_expedicion}-{self.numero}"

    def _base(self) -> str:
        """Los 43 dígitos anteriores al dígito verificador."""
        return (
            f"{self.tipo_documento.value:02d}"
            f"{self.ruc_emisor}"
            f"{self.dv_ruc}"
            f"{self.establecimiento}"
            f"{self.punto_expedicion}"
            f"{self.numero}"
            f"{self.tipo_contribuyente.value}"
            f"{self.fecha_emision:%Y%m%d}"
            f"{self.tipo_emision.value}"
            f"{self.codigo_seguridad}"
        )

    def __str__(self) -> str:
        """Devuelve el CDC de 44 dígitos."""
        return self.valor

    @classmethod
    def crear(
        cls,
        *,
        tipo_documento: TipoDocumento,
        ruc_emisor: str,
        establecimiento: str | int,
        punto_expedicion: str | int,
        numero: str | int,
        tipo_contribuyente: TipoContribuyente,
        fecha_emision: date,
        codigo_seguridad: str,
        tipo_emision: TipoEmision = TipoEmision.NORMAL,
        dv_emisor: int | None = None,
    ) -> Cdc:
        """Arma un CDC y calcula su dígito verificador.

        Args:
            tipo_documento: tipo de documento electrónico (campo ``iTiDE``).
            ruc_emisor: RUC del emisor. Se acepta con o sin dígito verificador,
                en cualquiera de las formas ``80012345-6``, ``800123456`` u
                ``80012345``.
            establecimiento: código de establecimiento, 3 dígitos.
            punto_expedicion: punto de expedición, 3 dígitos.
            numero: número del documento, 7 dígitos.
            tipo_contribuyente: persona física o jurídica.
            fecha_emision: fecha de emisión del documento.
            codigo_seguridad: ``dCodSeg``, 9 dígitos. Ver
                :func:`pysifen.security.generar_codigo_seguridad`.
            tipo_emision: normal o contingencia.
            dv_emisor: dígito verificador del RUC. Si no se pasa y el RUC no lo
                trae, se calcula.

        Returns:
            El CDC armado.

        Raises:
            CdcError: si algún componente no cumple su formato.
        """
        base_ruc, dv = _separar_ruc(ruc_emisor, dv_emisor)

        parcial = cls(
            tipo_documento=tipo_documento,
            ruc_emisor=base_ruc,
            dv_ruc=dv,
            establecimiento=_rellenar(establecimiento, 3, "establecimiento"),
            punto_expedicion=_rellenar(punto_expedicion, 3, "punto_expedicion"),
            numero=_rellenar(numero, 7, "numero"),
            tipo_contribuyente=tipo_contribuyente,
            fecha_emision=fecha_emision,
            tipo_emision=tipo_emision,
            codigo_seguridad=_rellenar(codigo_seguridad, 9, "codigo_seguridad"),
            dv=0,
        )
        return replace(parcial, dv=calcular_dv_mod11(parcial._base()))

    @classmethod
    def parse(cls, valor: str) -> Cdc:
        """Interpreta un CDC existente y verifica su dígito verificador.

        Args:
            valor: los 44 dígitos. Se toleran espacios, como en el formato de
                grupos de cuatro que se imprime en el KuDE.

        Returns:
            El CDC descompuesto en sus campos.

        Raises:
            CdcError: si el largo no es 44, si hay caracteres no numéricos, si
                el dígito verificador no cierra, o si algún código no pertenece
                a la tabla del manual.
        """
        texto = _solo_digitos(valor)
        if len(texto) != LARGO_CDC:
            raise CdcError(f"el CDC debe tener {LARGO_CDC} dígitos, tiene {len(texto)}")

        base, dv_declarado = texto[:-1], int(texto[-1])
        dv_calculado = calcular_dv_mod11(base)
        if dv_declarado != dv_calculado:
            raise CdcError(
                "el dígito verificador no corresponde: "
                f"declarado {dv_declarado}, calculado {dv_calculado}"
            )

        try:
            tipo_documento = TipoDocumento(int(texto[0:2]))
            tipo_contribuyente = TipoContribuyente(int(texto[24]))
            tipo_emision = TipoEmision(int(texto[33]))
        except ValueError as exc:
            raise CdcError(f"el CDC tiene un código fuera de tabla: {exc}") from exc

        try:
            fecha_emision = date(
                int(texto[25:29]), int(texto[29:31]), int(texto[31:33])
            )
        except ValueError as exc:
            raise CdcError(f"la fecha de emisión del CDC es inválida: {exc}") from exc

        return cls(
            tipo_documento=tipo_documento,
            ruc_emisor=texto[2:10],
            dv_ruc=int(texto[10]),
            establecimiento=texto[11:14],
            punto_expedicion=texto[14:17],
            numero=texto[17:24],
            tipo_contribuyente=tipo_contribuyente,
            fecha_emision=fecha_emision,
            tipo_emision=tipo_emision,
            codigo_seguridad=texto[34:43],
            dv=dv_declarado,
        )


def _separar_ruc(ruc: str, dv_explicito: int | None) -> tuple[str, int]:
    """Separa un RUC en base de 8 dígitos y dígito verificador.

    Acepta ``80012345-6``, ``800123456`` y ``80012345``. En el segundo caso el
    último dígito se toma como verificador sólo si el resto sigue entrando en
    ocho posiciones.
    """
    if dv_explicito is not None:
        base = _solo_digitos(ruc)
        if len(base) > _LARGO_RUC_BASE:
            base = base[:8]
        return _rellenar(base, 8, "ruc_emisor"), dv_explicito

    if "-" in ruc:
        parte, _, resto = ruc.rpartition("-")
        return _rellenar(parte, 8, "ruc_emisor"), int(_solo_digitos(resto) or "0")

    digitos = _solo_digitos(ruc)
    if not digitos:
        raise CdcError("ruc_emisor no puede estar vacío", campo="ruc_emisor")

    if len(digitos) > _LARGO_RUC_BASE:
        return _rellenar(digitos[:-1], 8, "ruc_emisor"), int(digitos[-1])

    return _rellenar(digitos, 8, "ruc_emisor"), calcular_dv_mod11(digitos)
