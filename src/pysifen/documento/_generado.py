"""Modelos del documento electrónico, generados desde el esquema oficial.

.. danger::
   **Este archivo se genera. No editarlo a mano.**

   Sale de ``src/pysifen/esquemas/DE_v150.xsd`` a través de
   ``scripts/generar_modelos.py``. Cualquier cambio manual se pierde en la
   próxima regeneración, y peor: haría que la librería acepte documentos que el
   SIFEN rechaza.

   Para cambiar algo acá, hay que cambiar el generador.

El orden de los campos, su obligatoriedad, sus longitudes, sus patrones y sus
valores enumerados salen del esquema. Los docstrings salen de la documentación
que el propio esquema trae embebida, así que describen los campos con las
palabras de la fuente normativa.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, ClassVar, Literal

from pydantic import Field, StringConstraints

from pysifen.documento.base import GrupoSifen, campo, campo_opcional


class COpeDE(GrupoSifen):
    """Campos de la operacion del Documento Electronico.

    Elemento XML: ``gOpeDE``. Tipo del esquema: ``tgCOpeDE``.
    """

    _etiqueta: ClassVar[str] = "gOpeDE"

    iTipEmi: int = campo(None, "Tipo de Emision: 1(Normal), 2(Contingencia).")
    dDesTipEmi: Literal["Normal", "Contingencia"] = campo(
        None, "Descripcion del tipo de emision: 1(Normal). 2(Contingencia)."
    )
    dCodSeg: Annotated[str, StringConstraints(pattern="[0-9]{9}")] = campo(
        None,
        "La generacion de este codigo es responsabilidad del emisor, segun los delineamientos establecidos en el Manual Tecnico, no debe ser un numero secuencial, sino aleatorio, tampoco debe contener solo ceros.",
    )
    dInfoEmi: (
        Annotated[str, StringConstraints(min_length=1, max_length=3000, pattern=".+")]
        | None
    ) = campo_opcional(None, "Informacion de interes del emisor respecto al DE.")
    dInfoFisc: (
        Annotated[str, StringConstraints(min_length=1, max_length=3000, pattern=".+")]
        | None
    ) = campo_opcional(None, "Informacion de interes del Fisco respecto al DE.")


class DTim(GrupoSifen):
    """Campos de datos del timbrado.

    Elemento XML: ``gTimb``. Tipo del esquema: ``tgDTim``.
    """

    _etiqueta: ClassVar[str] = "gTimb"

    iTiDE: int = campo(None, "Tipo de documento electronico.")
    dDesTiDE: Literal[
        "Factura electrónica",
        "Autofactura electrónica",
        "Nota de crédito electrónica",
        "Nota de débito electrónica",
        "Nota de remisión electrónica",
        "Boleta de venta electrónica",
        "Boleta resimple electrónica",
    ] = campo(None, "Descripcion del tipo de documento electronico.")
    dNumTim: str = campo(None, "Numero de timbrado del documento electronico.")
    dEst: Annotated[str, StringConstraints(min_length=3, pattern="[0-9]{3}")] = campo(
        None, "Codigo de establecimiento proveido por el Sistema de timbrado."
    )
    dPunExp: Annotated[str, StringConstraints(min_length=3, pattern="[0-9]{3}")] = (
        campo(None, "Codigo de Punto de Exp. proveido por el Sist.Timbrado.")
    )
    dNumDoc: Annotated[
        str,
        StringConstraints(
            min_length=7, max_length=7, pattern="0+[1-9][0-9]*|[1-9]+[0-9]+"
        ),
    ] = campo(None, "Numero de documento del DE.")
    dSerieNum: (
        Annotated[str, StringConstraints(min_length=1, pattern="[A-Z]{2}")] | None
    ) = campo_opcional(None, "Serie del número de timbrado.")
    dFeIniT: date = campo(None, "Fecha inicio de vigencia del Timbrado.")


class ActEco(GrupoSifen):
    """Grupo de Campos de la Actividad Economica.

    Elemento XML: ``gActEco``. Tipo del esquema: ``tgActEco``.
    """

    _etiqueta: ClassVar[str] = "gActEco"

    cActEco: Annotated[
        str, StringConstraints(min_length=1, max_length=8, pattern="[0-9A-Z]{1,8}")
    ] = campo(
        None, "Codigo de actividad economica del emisor segun la lista de maragantu."
    )
    dDesActEco: Annotated[
        str, StringConstraints(min_length=1, max_length=300, pattern=".*[^\\s].*")
    ] = campo(None, "Descripcion de actividad economica.")


class RespDE(GrupoSifen):
    """Grupo de Campos que identifican al responsable de la generación del DE.

    Elemento XML: ``gRespDE``. Tipo del esquema: ``tgRespDE``.
    """

    _etiqueta: ClassVar[str] = "gRespDE"

    iTipIDRespDE: int = campo(
        None, "Tipo de documento de identidad del responsable de la generación del DE."
    )
    dDTipIDRespDE: str = campo(
        None,
        "Descripcion del tipo de documento de identidad del responsable de la generación del DE.",
    )
    dNumIDRespDE: Annotated[str, StringConstraints(pattern="[0-9A-Za-z\\-]{1,20}")] = (
        campo(None, "Numero de documento de identidad.")
    )
    dNomRespDE: Annotated[
        str, StringConstraints(min_length=4, max_length=255, pattern=".*[^\\s].*")
    ] = campo(None, "Nombre o razon social.")
    dCarRespDE: Annotated[
        str, StringConstraints(min_length=4, max_length=100, pattern=".*[^\\s].*")
    ] = campo(None, "Cargo del responsable de la generación del DE.")


class Emis(GrupoSifen):
    """Campos que identifican al emisor del Documento Electrónico DE.

    Elemento XML: ``gEmis``. Tipo del esquema: ``tgEmis``.
    """

    _etiqueta: ClassVar[str] = "gEmis"

    dRucEm: Annotated[
        str,
        StringConstraints(min_length=3, max_length=8, pattern="[1-9][0-9]*[0-9A-D]?"),
    ] = campo(None, "dRucEm")
    dDVEmi: int = campo(None, "dDVEmi")
    iTipCont: int = campo(
        None, "Tipo de contribuyente. 1(Persona Fisica), 2(Persona Juridica)."
    )
    cTipReg: int | None = campo_opcional(None, "Tipo de Régimen.")
    dNomEmi: Annotated[
        str, StringConstraints(min_length=4, max_length=255, pattern=".*[^\\s].*")
    ] = campo(None, "Nombre o razon social.")
    dNomFanEmi: (
        Annotated[
            str, StringConstraints(min_length=4, max_length=255, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "Nombre o razon social.")
    dDirEmi: Annotated[
        str, StringConstraints(min_length=1, max_length=255, pattern=".*[^\\s].*")
    ] = campo(None, "Tipo de dato para dirección de 255 caracteres.")
    dNumCas: Annotated[int, Field(ge=0)] = campo(None, "Numero de casa.")
    dCompDir1: (
        Annotated[
            str, StringConstraints(min_length=1, max_length=255, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "Tipo de dato para dirección de 255 caracteres.")
    dCompDir2: (
        Annotated[
            str, StringConstraints(min_length=1, max_length=255, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "Tipo de dato para dirección de 255 caracteres.")
    cDepEmi: str = campo(None, "cDepEmi")
    dDesDepEmi: str = campo(None, "dDesDepEmi")
    cDisEmi: Annotated[int, Field(ge=1)] | None = campo_opcional(
        None, "Codigo de distrito."
    )
    dDesDisEmi: (
        Annotated[
            str, StringConstraints(min_length=1, max_length=30, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "Descripcion de distrito.")
    cCiuEmi: Annotated[int, Field(ge=1, le=99999)] = campo(None, "cCiuEmi")
    dDesCiuEmi: Annotated[
        str, StringConstraints(min_length=1, max_length=30, pattern=".*[^\\s].*")
    ] = campo(None, "dDesCiuEmi")
    dTelEmi: Annotated[
        str, StringConstraints(min_length=6, max_length=15, pattern=".+")
    ] = campo(None, "dTelEmi")
    dEmailE: Annotated[
        str,
        StringConstraints(
            pattern="([0-9a-zA-Z]([0-9a-zA-Z\\.\\-_])*@([0-9a-zA-Z][0-9a-zA-Z\\-_]*\\.)+[a-zA-Z]{2,9})"
        ),
    ] = campo(None, "dEmailE")
    dDenSuc: str | None = campo_opcional(None, "Denominación comercial de la sucursal.")
    gActEco: tuple[ActEco, ...] = campo_opcional(None, "gActEco")
    gRespDE: RespDE | None = campo_opcional(None, "gRespDE")


class DatRec(GrupoSifen):
    """Campos que identifican al receptor del Documento Electrónico DE.

    Elemento XML: ``gDatRec``. Tipo del esquema: ``tgDatRec``.
    """

    _etiqueta: ClassVar[str] = "gDatRec"

    iNatRec: int = campo(
        None, "Naturaleza del receptor: 1(Contribuyente), 2(No Contribuyente)."
    )
    iTiOpe: int = campo(None, "Tipo de operacion: 1(B2B), 2(B2C), 3(B2G), 4(B2F).")
    cPaisRec: str = campo(None, "cPaisRec")
    dDesPaisRe: Annotated[
        str, StringConstraints(min_length=4, max_length=50, pattern=".*[^\\s].*")
    ] = campo(None, "dDesPaisRe")
    iTiContRec: int | None = campo_opcional(
        None, "Tipo de contribuyente. 1(Persona Fisica), 2(Persona Juridica)."
    )
    dRucRec: (
        Annotated[
            str,
            StringConstraints(
                min_length=3, max_length=8, pattern="[1-9][0-9]*[0-9A-D]?"
            ),
        ]
        | None
    ) = campo_opcional(None, "dRucRec")
    dDVRec: int | None = campo_opcional(None, "dDVRec")
    iTipIDRec: int | None = campo_opcional(
        None, "Tipo de documento de identidad del receptor."
    )
    dDTipIDRec: str | None = campo_opcional(
        None, "Descripcion del tipo de documento de identidad del receptor."
    )
    dNumIDRec: (
        Annotated[str, StringConstraints(pattern="[0-9A-Za-z\\-]{1,20}")] | None
    ) = campo_opcional(None, "Numero de documento de identidad.")
    dNomRec: Annotated[
        str, StringConstraints(min_length=4, max_length=255, pattern=".*[^\\s].*")
    ] = campo(None, "Nombre o razon social.")
    dNomFanRec: (
        Annotated[
            str, StringConstraints(min_length=4, max_length=255, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "Nombre o razon social.")
    dDirRec: (
        Annotated[
            str, StringConstraints(min_length=1, max_length=255, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "Tipo de dato para dirección de 255 caracteres.")
    dNumCasRec: Annotated[int, Field(ge=0)] | None = campo_opcional(
        None, "Numero de casa."
    )
    cDepRec: str | None = campo_opcional(None, "cDepRec")
    dDesDepRec: str | None = campo_opcional(None, "dDesDepRec")
    cDisRec: int | None = campo_opcional(
        None, "Código del distrito donde se realiza la transacción."
    )
    dDesDisRec: (
        Annotated[
            str, StringConstraints(min_length=1, max_length=30, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(
        None, "Descripción del distrito donde se realiza la transacción."
    )
    cCiuRec: int | None = campo_opcional(
        None, "Código de la ciudad donde se realiza la transacción."
    )
    dDesCiuRec: (
        Annotated[
            str, StringConstraints(min_length=1, max_length=30, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(
        None, "Descripción de la ciudad donde se realiza la transacción."
    )
    dTelRec: (
        Annotated[str, StringConstraints(min_length=6, max_length=15, pattern=".+")]
        | None
    ) = campo_opcional(None, "dTelRec")
    dCelRec: (
        Annotated[str, StringConstraints(min_length=10, max_length=20, pattern=".+")]
        | None
    ) = campo_opcional(None, "dCelRec")
    dEmailRec: (
        Annotated[
            str,
            StringConstraints(
                pattern="([0-9a-zA-Z]([0-9a-zA-Z\\.\\-_])*@([0-9a-zA-Z][0-9a-zA-Z\\-_]*\\.)+[a-zA-Z]{2,9})"
            ),
        ]
        | None
    ) = campo_opcional(None, "dEmailRec")
    dCodCliente: str | None = campo_opcional(None, "Codigo del Cliente.")


class OblAfe(GrupoSifen):
    """Grupo de campos que identifican las obligaciones afectadas.

    Elemento XML: ``gOblAfe``. Tipo del esquema: ``tgOblAfe``.
    """

    _etiqueta: ClassVar[str] = "gOblAfe"

    cOblAfe: int = campo(None, "Código de la obligación afectada.")
    dDesOblAfe: Annotated[
        str, StringConstraints(min_length=21, max_length=65, pattern=".*[^\\s].*")
    ] = campo(None, "Descripción de la obligación afectada.")


class OpeCom(GrupoSifen):
    """Campos inherentes a la operacion comercial.

    Elemento XML: ``gOpeCom``. Tipo del esquema: ``tgOpeCom``.
    """

    _etiqueta: ClassVar[str] = "gOpeCom"

    iTipTra: Annotated[int, Field(ge=1, le=13)] | None = campo_opcional(
        None, "Tipo de transaccion."
    )
    dDesTipTra: (
        Literal[
            "Venta de mercadería",
            "Prestación de servicios",
            "Mixto (Venta de mercadería y servicios)",
            "Venta de activo fijo",
            "Venta de divisas",
            "Compra de divisas",
            "Promoción o entrega de muestras",
            "Donación",
            "Anticipo",
            "Compra de productos",
            "Compra de servicios",
            "Venta de crédito fiscal",
            "Muestras médicas (Art. 3 RG 24/2014)",
        ]
        | None
    ) = campo_opcional(None, "Descripcion del tipo de transaccion.")
    iTImp: int = campo(None, "Tipo de impuesto afectado.")
    dDesTImp: Literal["IVA", "ISC", "Renta", "Ninguno", "IVA - Renta"] = campo(
        None, "Descripción del tipo de impuesto afectado."
    )
    cMoneOpe: str = campo(None, "cMoneOpe")
    dDesMoneOpe: Annotated[
        str, StringConstraints(min_length=3, max_length=20, pattern=".*[^\\s].*")
    ] = campo(None, "Descripcion de la moneda.")
    dCondTiCam: int | None = campo_opcional(
        None, "Condición del tipo de cambio 1(Global), 2(Por ítem)."
    )
    dTiCam: Annotated[Decimal, Field(max_digits=9, decimal_places=4)] | None = (
        campo_opcional(None, "Tipo base para los tipos de cambio.")
    )
    iCondAnt: int | None = campo_opcional(
        None, "Condición del Anticipo 1(Global), 2(Por ítem)."
    )
    dDesCondAnt: Literal["Anticipo Global", "Anticipo por Ítem"] | None = (
        campo_opcional(None, "Descripción de la condición del Anticipo.")
    )
    gOblAfe: tuple[OblAfe, ...] = campo_opcional(None, "gOblAfe")


class DaGOC(GrupoSifen):
    """Campos Generales del Documento Electrónico DE.

    Elemento XML: ``gDatGralOpe``. Tipo del esquema: ``tgDaGOC``.
    """

    _etiqueta: ClassVar[str] = "gDatGralOpe"

    dFeEmiDE: datetime = campo(
        None, "Normalizador de Fecha y Hora AAAA-MM-DDThh:mm:ss."
    )
    gOpeCom: OpeCom | None = campo_opcional(None, "gOpeCom")
    gEmis: Emis = campo(None, "gEmis")
    gDatRec: DatRec = campo(None, "gDatRec")


class PagTarCD(GrupoSifen):
    """Campos que describen el pago o entrega inicial de la operación con...

    Campos que describen el pago o entrega inicial de la operación con tarjeta de
    crédito/débito.

    Elemento XML: ``gPagTarCD``. Tipo del esquema: ``tgPagTarCD``.
    """

    _etiqueta: ClassVar[str] = "gPagTarCD"

    iDenTarj: int = campo(None, "Codigo de tipo de tarjeta.")
    dDesDenTarj: str = campo(None, "Descripción de denominación de la tarjeta.")
    dRSProTar: (
        Annotated[
            str, StringConstraints(min_length=4, max_length=60, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "Nombre o razón social.")
    dRUCProTar: (
        Annotated[
            str,
            StringConstraints(
                min_length=3, max_length=8, pattern="[1-9][0-9]*[0-9A-D]?"
            ),
        ]
        | None
    ) = campo_opcional(None, "dRUCProTar")
    dDVProTar: int | None = campo_opcional(None, "dDVProTar")
    iForProPa: int = campo(
        None, "Forma de procesamiento del pago. 1(POS), 2(Pago Electronico)."
    )
    dCodAuOpe: Annotated[int, Field(ge=100000)] | None = campo_opcional(
        None, "Código de autorización de la operación."
    )
    dNomTit: str | None = campo_opcional(None, "Nombre del titular de la tarjeta.")
    dNumTarj: str | None = campo_opcional(None, "Numero de la tarjeta.")


class PagCheq(GrupoSifen):
    """Campos que describen el pago o entrega inicial de la operación con...

    Campos que describen el pago o entrega inicial de la operación con cheque.

    Elemento XML: ``gPagCheq``. Tipo del esquema: ``tgPagCheq``.
    """

    _etiqueta: ClassVar[str] = "gPagCheq"

    dNumCheq: Annotated[
        str, StringConstraints(min_length=8, max_length=8, pattern="[0-9]{8}")
    ] = campo(None, "Numero de cheque.")
    dBcoEmi: str = campo(None, "dBcoEmi")


class Cuotas(GrupoSifen):
    """Campos que describen las cuotas.

    Elemento XML: ``gCuotas``. Tipo del esquema: ``tgCuotas``.
    """

    _etiqueta: ClassVar[str] = "gCuotas"

    cMoneCuo: str = campo(None, "cMoneCuo")
    dDMoneCuo: Annotated[
        str, StringConstraints(min_length=3, max_length=20, pattern=".*[^\\s].*")
    ] = campo(None, "Descripcion de la moneda.")
    dMonCuota: Annotated[
        Decimal, Field(ge=0, le=999999999999999.9999, max_digits=19, decimal_places=4)
    ] = campo(None, "Tipo base para los atributos de monto.")
    dVencCuo: (
        Annotated[
            str,
            StringConstraints(
                pattern="[2-9][0-9]{3}-([0][1-9]|[1][0-2])-([0][0-9]|[1-2][0-9]|[3][0-1])"
            ),
        ]
        | None
    ) = campo_opcional(None, "dVencCuo")


class CompPub(GrupoSifen):
    """Campos que describen informaciones de compras publicas.

    Elemento XML: ``gCompPub``. Tipo del esquema: ``tgCompPub``.
    """

    _etiqueta: ClassVar[str] = "gCompPub"

    dModCont: Annotated[
        str, StringConstraints(min_length=2, max_length=2, pattern=".*[^\\s].*")
    ] = campo(None, "Modalidad - Codigo emitido por la DNCP.")
    dEntCont: Annotated[str, StringConstraints(pattern="[0-9]{5}")] = campo(
        None, "Entidad - Codigo de contratacion emitido por la DNCP."
    )
    dAnoCont: int = campo(None, "Anho - Codigo de contratacion emitido por la DNCP.")
    dSecCont: Annotated[str, StringConstraints(pattern="[0-9]{7}")] = campo(
        None, "Secuencia - Codigo de contratacion emitido por la DNCP."
    )
    dFeCodCont: Annotated[
        str,
        StringConstraints(
            pattern="[2-9][0-9]{3}-([0][1-9]|[1][0-2])-([0][0-9]|[1-2][0-9]|[3][0-1])"
        ),
    ] = campo(None, "dFeCodCont")


class CamFE(GrupoSifen):
    """Campos que componen la factura electronica.

    Elemento XML: ``gCamFE``. Tipo del esquema: ``tgCamFE``.
    """

    _etiqueta: ClassVar[str] = "gCamFE"

    iIndPres: int = campo(None, "Indicador de presencia.")
    dDesIndPres: str = campo(None, "Descripcion del indicador de presencia.")
    dFecEmNR: (
        Annotated[
            str,
            StringConstraints(
                pattern="[2-9][0-9]{3}-([0][1-9]|[1][0-2])-([0][0-9]|[1-2][0-9]|[3][0-1])"
            ),
        ]
        | None
    ) = campo_opcional(None, "dFecEmNR")
    gCompPub: CompPub | None = campo_opcional(None, "gCompPub")


class ValorRestaItem(GrupoSifen):
    """Campos que describen los descuentos, anticipos y valor total por item.

    Elemento XML: ``gValorRestaItem``. Tipo del esquema: ``tgValorRestaItem``.
    """

    _etiqueta: ClassVar[str] = "gValorRestaItem"

    dDescItem: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dPorcDesIt: (
        Annotated[Decimal, Field(ge=0, le=100, max_digits=11, decimal_places=8)] | None
    ) = campo_opcional(None, "Tipo de dato base para representar porcentajes.")
    dDescGloItem: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dAntPreUniIt: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dAntGloPreUniIt: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dTotOpeItem: Annotated[
        Decimal,
        Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
    ] = campo(None, "Tipo base para los atributos de monto.")
    dTotOpeGs: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")


class ValorItem(GrupoSifen):
    """Campos que describen el precio, tipo de cambio y valor total de la...

    Campos que describen el precio, tipo de cambio y valor total de la operación por
    ítem.

    Elemento XML: ``gValorItem``. Tipo del esquema: ``tgValorItem``.
    """

    _etiqueta: ClassVar[str] = "gValorItem"

    dPUniProSer: Annotated[
        Decimal,
        Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
    ] = campo(None, "Tipo base para los atributos de monto.")
    dTiCamIt: Annotated[Decimal, Field(max_digits=9, decimal_places=4)] | None = (
        campo_opcional(None, "Tipo base para los tipos de cambio.")
    )
    dTotBruOpeItem: Annotated[
        Decimal,
        Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
    ] = campo(None, "Tipo base para los atributos de monto.")
    gValorRestaItem: ValorRestaItem = campo(None, "gValorRestaItem")


class CamIVA(GrupoSifen):
    """Campos que describen el IVA de la operación por ítem.

    Elemento XML: ``gCamIVA``. Tipo del esquema: ``tgCamIVA``.
    """

    _etiqueta: ClassVar[str] = "gCamIVA"

    iAfecIVA: int = campo(
        None,
        "Forma de afectacion del IVA 1(Gravado), 2(Exonerado), 3(Exento), 4(Gravado parcial).",
    )
    dDesAfecIVA: Literal[
        "Gravado IVA",
        "Exonerado (Art. 100 - Ley 6380/2019)",
        "Exento",
        "Gravado parcial (Grav- Exento)",
    ] = campo(None, "Descripcion de la afectacion del IVA.")
    dPropIVA: Annotated[
        Decimal, Field(ge=0, le=100, max_digits=11, decimal_places=8)
    ] = campo(None, "Tipo de dato base para representar porcentajes.")
    dTasaIVA: Annotated[int, Field(ge=0)] = campo(None, "Tasa del IVA.")
    dBasGravIVA: Annotated[
        Decimal,
        Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
    ] = campo(None, "Tipo base para los atributos de monto.")
    dLiqIVAItem: Annotated[
        Decimal,
        Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
    ] = campo(None, "Tipo base para los atributos de monto.")
    dBasExe: Annotated[
        Decimal,
        Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
    ] = campo(None, "Tipo base para los atributos de monto.")


class CamISC(GrupoSifen):
    """Campos que describen el ISC de la operacion por ítem.

    Elemento XML: ``tgCamISC``. Tipo del esquema: ``tgCamISC``.
    """

    _etiqueta: ClassVar[str] = "tgCamISC"

    cCatISC: int = campo(None, "Categoria de ISC.")
    dDesCatISC: Literal[
        "SECCION I-(Cigarrillos,Tabacos,Esencias y Otros derivados del Tabaco)",
        "SECCION II - (Bebidas con y sin alcohol)",
        "SECCION III - (Alcoholes y Derivados del alcohol)",
        "SECCION IV - (Combustibles)",
        "SECCION V - (Artículos considerados de lujo)",
    ] = campo(None, "Descripcion de categoria de ISC.")
    cTasaISC: int = campo(None, "Tasa del ISC.")
    dBaseGravISC: Annotated[
        Decimal,
        Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
    ] = campo(None, "Tipo base para los atributos de monto.")
    dLiqISCItem: Annotated[
        Decimal,
        Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
    ] = campo(None, "Tipo base para los atributos de monto.")


class RasMerc(GrupoSifen):
    """Grupo de rastreo de la mercaderia.

    Elemento XML: ``gRasMerc``. Tipo del esquema: ``tgRasMerc``.
    """

    _etiqueta: ClassVar[str] = "gRasMerc"

    dNumLote: str | None = campo_opcional(None, "dNumLote")
    dVencMerc: (
        Annotated[
            str,
            StringConstraints(
                pattern="[2-9][0-9]{3}-([0][1-9]|[1][0-2])-([0][0-9]|[1-2][0-9]|[3][0-1])"
            ),
        ]
        | None
    ) = campo_opcional(None, "dVencMerc")
    dNSerie: str | None = campo_opcional(None, "Numero de serie.")
    dNumPedi: str | None = campo_opcional(None, "Numero de pedido.")
    dNumSegui: str | None = campo_opcional(None, "Numero de seguimiento del envio.")
    dNumReg: (
        Annotated[
            str, StringConstraints(min_length=1, max_length=20, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "Tipo de dato alfanumérico de 20 caracteres.")
    dNumRegEntCom: (
        Annotated[
            str, StringConstraints(min_length=1, max_length=20, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "Tipo de dato alfanumérico de 20 caracteres.")
    dNomPro: (
        Annotated[
            str, StringConstraints(min_length=1, max_length=30, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "Nombre del Producto.")


class VehNuevo(GrupoSifen):
    """Sector de automotores nuevos y usados.

    Elemento XML: ``gVehNuevo``. Tipo del esquema: ``tgVehNuevo``.
    """

    _etiqueta: ClassVar[str] = "gVehNuevo"

    iTipOpVN: int | None = campo_opcional(
        None, "Tipo de operacion de venta de vehiculos."
    )
    dDesTipOpVN: str | None = campo_opcional(
        None, "Descripcion del tipo de venta de vehiculos."
    )
    dChasis: Annotated[str, StringConstraints(pattern="[0-9A-Za-z]{17}")] | None = (
        campo_opcional(None, "Chasis.")
    )
    dColor: str | None = campo_opcional(None, "dColor")
    dPotencia: str | None = campo_opcional(None, "Potencia del motor (CV).")
    dCapMot: str | None = campo_opcional(None, "Capacidad del motor (cc).")
    dPNet: (
        Annotated[Decimal, Field(ge=0, le=999999.9999, max_digits=10, decimal_places=4)]
        | None
    ) = campo_opcional(None, "Tipo base para montos.")
    dPBruto: (
        Annotated[Decimal, Field(ge=0, le=999999.9999, max_digits=10, decimal_places=4)]
        | None
    ) = campo_opcional(None, "Tipo base para montos.")
    iTipCom: int | None = campo_opcional(None, "Tipo de combustible.")
    dDesTipCom: str | None = campo_opcional(
        None, "Descripcion del tipo de combustible."
    )
    dNroMotor: str | None = campo_opcional(None, "Numero de motor.")
    dCapTracc: (
        Annotated[Decimal, Field(ge=0, le=999999.9999, max_digits=10, decimal_places=4)]
        | None
    ) = campo_opcional(None, "Tipo base para montos.")
    dAnoFab: str | None = campo_opcional(None, "Anho de fabricacion.")
    cTipVeh: (
        Annotated[
            str, StringConstraints(min_length=4, max_length=10, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "Tipo de vehículo.")
    dCapac: str | None = campo_opcional(None, "Capacidad máxima de pasajeros.")
    dCilin: str | None = campo_opcional(None, "Cilindradas del motor.")


class GrupEner(GrupoSifen):
    """Grupo del sector de energia electrica.

    Elemento XML: ``gGrupEner``. Tipo del esquema: ``tgGrupEner``.
    """

    _etiqueta: ClassVar[str] = "gGrupEner"

    dNroMed: str | None = campo_opcional(None, "Numero de medidor.")
    dActiv: str | None = campo_opcional(None, "Codigo de actividad.")
    dCateg: str | None = campo_opcional(None, "Codigo de categoría.")
    dLecAnt: (
        Annotated[
            Decimal, Field(ge=0, le=99999999999.99, max_digits=13, decimal_places=2)
        ]
        | None
    ) = campo_opcional(None, "Lectura energía.")
    dLecAct: (
        Annotated[
            Decimal, Field(ge=0, le=99999999999.99, max_digits=13, decimal_places=2)
        ]
        | None
    ) = campo_opcional(None, "Lectura energía.")
    dConKwh: (
        Annotated[
            Decimal, Field(ge=0, le=99999999999.99, max_digits=13, decimal_places=2)
        ]
        | None
    ) = campo_opcional(None, "Lectura energía.")


class GrupSup(GrupoSifen):
    """Grupo del sector de supermercados.

    Elemento XML: ``gGrupSup``. Tipo del esquema: ``tgGrupSup``.
    """

    _etiqueta: ClassVar[str] = "gGrupSup"

    dNomCaj: str | None = campo_opcional(None, "Nombre del cajero.")
    dEfectivo: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.9999, max_digits=19, decimal_places=4),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dVuelto: (
        Annotated[Decimal, Field(ge=0, le=999999.9999, max_digits=10, decimal_places=4)]
        | None
    ) = campo_opcional(None, "Tipo base para montos.")
    dDonac: (
        Annotated[Decimal, Field(ge=0, le=999999.9999, max_digits=10, decimal_places=4)]
        | None
    ) = campo_opcional(None, "Tipo base para montos.")
    dDesDonac: str | None = campo_opcional(None, "Descripcion de la donacion.")


class GrupPolSeg(GrupoSifen):
    """Póliza de seguros.

    Elemento XML: ``gGrupPolSeg``. Tipo del esquema: ``tgGrupPolSeg``.
    """

    _etiqueta: ClassVar[str] = "gGrupPolSeg"

    dPoliza: Annotated[
        str, StringConstraints(min_length=1, max_length=20, pattern=".*[^\\s].*")
    ] = campo(None, "Codigo de poliza.")
    dUnidVig: str = campo(None, "Descripción de la unidad de tiempo de vigencia.")
    dVigencia: Annotated[Decimal, Field(le=99999.9, max_digits=6, decimal_places=1)] = (
        campo(None, "Vigencia de póliza de seguro.")
    )
    dNumPoliza: str = campo(None, "Número de la póliza.")
    dFecIniVig: datetime | None = campo_opcional(
        None, "Normalizador de Fecha y Hora AAAA-MM-DDThh:mm:ss."
    )
    dFecFinVig: datetime | None = campo_opcional(
        None, "Normalizador de Fecha y Hora AAAA-MM-DDThh:mm:ss."
    )
    dCodInt: str | None = campo_opcional(None, "Código interno del ítem.")


class GrupSeg(GrupoSifen):
    """Datos del sector de seguros.

    Elemento XML: ``gGrupSeg``. Tipo del esquema: ``tgGrupSeg``.
    """

    _etiqueta: ClassVar[str] = "gGrupSeg"

    dCodEmpSeg: str | None = campo_opcional(
        None,
        "Codigo de la empresa de seguros en la Superintedencia Nacional de Seguros.",
    )
    gGrupPolSeg: tuple[GrupPolSeg, ...] = campo_opcional(None, "gGrupPolSeg")


class GrupAdi(GrupoSifen):
    """Grupo de datos adicionales de uso comercial.

    Elemento XML: ``gGrupAdi``. Tipo del esquema: ``tgGrupAdi``.
    """

    _etiqueta: ClassVar[str] = "gGrupAdi"

    dCiclo: str | None = campo_opcional(None, "dCiclo")
    dFecIniC: date | None = campo_opcional(None, "Fecha inicio de vigencia de SIFEN.")
    dFecFinC: (
        Annotated[
            str,
            StringConstraints(
                pattern="[2-9][0-9]{3}-([0][1-9]|[1][0-2])-([0][0-9]|[1-2][0-9]|[3][0-1])"
            ),
        ]
        | None
    ) = campo_opcional(None, "dFecFinC")
    dVencPag: tuple[
        Annotated[
            str,
            StringConstraints(
                pattern="[2-9][0-9]{3}-([0][1-9]|[1][0-2])-([0][0-9]|[1-2][0-9]|[3][0-1])"
            ),
        ],
        ...,
    ] = campo_opcional(None, "dVencPag")
    dContrato: str | None = campo_opcional(None, "Numero de contrato.")
    dSalAnt: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.9999, max_digits=19, decimal_places=4),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dCodConDncp: str | None = campo_opcional(None, "Codigo de contratacion de la DNCP.")


class CamEsp(GrupoSifen):
    """Campos complementarios comerciales de uso especifico.

    Elemento XML: ``gCamEsp``. Tipo del esquema: ``tgCamEsp``.
    """

    _etiqueta: ClassVar[str] = "gCamEsp"

    gGrupEner: tuple[GrupEner, ...] = campo_opcional(None, "gGrupEner")
    gGrupSeg: GrupSeg | None = campo_opcional(None, "gGrupSeg")
    gGrupSup: GrupSup | None = campo_opcional(None, "gGrupSup")
    gGrupAdi: GrupAdi | None = campo_opcional(None, "gGrupAdi")


class CamItem(GrupoSifen):
    """Campos que describen los items de la operacion.

    Elemento XML: ``gCamItem``. Tipo del esquema: ``tgCamItem``.
    """

    _etiqueta: ClassVar[str] = "gCamItem"

    dCodInt: Annotated[
        str, StringConstraints(min_length=1, max_length=50, pattern=".*[^\\s].*")
    ] = campo(None, "Codigo interno de mercaderia.")
    dParAranc: Annotated[str, StringConstraints(pattern="[0-9]{4}")] | None = (
        campo_opcional(None, "Partida arancelaria.")
    )
    dNCM: Annotated[str, StringConstraints(pattern="[0-9]{6,8}")] | None = (
        campo_opcional(None, "Nomenclatura comun del MERCOSUR (NCM).")
    )
    dDncpG: Annotated[str, StringConstraints(pattern="[0-9]{8}")] | None = (
        campo_opcional(None, "Codigo DNCP - Nivel General.")
    )
    dDncpE: Annotated[str, StringConstraints(pattern="[0-9]{3,4}")] | None = (
        campo_opcional(None, "Codigo DNCP - Nivel Especifico.")
    )
    dGtin: Annotated[str, StringConstraints(pattern="[0-9]{8,14}")] | None = (
        campo_opcional(None, "Codigo GTIN por Producto y por Paquete.")
    )
    dGtinPq: Annotated[str, StringConstraints(pattern="[0-9]{8,14}")] | None = (
        campo_opcional(None, "Codigo GTIN por Producto y por Paquete.")
    )
    dDesProSer: str = campo(None, "dDesProSer")
    cUniMed: str = campo(None, "cUniMed")
    dDesUniMed: str = campo(None, "dDesUniMed")
    dCantProSer: Annotated[
        Decimal, Field(ge=0, le=9999999999.99999999, max_digits=18, decimal_places=8)
    ] = campo(None, "Cantidad del producto/servicio.")
    cPaisOrig: str | None = campo_opcional(None, "cPaisOrig")
    dDesPaisOrig: (
        Annotated[
            str, StringConstraints(min_length=4, max_length=50, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "dDesPaisOrig")
    dInfItem: str | None = campo_opcional(None, "dInfItem")
    cRelMerc: int | None = campo_opcional(
        None,
        "Código de datos de relevancia de las mercaderías : 1(Tolerancia de quiebra), 2(Tolerancia de merma).",
    )
    dDesRelMerc: Literal["Tolerancia de quiebra", "Tolerancia de merma"] | None = (
        campo_opcional(
            None,
            "Descripcion del Código de datos de relevancia de las mercaderías : 1(Tolerancia de quiebra), 2(Tolerancia de merma).",
        )
    )
    dCanQuiMer: str | None = campo_opcional(None, "dCanQuiMer")
    dPorQuiMer: (
        Annotated[Decimal, Field(ge=0, le=100, max_digits=11, decimal_places=8)] | None
    ) = campo_opcional(None, "Tipo de dato base para representar porcentajes.")
    dCDCAnticipo: (
        Annotated[
            str,
            StringConstraints(
                min_length=44,
                max_length=44,
                pattern="[0-9]{2}([0-9]{7}[0-9A-D])[0-9]{34}",
            ),
        ]
        | None
    ) = campo_opcional(None, "Codigo de Control del Documento Electronico.")
    gValorItem: ValorItem | None = campo_opcional(None, "gValorItem")
    gCamIVA: CamIVA | None = campo_opcional(None, "gCamIVA")
    gRasMerc: RasMerc | None = campo_opcional(None, "gRasMerc")
    gVehNuevo: VehNuevo | None = campo_opcional(None, "gVehNuevo")


class CamAE(GrupoSifen):
    """Campos que componen la Autofatura electrónica.

    Elemento XML: ``gCamAE``. Tipo del esquema: ``tgCamAE``.
    """

    _etiqueta: ClassVar[str] = "gCamAE"

    iNatVen: int = campo(
        None, "Naturaleza del vendedor: 1(No Contribuyente), 2(Extranjero)."
    )
    dDesNatVen: Literal["No contribuyente", "Extranjero"] = campo(
        None, "Descripcion del vendedor: 1(No contribuyente). 2(Extranjero)."
    )
    iTipIDVen: int = campo(None, "Tipo de documento de identidad del vendedor.")
    dDTipIDVen: Literal[
        "Cédula paraguaya", "Pasaporte", "Cédula extranjera", "Carnet de residencia"
    ] = campo(None, "Descripcion del tipo de documento de identidad.")
    dNumIDVen: Annotated[str, StringConstraints(pattern="[0-9A-Za-z\\-]{1,20}")] = (
        campo(None, "Numero de documento de identidad.")
    )
    dNomVen: Annotated[
        str, StringConstraints(min_length=4, max_length=60, pattern=".*[^\\s].*")
    ] = campo(None, "Nombre o razón social.")
    dDirVen: Annotated[
        str, StringConstraints(min_length=1, max_length=255, pattern=".*[^\\s].*")
    ] = campo(None, "Tipo de dato para dirección de 255 caracteres.")
    dNumCasVen: Annotated[int, Field(ge=0)] = campo(None, "Numero de casa.")
    cDepVen: str = campo(None, "cDepVen")
    dDesDepVen: str = campo(None, "dDesDepVen")
    cDisVen: int | None = campo_opcional(
        None, "Código del distrito donde se realiza la transacción."
    )
    dDesDisVen: (
        Annotated[
            str, StringConstraints(min_length=1, max_length=30, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(
        None, "Descripción del distrito donde se realiza la transacción."
    )
    cCiuVen: int = campo(None, "Código de la ciudad donde se realiza la transacción.")
    dDesCiuVen: Annotated[
        str, StringConstraints(min_length=1, max_length=30, pattern=".*[^\\s].*")
    ] = campo(None, "Descripción de la ciudad donde se realiza la transacción.")
    dDirProv: Annotated[
        str, StringConstraints(min_length=1, max_length=255, pattern=".*[^\\s].*")
    ] = campo(None, "Tipo de dato para dirección de 255 caracteres.")
    cDepProv: str = campo(None, "cDepProv")
    dDesDepProv: str = campo(None, "dDesDepProv")
    cDisProv: int | None = campo_opcional(
        None, "Código del distrito donde se realiza la transacción."
    )
    dDesDisProv: (
        Annotated[
            str, StringConstraints(min_length=1, max_length=30, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(
        None, "Descripción del distrito donde se realiza la transacción."
    )
    cCiuProv: int = campo(None, "Código de la ciudad donde se realiza la transacción.")
    dDesCiuProv: Annotated[
        str, StringConstraints(min_length=1, max_length=30, pattern=".*[^\\s].*")
    ] = campo(None, "Descripción de la ciudad donde se realiza la transacción.")


class CamNCDE(GrupoSifen):
    """Campos que componen la Nota de credito/Debito Electronica.

    Elemento XML: ``gCamNCDE``. Tipo del esquema: ``tgCamNCDE``.
    """

    _etiqueta: ClassVar[str] = "gCamNCDE"

    iMotEmi: Annotated[str, StringConstraints(min_length=1, pattern="[1-8]")] = campo(
        None, "Motivo de emision de la nota de credito/debito electronica."
    )
    dDesMotEmi: Literal[
        "Devolución y Ajuste de precios",
        "Devolución",
        "Descuento",
        "Bonificación",
        "Crédito incobrable",
        "Recupero de costo",
        "Recupero de gasto",
        "Ajuste de precio",
    ] = campo(
        None, "Descripcion del motivo de la emision de la nota de credito/debito."
    )


class CamNRE(GrupoSifen):
    """Campos que componen la nora de remision electronica.

    Elemento XML: ``gCamNRE``. Tipo del esquema: ``tgCamNRE``.
    """

    _etiqueta: ClassVar[str] = "gCamNRE"

    iMotEmiNR: int = campo(None, "Motivo de emisión.")
    dDesMotEmiNR: str = campo(None, "Descripcion del motivo de emisión.")
    iRespEmiNR: int = campo(
        None, "Responsable por la emisión de la Nota de Remisión Electrónica."
    )
    dDesRespEmiNR: str = campo(
        None,
        "Descripción del Responsable de la emisión de la Nota de Remisión Electrónica.",
    )
    dKmR: str = campo(None, "Kilometros estimados de recorrido.")
    dFecEm: (
        Annotated[
            str,
            StringConstraints(
                pattern="[2-9][0-9]{3}-([0][1-9]|[1][0-2])-([0][0-9]|[1-2][0-9]|[3][0-1])"
            ),
        ]
        | None
    ) = campo_opcional(None, "dFecEm")
    cPreFle: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")


class PagCont(GrupoSifen):
    """Campos que describen la forma de pago al contado.

    Elemento XML: ``gPaConEIni``. Tipo del esquema: ``tgPagCont``.
    """

    _etiqueta: ClassVar[str] = "gPaConEIni"

    iTiPago: int = campo(None, "Codigo de tipo de pago.")
    dDesTiPag: str = campo(None, "Descripcion del tipo de pago.")
    dMonTiPag: Annotated[
        Decimal, Field(ge=0, le=999999999999999.9999, max_digits=19, decimal_places=4)
    ] = campo(None, "Tipo base para los atributos de monto.")
    cMoneTiPag: str = campo(None, "cMoneTiPag")
    dDMoneTiPag: Annotated[
        str, StringConstraints(min_length=3, max_length=20, pattern=".*[^\\s].*")
    ] = campo(None, "Descripcion de la moneda.")
    dTiCamTiPag: Annotated[Decimal, Field(max_digits=9, decimal_places=4)] | None = (
        campo_opcional(None, "Tipo base para los tipos de cambio.")
    )
    gPagTarCD: PagTarCD | None = campo_opcional(None, "gPagTarCD")
    gPagCheq: PagCheq | None = campo_opcional(None, "gPagCheq")


class PagCred(GrupoSifen):
    """Campos que describen la operación a crédito.

    Elemento XML: ``gPagCred``. Tipo del esquema: ``tgPagCred``.
    """

    _etiqueta: ClassVar[str] = "gPagCred"

    iCondCred: str = campo(None, "Condicion de la operacion de credito.")
    dDCondCred: Literal["Plazo", "Cuota"] = campo(
        None, "Descripción de la condición de la operación a crédito."
    )
    dPlazoCre: str | None = campo_opcional(None, "Plazo del crédito.")
    dCuotas: str | None = campo_opcional(None, "Cantidad de cuotas.")
    dMonEnt: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.9999, max_digits=19, decimal_places=4),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    gCuotas: tuple[Cuotas, ...] = campo_opcional(None, "gCuotas")


class CamCond(GrupoSifen):
    """Campos que describen la condición de la operación.

    Elemento XML: ``gCamCond``. Tipo del esquema: ``tgCamCond``.
    """

    _etiqueta: ClassVar[str] = "gCamCond"

    iCondOpe: int = campo(None, "Condicion de la operacion.")
    dDCondOpe: Literal["Contado", "Crédito"] = campo(
        None, "Descripcion de condicion de operacion."
    )
    gPaConEIni: tuple[PagCont, ...] = campo_opcional(None, "gPaConEIni")
    gPagCred: PagCred | None = campo_opcional(None, "gPagCred")


class CamSal(GrupoSifen):
    """Campos que identifican el local de salida de las mercaderías.

    Elemento XML: ``gCamSal``. Tipo del esquema: ``tgCamSal``.
    """

    _etiqueta: ClassVar[str] = "gCamSal"

    dDirLocSal: Annotated[
        str, StringConstraints(min_length=1, max_length=255, pattern=".*[^\\s].*")
    ] = campo(None, "Tipo de dato para dirección de 255 caracteres.")
    dNumCasSal: Annotated[int, Field(ge=0)] = campo(None, "Numero de casa.")
    dComp1Sal: (
        Annotated[
            str, StringConstraints(min_length=1, max_length=255, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "Tipo de dato para dirección de 255 caracteres.")
    dComp2Sal: (
        Annotated[
            str, StringConstraints(min_length=1, max_length=255, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "Tipo de dato para dirección de 255 caracteres.")
    cDepSal: str = campo(None, "cDepSal")
    dDesDepSal: str = campo(None, "dDesDepSal")
    cDisSal: int | None = campo_opcional(
        None, "Código del distrito donde se realiza la transacción."
    )
    dDesDisSal: (
        Annotated[
            str, StringConstraints(min_length=1, max_length=30, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(
        None, "Descripción del distrito donde se realiza la transacción."
    )
    cCiuSal: int = campo(None, "Código de la ciudad donde se realiza la transacción.")
    dDesCiuSal: Annotated[
        str, StringConstraints(min_length=1, max_length=30, pattern=".*[^\\s].*")
    ] = campo(None, "Descripción de la ciudad donde se realiza la transacción.")
    dTelSal: (
        Annotated[str, StringConstraints(min_length=6, max_length=15, pattern=".+")]
        | None
    ) = campo_opcional(None, "dTelSal")


class CamEnt(GrupoSifen):
    """Campos que identifican el local de entrega de las mercaderías.

    Elemento XML: ``gCamEnt``. Tipo del esquema: ``tgCamEnt``.
    """

    _etiqueta: ClassVar[str] = "gCamEnt"

    dDirLocEnt: Annotated[
        str, StringConstraints(min_length=1, max_length=255, pattern=".*[^\\s].*")
    ] = campo(None, "Tipo de dato para dirección de 255 caracteres.")
    dNumCasEnt: Annotated[int, Field(ge=0)] = campo(None, "Numero de casa.")
    dComp1Ent: (
        Annotated[
            str, StringConstraints(min_length=1, max_length=255, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "Tipo de dato para dirección de 255 caracteres.")
    dComp2Ent: (
        Annotated[
            str, StringConstraints(min_length=1, max_length=255, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "Tipo de dato para dirección de 255 caracteres.")
    cDepEnt: str = campo(None, "cDepEnt")
    dDesDepEnt: str = campo(None, "dDesDepEnt")
    cDisEnt: int | None = campo_opcional(
        None, "Código del distrito donde se realiza la transacción."
    )
    dDesDisEnt: (
        Annotated[
            str, StringConstraints(min_length=1, max_length=30, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(
        None, "Descripción del distrito donde se realiza la transacción."
    )
    cCiuEnt: int = campo(None, "Código de la ciudad donde se realiza la transacción.")
    dDesCiuEnt: Annotated[
        str, StringConstraints(min_length=1, max_length=30, pattern=".*[^\\s].*")
    ] = campo(None, "Descripción de la ciudad donde se realiza la transacción.")
    dTelEnt: (
        Annotated[str, StringConstraints(min_length=6, max_length=15, pattern=".+")]
        | None
    ) = campo_opcional(None, "dTelEnt")


class VehTras(GrupoSifen):
    """Campos que identifican el vehículo de traslado de mercaderías.

    Elemento XML: ``gVehTras``. Tipo del esquema: ``tgVehTras``.
    """

    _etiqueta: ClassVar[str] = "gVehTras"

    dTiVehTras: str = campo(
        None,
        'Tipo de vehículo dentro de la clasificación mencionada en el campo "Modalidad del transporte".',
    )
    dMarVeh: str = campo(None, "Marca.")
    dTipIdenVeh: str = campo(None, "Tipo de identificación del vehículo.")
    dNroIDVeh: str | None = campo_opcional(
        None, "Número de identificación del vehículo."
    )
    dAdicVeh: str | None = campo_opcional(None, "Datos adicionales del vehículo.")
    dNroMatVeh: str | None = campo_opcional(None, "Número de matrícula del vehículo.")
    dNroVuelo: str | None = campo_opcional(None, "Tipo de vehiculo.")


class CamTrans(GrupoSifen):
    """Campos que identifican al transportista (persona física o jurídica).

    Elemento XML: ``gCamTrans``. Tipo del esquema: ``tgCamTrans``.
    """

    _etiqueta: ClassVar[str] = "gCamTrans"

    iNatTrans: int = campo(
        None, "Naturaleza del receptor: 1(Contribuyente), 2(No Contribuyente)."
    )
    dNomTrans: Annotated[
        str, StringConstraints(min_length=4, max_length=60, pattern=".*[^\\s].*")
    ] = campo(None, "Nombre o razón social.")
    dRucTrans: (
        Annotated[
            str,
            StringConstraints(
                min_length=3, max_length=8, pattern="[1-9][0-9]*[0-9A-D]?"
            ),
        ]
        | None
    ) = campo_opcional(None, "dRucTrans")
    dDVTrans: int | None = campo_opcional(None, "dDVTrans")
    iTipIDTrans: int | None = campo_opcional(
        None, "Tipo de documento de identidad del vendedor."
    )
    dDTipIDTrans: (
        Literal[
            "Cédula paraguaya", "Pasaporte", "Cédula extranjera", "Carnet de residencia"
        ]
        | None
    ) = campo_opcional(None, "Descripcion del tipo de documento de identidad.")
    dNumIDTrans: (
        Annotated[str, StringConstraints(pattern="[0-9A-Za-z\\-]{1,20}")] | None
    ) = campo_opcional(None, "Numero de documento de identidad.")
    cNacTrans: str | None = campo_opcional(None, "cNacTrans")
    dDesNacTrans: (
        Annotated[
            str, StringConstraints(min_length=4, max_length=50, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "dDesNacTrans")
    dNumIDChof: Annotated[str, StringConstraints(pattern="[0-9A-Za-z\\-]{1,20}")] = (
        campo(None, "Numero de documento de identidad.")
    )
    dNomChof: Annotated[
        str, StringConstraints(min_length=4, max_length=60, pattern=".*[^\\s].*")
    ] = campo(None, "Nombre o razón social.")
    dDomFisc: str = campo(None, "dDomFisc")
    dDirChof: Annotated[
        str, StringConstraints(min_length=1, max_length=255, pattern=".*[^\\s].*")
    ] = campo(None, "Tipo de dato para dirección de 255 caracteres.")
    dNombAg: (
        Annotated[
            str, StringConstraints(min_length=4, max_length=60, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "Nombre o razón social.")
    dRucAg: (
        Annotated[
            str,
            StringConstraints(
                min_length=3, max_length=8, pattern="[1-9][0-9]*[0-9A-D]?"
            ),
        ]
        | None
    ) = campo_opcional(None, "dRucAg")
    dDVAg: int | None = campo_opcional(None, "dDVAg")
    dDirAge: (
        Annotated[
            str, StringConstraints(min_length=1, max_length=255, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "Tipo de dato para dirección de 255 caracteres.")


class Transp(GrupoSifen):
    """Campos que describen el transporte de mercaderias.

    Elemento XML: ``gTransp``. Tipo del esquema: ``tgTransp``.
    """

    _etiqueta: ClassVar[str] = "gTransp"

    iTipTrans: Annotated[int, Field(ge=1)] | None = campo_opcional(
        None, "Tipo de transporte."
    )
    dDesTipTrans: Literal["Propio", "Tercero"] | None = campo_opcional(
        None, "Descripcion del tipo de transporte."
    )
    iModTrans: int = campo(None, "Modalidad del transporte.")
    dDesModTrans: Literal["Terrestre", "Fluvial", "Aéreo", "Multimodal"] = campo(
        None, "Descripcion de la Modalidad de transporte."
    )
    iRespFlete: int = campo(None, "Responsable por el costo del flete.")
    cCondNeg: (
        Literal[
            "CFR", "CIF", "CIP", "CPT", "DAP", "DAT", "DDP", "EXW", "FAS", "FCA", "FOB"
        ]
        | None
    ) = campo_opcional(None, "Condicion de la negociacion.")
    dNuManif: str | None = campo_opcional(
        None,
        "Número de manifiesto o conocimiento de carga/ declaración de tránsito aduanero/ Carta de porte internacional.",
    )
    dNuDespImp: str | None = campo_opcional(None, "Numero de despacho de importación.")
    dIniTras: date | None = campo_opcional(None, "Fecha inicio de vigencia de SIFEN.")
    dFinTras: (
        Annotated[
            str,
            StringConstraints(
                pattern="[2-9][0-9]{3}-([0][1-9]|[1][0-2])-([0][0-9]|[1-2][0-9]|[3][0-1])"
            ),
        ]
        | None
    ) = campo_opcional(None, "dFinTras")
    cPaisDest: str | None = campo_opcional(None, "cPaisDest")
    dDesPaisDest: (
        Annotated[
            str, StringConstraints(min_length=4, max_length=50, pattern=".*[^\\s].*")
        ]
        | None
    ) = campo_opcional(None, "dDesPaisDest")
    gCamSal: CamSal | None = campo_opcional(None, "gCamSal")
    gCamEnt: tuple[CamEnt, ...] = campo_opcional(None, "gCamEnt")
    gVehTras: tuple[VehTras, ...] = campo_opcional(None, "gVehTras")
    gCamTrans: CamTrans | None = campo_opcional(None, "gCamTrans")


class CamRDE(GrupoSifen):
    """Campos que componen el Recibo de Dinero Electrónico.

    Elemento XML: ``gCamRDE``. Tipo del esquema: ``tgCamRDE``.
    """

    _etiqueta: ClassVar[str] = "gCamRDE"

    iForPag: int = campo(None, "Código de Forma de Pago.")
    dDesForPag: str = campo(None, "Descripción de la Forma de Pago.")
    dNumTrans: str | None = campo_opcional(None, "Número de Transacción.")
    dConc: str = campo(None, "Concepto/Observación.")
    dRucEntFin: (
        Annotated[
            str,
            StringConstraints(
                min_length=3, max_length=8, pattern="[1-9][0-9]*[0-9A-D]?"
            ),
        ]
        | None
    ) = campo_opcional(None, "dRucEntFin")
    dDvEntFin: int | None = campo_opcional(None, "dDvEntFin")
    dNomEntFin: str | None = campo_opcional(
        None, "Nombre o Razón Social de la Entidad Financiera."
    )
    dImpPag: Annotated[
        Decimal, Field(ge=0, le=999999999999999.9999, max_digits=19, decimal_places=4)
    ] = campo(None, "Tipo base para los atributos de monto.")


class DtipDE(GrupoSifen):
    """Campos específicos por tipo de documento electronico.

    Elemento XML: ``gDtipDE``. Tipo del esquema: ``tgDtipDE``.
    """

    _etiqueta: ClassVar[str] = "gDtipDE"

    gCamFE: CamFE | None = campo_opcional(None, "gCamFE")
    gCamAE: CamAE | None = campo_opcional(None, "gCamAE")
    gCamNCDE: CamNCDE | None = campo_opcional(None, "gCamNCDE")
    gCamNRE: CamNRE | None = campo_opcional(None, "gCamNRE")
    gCamCond: CamCond | None = campo_opcional(None, "gCamCond")
    gCamItem: tuple[CamItem, ...] = campo_opcional(None, "gCamItem")
    gCamEsp: CamEsp | None = campo_opcional(None, "gCamEsp")
    gTransp: Transp | None = campo_opcional(None, "gTransp")
    gCamRDE: tuple[CamRDE, ...] = campo_opcional(None, "gCamRDE")


class CamFEI(GrupoSifen):
    """Campos que componen la factura electronica de importacion FEI.

    Elemento XML: ``tgCamFEI``. Tipo del esquema: ``tgCamFEI``.
    """

    _etiqueta: ClassVar[str] = "tgCamFEI"

    cTipRegImp: Annotated[str, StringConstraints(pattern="[0-9]{4}")] = campo(
        None, "Regimenes Aduaneros."
    )
    dPuLleg: str = campo(None, "dPuLleg")
    dNuDesp: str = campo(None, "dNuDesp")
    dFecDesp: Annotated[
        str,
        StringConstraints(
            pattern="[2-9][0-9]{3}-([0][1-9]|[1][0-2])-([0][0-9]|[1-2][0-9]|[3][0-1])"
        ),
    ] = campo(None, "dFecDesp")
    dNomDesp: str = campo(None, "dNomDesp")
    dRucDesp: Annotated[
        str,
        StringConstraints(min_length=3, max_length=8, pattern="[1-9][0-9]*[0-9A-D]?"),
    ] = campo(None, "dRucDesp")
    dDVDesp: int = campo(None, "dDVDesp")
    cPaisProd: str = campo(None, "cPaisProd")
    dDesPaisProd: Annotated[
        str, StringConstraints(min_length=4, max_length=50, pattern=".*[^\\s].*")
    ] = campo(None, "dDesPaisProd")
    dVend: str = campo(None, "dVend")
    dValorInv: str = campo(None, "dValorInv")
    dValorFle: str = campo(None, "dValorFle")
    dValorSeg: str = campo(None, "dValorSeg")
    dValorImpGs: str = campo(None, "dValorImpGs")
    dDerAdu: str = campo(None, "dDerAdu")
    dIndi: str = campo(None, "dIndi")
    dSerValor: str = campo(None, "dSerValor")
    dIVAImp: str = campo(None, "dIVAImp")
    dTasaIntAd: str = campo(None, "dTasaIntAd")


class CamFEE(GrupoSifen):
    """Campos que componen la factura electronica de exportacion.

    Elemento XML: ``tgCamFEE``. Tipo del esquema: ``tgCamFEE``.
    """

    _etiqueta: ClassVar[str] = "tgCamFEE"

    cFleExp: str = campo(None, "cFleExp")
    dDesFleExp: Annotated[
        str, StringConstraints(min_length=4, max_length=50, pattern=".*[^\\s].*")
    ] = campo(None, "dDesFleExp")
    dPuEmb: str = campo(None, "Puerto de embarque.")


class TotSub(GrupoSifen):
    """F. Campos que describen los subtotales y totales de la transacción...

    F. Campos que describen los subtotales y totales de la transacción documentada.

    Elemento XML: ``gTotSub``. Tipo del esquema: ``tgTotSub``.
    """

    _etiqueta: ClassVar[str] = "gTotSub"

    dSubExe: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dSubExo: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dSub5: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dSub10: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dTotOpe: Annotated[
        Decimal,
        Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
    ] = campo(None, "Tipo base para los atributos de monto.")
    dTotDesc: Annotated[
        Decimal,
        Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
    ] = campo(None, "Tipo base para los atributos de monto.")
    dTotDescGlotem: Annotated[
        Decimal,
        Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
    ] = campo(None, "Tipo base para los atributos de monto.")
    dTotAntItem: Annotated[
        Decimal,
        Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
    ] = campo(None, "Tipo base para los atributos de monto.")
    dTotAnt: Annotated[
        Decimal,
        Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
    ] = campo(None, "Tipo base para los atributos de monto.")
    dPorcDescTotal: Annotated[
        Decimal, Field(ge=0, le=100, max_digits=11, decimal_places=8)
    ] = campo(None, "Tipo de dato base para representar porcentajes.")
    dDescTotal: Annotated[
        Decimal,
        Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
    ] = campo(None, "Tipo base para los atributos de monto.")
    dAnticipo: Annotated[
        Decimal,
        Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
    ] = campo(None, "Tipo base para los atributos de monto.")
    dRedon: Annotated[
        Decimal, Field(ge=0, le=9999.9999, max_digits=8, decimal_places=4)
    ] = campo(None, "Campo de redondeo.")
    dComi: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dTotGralOpe: Annotated[
        Decimal,
        Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
    ] = campo(None, "Tipo base para los atributos de monto.")
    dIVA5: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dIVA10: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dLiqTotIVA5: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dLiqTotIVA10: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dIVAComi: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dTotIVA: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dBaseGrav5: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dBaseGrav10: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dTBasGraIVA: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")
    dTotalGs: (
        Annotated[
            Decimal,
            Field(ge=0, le=999999999999999.99999999, max_digits=23, decimal_places=8),
        ]
        | None
    ) = campo_opcional(None, "Tipo base para los atributos de monto.")


class CamCarg(GrupoSifen):
    """Campos generales de la carga.

    Elemento XML: ``gCamCarg``. Tipo del esquema: ``tgCamCarg``.
    """

    _etiqueta: ClassVar[str] = "gCamCarg"

    cUniMedTotVol: str | None = campo_opcional(None, "cUniMedTotVol")
    dDesUniMedTotVol: str | None = campo_opcional(None, "dDesUniMedTotVol")
    dTotVolMerc: str | None = campo_opcional(None, "Total volumen de la mercaderia.")
    cUniMedTotPes: str | None = campo_opcional(None, "cUniMedTotPes")
    dDesUniMedTotPes: str | None = campo_opcional(None, "dDesUniMedTotPes")
    dTotPesMerc: str | None = campo_opcional(None, "Total peso de la mercadería.")
    iCarCarga: str | None = campo_opcional(None, "iCarCarga")
    dDesCarCarga: str | None = campo_opcional(None, "dDesCarCarga")


class CamGen(GrupoSifen):
    """Campos complementarios comerciales de uso general.

    Elemento XML: ``gCamGen``. Tipo del esquema: ``tgCamGen``.
    """

    _etiqueta: ClassVar[str] = "gCamGen"

    dOrdCompra: str | None = campo_opcional(None, "Numero de orden de compra.")
    dOrdVta: str | None = campo_opcional(None, "Numero de orden de venta.")
    dAsiento: str | None = campo_opcional(None, "Número de asiento contable.")
    gCamCarg: CamCarg | None = campo_opcional(None, "gCamCarg")


class CamDEAsoc(GrupoSifen):
    """Campos que identifican al documento asociado.

    Elemento XML: ``gCamDEAsoc``. Tipo del esquema: ``tgCamDEAsoc``.
    """

    _etiqueta: ClassVar[str] = "gCamDEAsoc"

    iTipDocAso: int = campo(None, "Tipo de documento asociado.")
    dDesTipDocAso: Literal["Electrónico", "Impreso", "Constancia Electrónica"] = campo(
        None, "Descripcion del tipo de documento asociado."
    )
    dCdCDERef: (
        Annotated[
            str,
            StringConstraints(
                min_length=44,
                max_length=44,
                pattern="[0-9]{2}([0-9]{7}[0-9A-D])[0-9]{34}",
            ),
        ]
        | None
    ) = campo_opcional(None, "Codigo de Control del Documento Electronico.")
    dNTimDI: str | None = campo_opcional(
        None, "Numero de timbrado del documento electronico."
    )
    dEstDocAso: (
        Annotated[str, StringConstraints(min_length=3, pattern="[0-9]{3}")] | None
    ) = campo_opcional(
        None, "Codigo de establecimiento proveido por el Sistema de timbrado."
    )
    dPExpDocAso: (
        Annotated[str, StringConstraints(min_length=3, pattern="[0-9]{3}")] | None
    ) = campo_opcional(None, "Codigo de Punto de Exp. proveido por el Sist.Timbrado.")
    dNumDocAso: (
        Annotated[
            str,
            StringConstraints(
                min_length=7, max_length=7, pattern="0+[1-9][0-9]*|[1-9]+[0-9]+"
            ),
        ]
        | None
    ) = campo_opcional(None, "Numero de documento del DE.")
    iTipoDocAso: int | None = campo_opcional(None, "Tipos de documentos impresos.")
    dDTipoDocAso: (
        Literal["Factura", "Nota de crédito", "Nota de débito", "Nota de remisión"]
        | None
    ) = campo_opcional(None, "Tipos de documentos impresos.")
    dFecEmiDI: (
        Annotated[
            str,
            StringConstraints(
                pattern="[2-9][0-9]{3}-([0][1-9]|[1][0-2])-([0][0-9]|[1-2][0-9]|[3][0-1])"
            ),
        ]
        | None
    ) = campo_opcional(None, "dFecEmiDI")
    dNumComRet: str | None = campo_opcional(None, "Numero de comprobante de retencion.")
    dNumResCF: str | None = campo_opcional(
        None, "Numero de resolucion de Credito Fiscal."
    )
    iTipCons: int | None = campo_opcional(
        None, "Tipo de constancia de autofactura electronica."
    )
    dDesTipCons: (
        Literal["Constancia de no ser contribuyente", "Constancia de microproductores"]
        | None
    ) = campo_opcional(None, "Descripción del tipo de constancia.")
    dNumCons: str | None = campo_opcional(None, "Numero de constancia.")
    dNumControl: str | None = campo_opcional(
        None, "Numero de control de la constancia."
    )
    dRucFus: (
        Annotated[
            str,
            StringConstraints(
                min_length=3, max_length=8, pattern="[1-9][0-9]*[0-9A-D]?"
            ),
        ]
        | None
    ) = campo_opcional(None, "dRucFus")
    dNumCuoDocAso: str | None = campo_opcional(None, "dNumCuoDocAso")
    dImpCuoDocAso: str | None = campo_opcional(None, "dImpCuoDocAso")


class DocumentoElectronico(GrupoSifen):
    """Campos firmados del DE.

    Elemento XML: ``DE``. Tipo del esquema: ``tDE``.
    """

    _etiqueta: ClassVar[str] = "DE"

    dDVId: int = campo(None, "dDVId")
    dFecFirma: datetime = campo(
        None, "Normalizador de Fecha y Hora AAAA-MM-DDThh:mm:ss."
    )
    dSisFact: str = campo(None, "1-Sistema de facturación del contribuyente.")
    gOpeDE: COpeDE = campo(None, "gOpeDE")
    gTimb: DTim = campo(None, "gTimb")
    gDatGralOpe: DaGOC = campo(None, "gDatGralOpe")
    gDtipDE: DtipDE = campo(None, "gDtipDE")
    gTotSub: TotSub | None = campo_opcional(None, "gTotSub")
    gCamGen: CamGen | None = campo_opcional(None, "gCamGen")
    gCamDEAsoc: tuple[CamDEAsoc, ...] = campo_opcional(None, "gCamDEAsoc")


class CamFuFD(GrupoSifen):
    """Campos fuera de la firma digital.

    Elemento XML: ``gCamFuFD``. Tipo del esquema: ``tgCamFuFD``.
    """

    _etiqueta: ClassVar[str] = "gCamFuFD"

    dCarQR: str = campo(None, "Caracteres correspondiente al codigo QR.")
    dInfAdic: str | None = campo_opcional(
        None, "Información adicional de interés para el emisor."
    )


class RDE(GrupoSifen):
    """Grupo rDE del documento electrónico.

    Elemento XML: ``rDE``. Tipo del esquema: ``rDE``.
    """

    _etiqueta: ClassVar[str] = "rDE"

    dVerFor: str = campo(None, "dVerFor")
    DE: DocumentoElectronico = campo(None, "DE")
    gCamFuFD: CamFuFD = campo(None, "gCamFuFD")


__all__ = [
    "RDE",
    "ActEco",
    "COpeDE",
    "CamAE",
    "CamCarg",
    "CamCond",
    "CamDEAsoc",
    "CamEnt",
    "CamEsp",
    "CamFE",
    "CamFEE",
    "CamFEI",
    "CamFuFD",
    "CamGen",
    "CamISC",
    "CamIVA",
    "CamItem",
    "CamNCDE",
    "CamNRE",
    "CamRDE",
    "CamSal",
    "CamTrans",
    "CompPub",
    "Cuotas",
    "DTim",
    "DaGOC",
    "DatRec",
    "DocumentoElectronico",
    "DtipDE",
    "Emis",
    "GrupAdi",
    "GrupEner",
    "GrupPolSeg",
    "GrupSeg",
    "GrupSup",
    "OblAfe",
    "OpeCom",
    "PagCheq",
    "PagCont",
    "PagCred",
    "PagTarCD",
    "RasMerc",
    "RespDE",
    "TotSub",
    "Transp",
    "ValorItem",
    "ValorRestaItem",
    "VehNuevo",
    "VehTras",
]
