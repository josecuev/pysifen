#!/usr/bin/env python3
"""Genera los modelos del documento electrónico a partir del XSD oficial.

Por qué generar y no escribir a mano
------------------------------------

El documento electrónico tiene 49 grupos, más de 400 campos y 295 valores
enumerados que deben coincidir carácter por carácter. Transcribirlos a mano
garantiza errores, y peor: errores silenciosos, que recién aparecen cuando el
SIFEN rechaza un documento en producción.

El XSD ya tiene todo eso, con precisión: el orden de los elementos, su
obligatoriedad, sus longitudes, sus patrones y sus enumeraciones. Y trae además
la documentación de cada campo, que se convierte en el docstring del modelo. La
documentación de la librería sale entonces de la fuente normativa, no de una
copia que se desactualiza.

Cuando la DNIT publique un esquema nuevo, se vuelve a correr esto y el
diferencial muestra exactamente qué cambió.

Uso::

    python scripts/generar_modelos.py            # regenera el módulo
    python scripts/generar_modelos.py --check    # falla si está desactualizado
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

from lxml import etree

XS = "{http://www.w3.org/2001/XMLSchema}"
RAIZ = Path(__file__).resolve().parent.parent
ESQUEMAS = RAIZ / "src" / "pysifen" / "esquemas"
DESTINO = RAIZ / "src" / "pysifen" / "documento" / "_generado.py"

#: Cómo se traduce cada tipo base del XSD a Python.
TIPOS_BASE = {
    "xs:string": "str",
    "xs:normalizedString": "str",
    "xs:token": "str",
    "xs:integer": "int",
    "xs:positiveInteger": "int",
    "xs:nonNegativeInteger": "int",
    "xs:short": "int",
    "xs:int": "int",
    "xs:long": "int",
    "xs:decimal": "Decimal",
    "xs:double": "Decimal",
    "xs:date": "date",
    "xs:dateTime": "datetime",
    "xs:base64Binary": "str",
}


def cargar_esquema() -> tuple[dict[str, etree._Element], dict[str, etree._Element]]:
    """Lee los XSD y devuelve sus complexTypes y simpleTypes por nombre."""
    complejos: dict[str, etree._Element] = {}
    simples: dict[str, etree._Element] = {}
    for archivo in ("DE_v150.xsd", "DE_Types_v150.xsd"):
        raiz = etree.parse(str(ESQUEMAS / archivo)).getroot()
        for hijo in raiz:
            nombre = hijo.get("name") if isinstance(hijo.tag, str) else None
            if not nombre:
                continue
            if hijo.tag == f"{XS}complexType":
                complejos[nombre] = hijo
            elif hijo.tag == f"{XS}simpleType":
                simples[nombre] = hijo
    return complejos, simples


def documentacion(nodo: etree._Element) -> str:
    """Extrae el texto de ``xs:documentation``, ya limpio."""
    doc = nodo.find(f"{XS}annotation/{XS}documentation")
    if doc is None or not doc.text:
        return ""
    limpio = re.sub(r"\s+", " ", doc.text).strip()
    if limpio and limpio[-1] not in ".!?:":
        limpio += "."
    return limpio


def _restriccion(simple: etree._Element) -> etree._Element | None:
    """Devuelve la ``xs:restriction`` de un simpleType, si la tiene."""
    return simple.find(f"{XS}restriction")


def resolver_base(nombre: str, simples: dict[str, etree._Element]) -> str:
    """Sigue la cadena de restricciones hasta dar con un tipo base de Python."""
    visitados: set[str] = set()
    actual = nombre
    while actual and actual not in visitados:
        visitados.add(actual)
        if actual in TIPOS_BASE:
            return TIPOS_BASE[actual]
        simple = simples.get(actual)
        if simple is None:
            return "str"
        restriccion = _restriccion(simple)
        if restriccion is None:
            # Es una union; se trata como texto libre.
            return "str"
        actual = restriccion.get("base", "")
    return "str"


def enumeraciones(nombre: str, simples: dict[str, etree._Element]) -> list[str]:
    """Devuelve los valores enumerados de un simpleType, si los tiene."""
    simple = simples.get(nombre)
    if simple is None:
        return []
    restriccion = _restriccion(simple)
    if restriccion is None:
        return []
    return [e.get("value", "") for e in restriccion.findall(f"{XS}enumeration")]


def facetas(nombre: str, simples: dict[str, etree._Element]) -> dict[str, str]:
    """Junta las facetas de toda la cadena de restricciones."""
    reunidas: dict[str, str] = {}
    visitados: set[str] = set()
    actual = nombre
    while actual and actual not in visitados and actual not in TIPOS_BASE:
        visitados.add(actual)
        simple = simples.get(actual)
        if simple is None:
            break
        restriccion = _restriccion(simple)
        if restriccion is None:
            break
        for faceta in restriccion:
            if not isinstance(faceta.tag, str):
                continue
            clave = faceta.tag.replace(XS, "")
            if clave != "enumeration" and clave not in reunidas:
                reunidas[clave] = faceta.get("value", "")
        actual = restriccion.get("base", "")
    return reunidas


def anotacion(tipo_xsd: str, simples: dict[str, etree._Element]) -> str:
    """Arma la anotación de tipo de Python para un tipo del XSD."""
    valores = enumeraciones(tipo_xsd, simples)
    base = resolver_base(tipo_xsd, simples)

    if valores and base == "str":
        literales = ", ".join(_texto(v) for v in valores)
        return f"Literal[{literales}]"

    marcas = facetas(tipo_xsd, simples)

    if base == "str":
        # Se arman como diccionario para que no se repita ninguna clave: un
        # tipo puede heredar minLength de su base y declarar length propio, y
        # en ese caso manda el length, que es el más específico.
        limites: dict[str, str] = {}
        if "minLength" in marcas:
            limites["min_length"] = marcas["minLength"]
        if "maxLength" in marcas:
            limites["max_length"] = marcas["maxLength"]
        if "length" in marcas:
            limites["min_length"] = marcas["length"]
            limites["max_length"] = marcas["length"]
        if "pattern" in marcas:
            limites["pattern"] = _texto(marcas["pattern"])
        if limites:
            argumentos = ", ".join(f"{k}={v}" for k, v in limites.items())
            return f"Annotated[str, StringConstraints({argumentos})]"
        return "str"

    if base == "int" and _exige_relleno(marcas.get("pattern")):
        # Un patron del XSD restringe la forma LEXICA, no el valor. Cuando el
        # tipo es entero y el patron exige mas de un digito, lo que el esquema
        # pide es una cantidad minima de caracteres: dCodSeg es xs:integer con
        # pattern [0-9]{9}, asi que 000166795 es valido y 166795 no lo es.
        #
        # Un int de Python no puede representar eso: pierde los ceros a la
        # izquierda y al serializar produce un documento que el SIFEN rechaza.
        # Por eso estos campos van como cadena, que es lo unico que conserva la
        # forma que el esquema pide.
        #
        # No entran aca los patrones que enumeran codigos -[1-2], 1|[4-7]|9|10-
        # porque ahi no hay relleno posible: el entero ya es la forma correcta.
        return f"Annotated[str, StringConstraints(pattern={_texto(marcas['pattern'])})]"

    if base in {"int", "Decimal"}:
        numericos: dict[str, str] = {}
        if "minInclusive" in marcas:
            numericos["ge"] = marcas["minInclusive"]
        if "maxInclusive" in marcas:
            numericos["le"] = marcas["maxInclusive"]
        if base == "Decimal":
            if "totalDigits" in marcas:
                numericos["max_digits"] = marcas["totalDigits"]
            if "fractionDigits" in marcas:
                numericos["decimal_places"] = marcas["fractionDigits"]
        if numericos:
            argumentos = ", ".join(f"{k}={v}" for k, v in numericos.items())
            return f"Annotated[{base}, Field({argumentos})]"
        return base

    return base


def _exige_relleno(patron: str | None) -> bool:
    """Indica si un patron obliga a escribir el numero con ceros adelante.

    Es el caso de ``[0-9]{9}`` y de ``[0-9]{6,8}``: el minimo de digitos es
    mayor que uno, asi que un valor chico tiene que ir rellenado. No es el caso
    de ``[0-9]{1,5}`` ni de las alternativas que enumeran codigos.
    """
    if not patron:
        return False
    coincidencia = re.fullmatch(r"\[0-9\]\{(\d+)(?:,\d+)?\}", patron)
    return bool(coincidencia) and int(coincidencia.group(1)) > 1


def _texto(valor: str) -> str:
    """Escribe un literal de cadena de Python, sin sorpresas de comillas."""
    return repr(valor)


#: Tipos cuyo nombre derivado chocaria con el de un campo.
#:
#: El elemento ``DE`` es de tipo ``tDE``, y derivar la clase daria ``DE``: un
#: campo que se llama igual que su propia anotacion, que pydantic no puede
#: resolver. Se lo renombra al nombre de dominio, que ademas se lee mejor.
RENOMBRES = {"tDE": "DocumentoElectronico"}


def nombre_de_clase(tipo: str) -> str:
    """Convierte el nombre de un complexType del XSD en nombre de clase."""
    if tipo in RENOMBRES:
        return RENOMBRES[tipo]
    limpio = re.sub(r"^t(g)?", "", tipo)
    return limpio[:1].upper() + limpio[1:]


def elementos_de(tipo: etree._Element) -> list[etree._Element]:
    """Devuelve los elementos con nombre propio de la secuencia de un tipo.

    Se omiten los que vienen por ``ref``, que en este esquema es únicamente
    ``ds:Signature``: la firma no forma parte del modelo porque se calcula
    sobre el árbol ya armado. Ver :mod:`pysifen.signing.xmldsig`.
    """
    secuencia = tipo.find(f"{XS}sequence")
    if secuencia is None:
        return []
    return [
        h
        for h in secuencia
        if h.tag == f"{XS}element" and h.get("name") and not h.get("ref")
    ]


def mapa_de_etiquetas(complejos: dict[str, etree._Element]) -> dict[str, str]:
    """Averigua con qué nombre de elemento se usa cada complexType."""
    etiquetas: dict[str, str] = {}
    for tipo in complejos.values():
        for el in elementos_de(tipo):
            referido = el.get("type", "")
            if referido in complejos and referido not in etiquetas:
                etiquetas[referido] = el.get("name", "")
    etiquetas.setdefault("rDE", "rDE")
    etiquetas.setdefault("tDE", "DE")
    return etiquetas


def generar() -> str:
    """Arma el código del módulo de modelos."""
    complejos, simples = cargar_esquema()
    etiquetas = mapa_de_etiquetas(complejos)

    partes: list[str] = [_cabecera()]
    orden = _orden_topologico(complejos)

    for nombre in orden:
        tipo = complejos[nombre]
        partes.append(_clase(nombre, tipo, complejos, simples, etiquetas))

    exportados = sorted(nombre_de_clase(n) for n in complejos)
    partes.append("__all__ = [\n")
    partes.extend(f'    "{n}",\n' for n in exportados)
    partes.append("]\n")
    return "".join(partes)


def _orden_topologico(complejos: dict[str, etree._Element]) -> list[str]:
    """Ordena los tipos de modo que cada uno se defina después de sus hijos."""
    listo: list[str] = []
    visto: set[str] = set()

    def visitar(nombre: str, pila: frozenset[str] = frozenset()) -> None:
        if nombre in visto or nombre in pila:
            return
        for el in elementos_de(complejos[nombre]):
            referido = el.get("type", "")
            if referido in complejos:
                visitar(referido, pila | {nombre})
        visto.add(nombre)
        listo.append(nombre)

    for nombre in complejos:
        visitar(nombre)
    return listo


def _clase(
    nombre: str,
    tipo: etree._Element,
    complejos: dict[str, etree._Element],
    simples: dict[str, etree._Element],
    etiquetas: dict[str, str],
) -> str:
    """Genera una clase de modelo para un complexType."""
    clase = nombre_de_clase(nombre)
    etiqueta = etiquetas.get(nombre, nombre)
    doc = documentacion(tipo) or f"Grupo {etiqueta} del documento electrónico."

    lineas = [f"class {clase}(GrupoSifen):\n"]
    lineas.append(f'    """{_resumen(doc)}\n')
    if len(doc) > _ANCHO_RESUMEN:
        lineas.append(f"\n    {_envolver(doc, 4)}\n")
    lineas.append("\n")
    lineas.append(
        f"    Elemento XML: ``{etiqueta}``. Tipo del esquema: ``{nombre}``.\n"
    )
    lineas.append('    """\n\n')
    lineas.append(f'    _etiqueta: ClassVar[str] = "{etiqueta}"\n')

    campos = elementos_de(tipo)
    if not campos:
        lineas.append("\n")
        return "".join(lineas) + "\n"

    lineas.append("\n")
    for el in campos:
        lineas.append(_campo(el, complejos, simples))
    lineas.append("\n")
    return "".join(lineas)


