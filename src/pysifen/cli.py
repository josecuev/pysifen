"""Interfaz de línea de comandos.

Sirve para dos cosas: operar (verificar un documento recibido, validarlo contra
el esquema, descomponer un CDC) y **preguntarle a la librería por su propia
estructura**.

Lo primero es el caso de todos los días::

    pysifen verificar factura.xml              # ¿puedo confiar en esto?
    pysifen verificar *.xml --revocacion       # y además consultar al prestador

Lo segundo importa más de lo que parece. El documento electrónico tiene 49
grupos y más de 400 campos, y nadie —persona o agente— se los sabe de memoria.
En vez de obligar a leer el manual, la librería se describe a sí misma::

    pysifen buscar dTotGralOpe     # ¿en qué grupo vive este campo?
    pysifen grupo CamItem          # ¿qué campos tiene, cuáles obligatorios?

Esa descripción sale del modelo, que sale del esquema oficial. No hay una copia
que se pueda desactualizar.

.. tip::
   Todos los comandos aceptan ``--json``, para que la salida se pueda consumir
   desde otro programa o desde un agente sin tener que interpretar texto.

No usa ninguna dependencia fuera de la biblioteca estándar: el núcleo no
arrastra un framework de CLI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pysifen import __version__
from pysifen.cdc import Cdc
from pysifen.documento import grupos_disponibles
from pysifen.exceptions import SifenError
from pysifen.lectura import leer_documentos
from pysifen.validacion import URL_OFICIAL, validar_documento

__all__ = ["main"]


def _describir_campo(nombre: str, info: Any) -> dict[str, Any]:
    """Arma la descripción de un campo, tal como la ve el modelo."""
    return {
        "campo": nombre,
        "tipo": _texto_del_tipo(info.annotation),
        "obligatorio": info.is_required(),
        "descripcion": info.description or "",
    }


def _texto_del_tipo(anotacion: Any) -> str:
    """Devuelve una representación legible de la anotación de tipo."""
    texto = str(anotacion)
    texto = texto.replace("typing.", "").replace("pysifen.documento._generado.", "")
    return texto.replace("<class '", "").replace("'>", "")


def _grupos(_: argparse.Namespace) -> dict[str, Any]:
    """Lista todos los grupos del documento electrónico."""
    salida = []
    for nombre, modelo in sorted(grupos_disponibles().items()):
        salida.append(
            {
                "grupo": nombre,
                "elemento": modelo._etiqueta,
                "campos": len(modelo.model_fields),
                "descripcion": (modelo.__doc__ or "").strip().split("\n")[0],
            }
        )
    return {"grupos": salida, "total": len(salida)}


def _grupo(opciones: argparse.Namespace) -> dict[str, Any]:
    """Describe un grupo: sus campos, tipos y obligatoriedad."""
    disponibles = grupos_disponibles()
    modelo = disponibles.get(opciones.nombre)
    if modelo is None:
        parecidos = [n for n in disponibles if opciones.nombre.lower() in n.lower()]
        raise SifenError(
            f"no existe el grupo {opciones.nombre!r}."
            + (f" ¿Quisiste decir {', '.join(parecidos[:5])}?" if parecidos else "")
        )
    return {
        "grupo": opciones.nombre,
        "elemento": modelo._etiqueta,
        "descripcion": (modelo.__doc__ or "").strip(),
        "campos": [_describir_campo(n, i) for n, i in modelo.model_fields.items()],
    }


def _buscar(opciones: argparse.Namespace) -> dict[str, Any]:
    """Busca en qué grupos aparece un campo."""
    aguja = opciones.texto.lower()
    encontrados = []
    for nombre, modelo in sorted(grupos_disponibles().items()):
        for campo, info in modelo.model_fields.items():
            if aguja in campo.lower() or aguja in (info.description or "").lower():
                encontrados.append(
                    {"grupo": nombre, "elemento": modelo._etiqueta}
                    | _describir_campo(campo, info)
                )
    return {"busqueda": opciones.texto, "resultados": encontrados}


def _validar(opciones: argparse.Namespace) -> dict[str, Any]:
    """Valida un documento contra el esquema oficial."""
    ruta = Path(opciones.archivo)
    if not ruta.is_file():
        raise SifenError(f"no encontré el archivo {ruta}")
    problemas = validar_documento(ruta.read_bytes())
    return {
        "archivo": str(ruta),
        "valido": not problemas,
        "problemas": problemas,
    }


def _verificar(opciones: argparse.Namespace) -> dict[str, Any]:
    """Verifica documentos recibidos: firma, cadena, vigencia, CDC, QR."""
    rutas = [Path(r) for r in opciones.archivos]
    for ruta in rutas:
        if not ruta.is_file():
            raise SifenError(f"no encontré el archivo {ruta}")
    informes = leer_documentos(rutas, revocacion=opciones.revocacion)
    confiables = sum(1 for i in informes if i.confiable)
    return {
        "documentos": [i.resumir() for i in informes],
        "total": len(informes),
        "confiables": confiables,
        "con_reparos": len(informes) - confiables,
        "texto": [i.informe() for i in informes],
    }


def _cdc(opciones: argparse.Namespace) -> dict[str, Any]:
    """Descompone un Código de Control en sus partes."""
    codigo = Cdc.parse(opciones.codigo)
    return {
        "cdc": codigo.valor,
        "formateado": codigo.formateado,
        "tipo_documento": codigo.tipo_documento.name,
        "descripcion": codigo.tipo_documento.descripcion,
        "ruc_emisor": f"{codigo.ruc_emisor}-{codigo.dv_ruc}",
        "numero_documento": codigo.numero_documento,
        "tipo_contribuyente": codigo.tipo_contribuyente.name,
        "fecha_emision": codigo.fecha_emision.isoformat(),
        "tipo_emision": codigo.tipo_emision.name,
        "codigo_seguridad": codigo.codigo_seguridad,
        "digito_verificador": codigo.dv,
    }


def _esquemas(_: argparse.Namespace) -> dict[str, Any]:
    """Informa qué esquemas trae la librería."""
    from pysifen.validacion import DIRECTORIO_DE_ESQUEMAS

    manifiesto = json.loads(
        (DIRECTORIO_DE_ESQUEMAS / "checksums.json").read_text(encoding="utf-8")
    )
    return {
        "origen": URL_OFICIAL,
        "descargado": manifiesto["descargado"],
        "archivos": [
            {"archivo": n, "bytes": i["bytes"], "sha256": i["sha256"]}
            for n, i in sorted(manifiesto["archivos"].items())
        ],
    }


def _imprimir(datos: dict[str, Any], *, como_json: bool) -> None:
    """Muestra el resultado, en JSON o en texto para leer."""
    if como_json:
        # El texto legible es para la consola; en JSON ya va el resumen.
        print(
            json.dumps(
                {k: v for k, v in datos.items() if k != "texto"},
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    if "texto" in datos and isinstance(datos["texto"], list):
        print("\n\n".join(datos["texto"]))
        print(
            f"\n{datos['confiables']} confiable(s), {datos['con_reparos']} con reparos"
        )
        return

    if "grupos" in datos and isinstance(datos["grupos"], list):
        for fila in datos["grupos"]:
            print(
                f"{fila['grupo']:<22} {fila['elemento']:<16} {fila['campos']:>3} campos"
            )
        print(f"\n{datos['total']} grupos")
        return

    if "campos" in datos and isinstance(datos["campos"], list):
        print(f"{datos['grupo']}  ({datos['elemento']})\n")
        for c in datos["campos"]:
            marca = " " if c["obligatorio"] else "?"
            print(f"  {marca} {c['campo']:<18} {c['tipo']}")
            if c["descripcion"]:
                print(f"      {c['descripcion']}")
        print("\n  (? = opcional)")
        return

    if "resultados" in datos:
        for r in datos["resultados"]:
            marca = " " if r["obligatorio"] else "?"
            print(f"{r['grupo']:<20} {marca} {r['campo']:<18} {r['tipo']}")
        print(f"\n{len(datos['resultados'])} coincidencia(s)")
        return

    if "valido" in datos:
        if datos["valido"]:
            print(f"{datos['archivo']}: válido contra el esquema oficial")
        else:
            print(f"{datos['archivo']}: NO válido\n")
            for p in datos["problemas"]:
                print(f"  {p}")
        return

    for clave, valor in datos.items():
        if isinstance(valor, list):
            print(f"{clave}:")
            for v in valor:
                print(f"  {v}")
        else:
            print(f"{clave:<20} {valor}")


def construir_analizador() -> argparse.ArgumentParser:
    """Arma el analizador de argumentos con todos los comandos."""
    analizador = argparse.ArgumentParser(
        prog="pysifen",
        description=(
            "Herramientas para la facturación electrónica del Paraguay. "
            "Todos los comandos aceptan --json."
        ),
    )
    analizador.add_argument("--version", action="version", version=__version__)
    analizador.add_argument(
        "--json",
        action="store_true",
        help="salida en JSON, para consumir desde otro programa",
    )
    comandos = analizador.add_subparsers(dest="comando", required=True)

    comandos.add_parser(
        "grupos", help="lista los grupos del documento electrónico"
    ).set_defaults(funcion=_grupos)

    grupo = comandos.add_parser("grupo", help="describe un grupo y sus campos")
    grupo.add_argument("nombre", help="nombre del grupo, por ejemplo CamItem")
    grupo.set_defaults(funcion=_grupo)

    buscar = comandos.add_parser("buscar", help="busca en qué grupo vive un campo")
    buscar.add_argument("texto", help="nombre del campo o parte de su descripción")
    buscar.set_defaults(funcion=_buscar)

    verificar = comandos.add_parser(
        "verificar",
        help="verifica documentos recibidos: firma, cadena, vigencia, CDC y QR",
    )
    verificar.add_argument("archivos", nargs="+", help="documentos o lotes .xml")
    verificar.add_argument(
        "--revocacion",
        action="store_true",
        help=(
            "consultar al prestador que el certificado no esté revocado. Es lo "
            "único que sale a la red, por eso hay que pedirlo"
        ),
    )
    verificar.set_defaults(funcion=_verificar)

    validar = comandos.add_parser(
        "validar", help="valida un XML contra el esquema oficial"
    )
    validar.add_argument("archivo", help="ruta del documento a validar")
    validar.set_defaults(funcion=_validar)

    cdc = comandos.add_parser("cdc", help="descompone un Código de Control")
    cdc.add_argument("codigo", help="los 44 dígitos del CDC")
    cdc.set_defaults(funcion=_cdc)

    comandos.add_parser(
        "esquemas", help="informa qué esquemas trae la librería"
    ).set_defaults(funcion=_esquemas)

    return analizador


def main(argumentos: list[str] | None = None) -> int:
    """Punto de entrada de la línea de comandos.

    Args:
        argumentos: los argumentos a procesar. Por omisión, los de la consola.

    Returns:
        ``0`` si todo salió bien, ``1`` si hubo un problema de negocio, ``2``
        si el documento validado resultó inválido, ``3`` si algún documento
        verificado no resultó confiable. Así sirve en un script.
    """
    opciones = construir_analizador().parse_args(argumentos)
    try:
        datos = opciones.funcion(opciones)
    except SifenError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if opciones.json and hasattr(sys.stdout, "reconfigure"):
        # JSON es UTF-8 por definición (RFC 8259). En Windows la salida
        # redirigida usa la codificación de la consola, y quien lea el archivo
        # se encontraría con bytes que no son UTF-8 en la primera "ó".
        sys.stdout.reconfigure(encoding="utf-8")
    _imprimir(datos, como_json=opciones.json)

    if datos.get("valido") is False:
        return 2
    if datos.get("con_reparos", 0) > 0:
        return 3
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
