"""Pruebas de la lectura de un documento a los modelos.

Lo que se prueba acá es que **no se pierda nada**: un documento leído y vuelto
a serializar tiene que dar un XML equivalente al de partida. Es el criterio que
separa "extraigo unos campos con XPath" de "entiendo el documento".

Los documentos de estas pruebas se arman con los propios modelos y se comparan
consigo mismos después de la vuelta. En el repositorio no entra ningún documento
tributario real: traen datos de contribuyentes.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from lxml import etree

from pysifen.documento import (
    CamItem,
    DaGOC,
    DatRec,
    DocumentoElectronico,
    DtipDE,
    Emis,
    Operacion,
    Timbrado,
    documento_desde_xml,
    grupo_desde_elemento,
    sobre_rde,
)
from pysifen.documento.desde_xml import NS_SIFEN
from pysifen.exceptions import SifenError
from tests.conftest import CDC_DEL_MANUAL


def _documento() -> DocumentoElectronico:
    """Un documento que **valida de verdad**, no uno armado a medias.

    Importa que sea completo: la ida y vuelta se hace con
    ``model_validate``, así que un documento al que le falten los grupos
    obligatorios no probaría el camino, probaría el error.
    """
    return DocumentoElectronico(
        dDVId=8,
        dFecFirma=datetime(2026, 9, 10, 10, 0, 0),  # noqa: DTZ001
        dSisFact="1",
        gOpeDE=Operacion(iTipEmi=1, dDesTipEmi="Normal", dCodSeg="000166795"),
        gTimb=Timbrado(
            iTiDE=1,
            dDesTiDE="Factura electrónica",
            dNumTim="12558946",
            dEst="001",
            dPunExp="001",
            dNumDoc="0014528",
            dFeIniT=date(2026, 1, 1),
        ),
        gDatGralOpe=DaGOC(
            dFeEmiDE=datetime(2026, 9, 10, 9, 55, 0),  # noqa: DTZ001
            gEmis=Emis(
                dRucEm="80012345",
                dDVEmi=6,
                iTipCont=2,
                dNomEmi="CONTRIBUYENTE DE PRUEBA S.A.",
                dDirEmi="Avenida Siempreviva 742",
                dNumCas=742,
                cDepEmi="11",
                dDesDepEmi="ALTO PARANA",
                cCiuEmi=1,
                dDesCiuEmi="CIUDAD DEL ESTE",
                dTelEmi="021123456",
                dEmailE="facturacion@ejemplo.com.py",
            ),
            gDatRec=DatRec(
                iNatRec=1,
                iTiOpe=1,
                cPaisRec="PRY",
                dDesPaisRe="Paraguay",
                dNomRec="CLIENTE DE PRUEBA S.A.",
            ),
        ),
        gDtipDE=DtipDE(
            gCamItem=(
                CamItem(
                    dCodInt="ART-001",
                    dDesProSer="Servicio de prueba",
                    cUniMed="77",
                    dDesUniMed="UNI",
                    dCantProSer=Decimal("2.0000"),
                ),
            )
        ),
    )


def _infoset(elemento: etree._Element) -> list[tuple[str, str, dict[str, str]]]:
    """Nombre, texto y atributos de cada elemento, en orden de documento.

    Se compara así y no byte a byte porque el prefijo del espacio de nombres es
    una decisión de serialización, no información: ``<DE xmlns="...">`` y
    ``<ns0:DE xmlns:ns0="...">`` son el mismo documento.
    """
    return [
        (
            etree.QName(e).localname,
            (e.text or "").strip(),
            {etree.QName(k).localname: str(v) for k, v in e.attrib.items()},
        )
        for e in elemento.iter()
        if isinstance(e.tag, str)
    ]


class TestIdaYVuelta:
    """El criterio de la 0.5.0: leer y volver a escribir no pierde nada."""

    def test_un_documento_vuelve_igual(self) -> None:
        original = _documento().a_elemento(NS_SIFEN)
        original.set("Id", CDC_DEL_MANUAL)

        vuelta = documento_desde_xml(etree.tostring(original)).a_elemento(NS_SIFEN)
        vuelta.set("Id", CDC_DEL_MANUAL)

        assert _infoset(vuelta) == _infoset(original)

    def test_desde_el_sobre_completo(self) -> None:
        rde = sobre_rde(_documento(), CDC_DEL_MANUAL)

        de = documento_desde_xml(etree.tostring(rde))

        assert de.gTimb is not None
        assert de.gTimb.dNumTim == "12558946"

    def test_los_grupos_repetibles_vuelven_completos(self) -> None:
        # gCamItem es tuple[CamItem, ...]: si la lectura tomara sólo el primero,
        # una factura de tres renglones volvería con uno.
        original = _documento()
        con_tres = original.model_copy(
            update={
                "gDtipDE": DtipDE(
                    gCamItem=tuple(
                        original.gDtipDE.gCamItem[0].model_copy(
                            update={"dCodInt": f"ART-00{n}"}
                        )
                        for n in range(1, 4)
                    )
                )
            }
        )

        de = documento_desde_xml(etree.tostring(sobre_rde(con_tres, CDC_DEL_MANUAL)))

        assert de.gDtipDE is not None
        assert [i.dCodInt for i in de.gDtipDE.gCamItem] == [
            "ART-001",
            "ART-002",
            "ART-003",
        ]

    def test_desde_un_lote(self) -> None:
        lote = etree.Element("rLoteDE")
        lote.append(sobre_rde(_documento(), CDC_DEL_MANUAL))

        assert documento_desde_xml(lote).dSisFact == "1"


class TestTiposQueSeConservan:
    """Los tipos de Python, no cadenas sueltas."""

    def test_las_fechas_son_fechas(self) -> None:
        de = documento_desde_xml(
            etree.tostring(sobre_rde(_documento(), CDC_DEL_MANUAL))
        )

        assert de.dFecFirma == datetime(2026, 9, 10, 10, 0, 0)  # noqa: DTZ001
        assert de.gTimb is not None
        assert de.gTimb.dFeIniT == date(2026, 1, 1)
        assert de.gDatGralOpe.dFeEmiDE == datetime(2026, 9, 10, 9, 55, 0)  # noqa: DTZ001

    def test_los_ceros_a_la_izquierda_del_codigo_de_seguridad_se_conservan(
        self,
    ) -> None:
        # El esquema declara dCodSeg como xs:integer con pattern [0-9]{9}: el
        # patrón restringe la forma léxica, así que "000166795" es válido y
        # "166795" no. Si el modelo lo guardara como entero, la vuelta
        # produciría un documento que el SIFEN rechaza.
        de = documento_desde_xml(
            etree.tostring(sobre_rde(_documento(), CDC_DEL_MANUAL))
        )

        assert de.gOpeDE is not None
        assert de.gOpeDE.dCodSeg == "000166795"

    def test_los_decimales_conservan_su_escala(self) -> None:
        # El SIFEN escribe 36500.00000000 y el hash del QR se calcula sobre esa
        # cadena exacta: normalizar a 36500 romperia la verificacion.
        item = CamItem(
            dCodInt="ART-001",
            dDesProSer="Servicio de prueba",
            cUniMed="77",
            dDesUniMed="UNI",
            dCantProSer=Decimal("2.00000000"),
        )

        vuelto = grupo_desde_elemento(item.a_elemento(), CamItem)

        assert str(vuelto.dCantProSer) == "2.00000000"


class TestLoQueSeRechaza:
    """Un documento que no es un documento del SIFEN."""

    def test_un_elemento_que_el_grupo_no_declara(self) -> None:
        rde = sobre_rde(_documento(), CDC_DEL_MANUAL)
        de = rde.find(f"{{{NS_SIFEN}}}DE")
        assert de is not None
        etree.SubElement(de, f"{{{NS_SIFEN}}}dInventado").text = "1"

        with pytest.raises(SifenError, match="dInventado"):
            documento_desde_xml(etree.tostring(rde))

    def test_un_valor_que_no_pasa_la_validacion(self) -> None:
        rde = sobre_rde(_documento(), CDC_DEL_MANUAL)
        crudo = etree.tostring(rde).replace(b"<dDVId>8</dDVId>", b"<dDVId>no</dDVId>")

        with pytest.raises(SifenError, match="DocumentoElectronico"):
            documento_desde_xml(crudo)

    def test_un_xml_roto(self) -> None:
        with pytest.raises(SifenError, match="no es XML válido"):
            documento_desde_xml(b"<esto no es xml")

    def test_un_xml_sin_de(self) -> None:
        with pytest.raises(SifenError, match="no encontré"):
            documento_desde_xml(b"<rDE><dVerFor>150</dVerFor></rDE>")


class TestSinEspacioDeNombres:
    """Los documentos también se pueden armar sin espacio de nombres."""

    def test_se_lee_igual(self) -> None:
        suelto = _documento().a_elemento()

        de = documento_desde_xml(etree.tostring(suelto))

        assert de.gOpeDE is not None
        assert de.gOpeDE.dDesTipEmi == "Normal"