def descripcion_de_campo(
    el: etree._Element,
    simples: dict[str, etree._Element],
) -> str:
    """Busca la descripción del campo: primero en el elemento, luego en su tipo.

    De los 428 elementos del esquema sólo 55 traen documentación propia; los
    otros la heredan del simpleType que los tipa, donde 127 de 140 sí la tienen.
    """
    propia = documentacion(el)
    if propia:
        return propia
    tipo = simples.get(el.get("type", ""))
    if tipo is not None:
        heredada = documentacion(tipo)
        if heredada:
            return heredada
    return el.get("name", "")


def _tiene_firma(tipo: etree._Element) -> bool:
    """Indica si el tipo declara el elemento de firma por referencia."""
    secuencia = tipo.find(f"{XS}sequence")
    if secuencia is None:
        return False
    return any(
        (h.get("ref") or "").endswith("Signature")
        for h in secuencia
        if h.tag == f"{XS}element"
    )


def _campo(
    el: etree._Element,
    complejos: dict[str, etree._Element],
    simples: dict[str, etree._Element],
) -> str:
    """Genera la declaración de un campo."""
    nombre = el.get("name", "")
    tipo_xsd = el.get("type", "xs:string")
    minimo = el.get("minOccurs", "1")
    maximo = el.get("maxOccurs", "1")
    doc = descripcion_de_campo(el, simples)

    if tipo_xsd in complejos:
        anot = nombre_de_clase(tipo_xsd)
    elif tipo_xsd.startswith("ds:"):
        # La firma se agrega aparte, sobre el árbol ya armado.
        anot = "Any"
    else:
        anot = anotacion(tipo_xsd, simples)

    repetido = maximo not in {"1", None}
    opcional = minimo == "0"

    if repetido:
        anot_final = f"tuple[{anot}, ...]"
        defecto = "()"
    elif opcional:
        anot_final = f"{anot} | None"
        defecto = "None"
    else:
        anot_final = anot
        defecto = None

    descripcion = doc or nombre
    funcion = "campo" if defecto is None else "campo_opcional"
    asignacion = f"{funcion}(None, {_texto(descripcion)})"

    return f"    {nombre}: {anot_final} = {asignacion}\n"


#: Largo máximo de la línea de resumen de un docstring.
_ANCHO_RESUMEN = 72


def _resumen(texto: str) -> str:
    """Devuelve una línea de resumen que entre en el ancho permitido.

    Un docstring tiene que abrir con una sola línea. Cuando la documentación
    del esquema es más larga, se corta acá y el texto completo va en el cuerpo.
    """
    if len(texto) <= _ANCHO_RESUMEN:
        return texto
    corte = texto.rfind(" ", 0, _ANCHO_RESUMEN - 3)
    if corte <= 0:
        corte = _ANCHO_RESUMEN - 3
    return texto[:corte].rstrip(" .,;:") + "..."


def _envolver(texto: str, sangria: int) -> str:
    """Envuelve un texto para que entre en el ancho de línea del proyecto."""
    ancho = 88 - sangria
    lineas = textwrap.wrap(texto, width=ancho) or [texto]
    relleno = " " * sangria
    return ("\n" + relleno).join(lineas)


def _cabecera() -> str:
    """Devuelve el encabezado del módulo generado."""
    return '''"""Modelos del documento electrónico, generados desde el esquema oficial.

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
from typing import Annotated, Any, ClassVar, Literal

from pydantic import Field, StringConstraints

from pysifen.documento.base import GrupoSifen, campo, campo_opcional

'''


def _canonizar(ruta: Path) -> None:
    """Pasa el archivo generado por ruff.

    Así el módulo generado es siempre idéntico para la misma entrada, y el modo
    ``--check`` compara contra algo estable.
    """
    ruff = shutil.which("ruff")
    if ruff is None:  # pragma: no cover - en CI ruff siempre está
        return
    subprocess.run(  # noqa: S603 - ruta resuelta por which, argumentos fijos
        [ruff, "check", "--fix", "--quiet", str(ruta)], check=False
    )
    subprocess.run(  # noqa: S603
        [ruff, "format", "--quiet", str(ruta)], check=False
    )


def main() -> int:
    """Genera el módulo, o verifica que esté al día."""
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument(
        "--check",
        action="store_true",
        help="no escribe; falla si el módulo generado quedó desactualizado",
    )
    opciones = analizador.parse_args()

    codigo = generar()

    if opciones.check:
        if not DESTINO.exists():
            print(f"{DESTINO} no existe; correr el generador.", file=sys.stderr)
            return 1
        # El testigo va al lado del original: ruff resuelve su configuración
        # por la ubicación del archivo, y las reglas del módulo generado están
        # declaradas por ruta en el pyproject.
        testigo = DESTINO.with_name("_generado.testigo.py")
        try:
            testigo.write_text(codigo, encoding="utf-8")
            _canonizar(testigo)
            codigo = testigo.read_text(encoding="utf-8")
        finally:
            testigo.unlink(missing_ok=True)
        if DESTINO.read_text(encoding="utf-8") != codigo:
            print(
                f"{DESTINO} está desactualizado respecto del esquema. "
                "Correr: python scripts/generar_modelos.py",
                file=sys.stderr,
            )
            return 1
        print("El módulo generado está al día con el esquema.")
        return 0

    DESTINO.write_text(codigo, encoding="utf-8")
    _canonizar(DESTINO)
    complejos, _ = cargar_esquema()
    print(f"{DESTINO.relative_to(RAIZ)}: {len(complejos)} grupos generados")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
