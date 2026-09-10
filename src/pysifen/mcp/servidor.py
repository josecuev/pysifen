"""Servidor MCP para leer y verificar documentos tributarios electrónicos.

Expone la librería como herramientas que un modelo puede invocar. Está pensado
para el caso que más aparece en la práctica: alguien recibe una factura
electrónica y necesita saber **qué dice** y **si puede confiar en ella**, sin
tener certificado propio ni estar habilitado como facturador.

Por qué es stateless
--------------------

No guarda nada entre llamadas: cada herramienta recibe el documento, lo
procesa y devuelve el resultado. No hay sesión, ni caché de documentos, ni
estado compartido entre pedidos. Tampoco sale a la red, salvo que se le pida la
consulta de revocación.

Eso no es una simplificación sino lo que corresponde. La revisión 2026-07-28
del protocolo **eliminó las sesiones** del transporte HTTP, así que un servidor
sin estado es el modelo natural. Y para este dominio es además lo seguro: los
documentos tributarios traen datos de contribuyentes, y un servidor que no los
retiene no tiene nada que filtrar.

Lo único que se reutiliza entre llamadas es el esquema XSD compilado y la
Lista de Confianza, que son datos de la librería y no del usuario. Compilar
el esquema lleva del orden de un segundo; hacerlo por pedido haría inviable
procesar un lote.

Cómo se ejecuta
---------------

.. code-block:: bash

   pysifen-mcp                      # stdio, para clientes de escritorio
   pysifen-mcp --http               # Streamable HTTP en 127.0.0.1:8000
   pysifen-mcp --http --puerto 9000

Ver ``docs/mcp.md`` para la configuración en clientes de escritorio.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pysifen import __version__
from pysifen.cdc import Cdc
from pysifen.documento import grupos_disponibles
from pysifen.exceptions import SifenError
from pysifen.lectura import verificar_documento
from pysifen.pki.cadena import lista_de_confianza
from pysifen.validacion import esquema_de_documento

__all__ = ["construir_servidor", "main"]

#: Tope de tamaño de un documento, para no procesar algo desmedido.
LIMITE_DE_BYTES = 5 * 1024 * 1024


def _fallo(mensaje: str) -> dict[str, Any]:
    """Devuelve un error como dato, no como excepción.

    Un modelo maneja mucho mejor un resultado que dice qué pasó que una traza
    de excepción.
    """
    return {"ok": False, "error": mensaje}


def _leer_entrada(xml: str | None, ruta: str | None) -> bytes:
    """Obtiene el documento, venga como texto o como ruta de archivo.

    Raises:
        SifenError: si no se pasó ninguno, si se pasaron los dos, o si el
            archivo no se puede leer.
    """
    if bool(xml) == bool(ruta):
        raise SifenError("hay que pasar exactamente uno: 'xml' o 'ruta'")

    if xml is not None:
        crudo = xml.encode("utf-8")
    else:
        archivo = Path(ruta or "")
        if not archivo.is_file():
            raise SifenError(f"no encontré el archivo {archivo}")
        crudo = archivo.read_bytes()

    if len(crudo) > LIMITE_DE_BYTES:
        raise SifenError(
            f"el documento pesa {len(crudo)} bytes y el tope es {LIMITE_DE_BYTES}"
        )
    return crudo


def construir_servidor() -> Any:
    """Arma el servidor MCP con sus herramientas.

    Returns:
        El servidor listo para correr por cualquiera de los dos transportes.

    Raises:
        SifenError: si falta el extra ``mcp``.
    """
    try:
        from mcp.server.mcpserver import MCPServer
    except ImportError as exc:  # pragma: no cover - depende del extra
        raise SifenError(
            "para levantar el servidor MCP hace falta el extra: "
            'pip install "pysifen[mcp]"'
        ) from exc

    servidor = MCPServer(
        name="pysifen",
        version=__version__,
        instructions=(
            "Herramientas para documentos tributarios electrónicos del Paraguay "
            "(SIFEN). Sirven para leer una factura recibida y verificar si es "
            "auténtica, y para consultar la estructura oficial del documento. "
            "Verificar no requiere certificado propio: el documento trae el "
            "certificado de quien lo firmó, y la cadena se valida contra la "
            "Lista de Confianza oficial del Ministerio de Industria y Comercio."
        ),
    )

    # Se preparan una vez y se reutilizan: son datos de la librería, no del
    # usuario, así que compartirlos no rompe el carácter stateless.
    esquema_de_documento()
    anclas = lista_de_confianza()

    @servidor.tool()
    def verificar_factura(
        xml: str | None = None,
        ruta: str | None = None,
        revocacion: bool = False,
    ) -> dict[str, Any]:
        """Lee una factura electrónica y verifica si se puede confiar en ella.

        Comprueba el esquema oficial, la firma digital, que el certificado
        encadene hasta la Autoridad Certificadora Raíz del Paraguay por un
        prestador cualificado habilitado, que estuviera vigente al firmar, que
        el RUC del documento sea el del certificado, y que el CDC y el QR sean
        coherentes. Con revocacion=True consulta además que el prestador no lo
        haya dado de baja, y ahí no queda nada sin verificar.

        Devuelve una versión compacta del documento con el veredicto adelante.
        La clave 'confiable' es la que decide si el resto se puede usar.

        Args:
            xml: el documento como texto. Excluyente con 'ruta'.
            ruta: la ruta a un archivo .xml. Excluyente con 'xml'.
            revocacion: si consultar al prestador que el certificado no esté
                dado de baja. Es la única comprobación que sale a la red, por
                eso está apagada. Con ella el veredicto no deja nada sin
                verificar; sin ella, la respuesta lo declara en
                'limite_de_la_verificacion'.
        """
        try:
            crudo = _leer_entrada(xml, ruta)
        except SifenError as error:
            return _fallo(str(error))

        resultado = verificar_documento(crudo, lista=anclas, revocacion=revocacion)
        return {"ok": True} | resultado.resumir()

    @servidor.tool()
    def verificar_facturas(
        rutas: list[str], revocacion: bool = False
    ) -> dict[str, Any]:
        """Verifica varias facturas de una vez, reutilizando el esquema.

        Más eficiente que llamar a verificar_factura muchas veces: el esquema
        se compila una sola vez para todo el lote.

        Args:
            rutas: las rutas de los archivos .xml a verificar.
            revocacion: si consultar la revocación de cada certificado. Sale a
                la red una vez por documento, así que en un lote grande cuesta.
        """
        if not rutas:
            return _fallo("no se pasó ninguna ruta")
        if len(rutas) > 200:
            return _fallo(f"son {len(rutas)} documentos y el tope por llamada es 200")

        informes: list[dict[str, Any]] = []
        for ruta in rutas:
            try:
                crudo = _leer_entrada(None, ruta)
            except SifenError as error:
                informes.append({"ruta": ruta, "ok": False, "error": str(error)})
                continue
            resultado = verificar_documento(crudo, lista=anclas, revocacion=revocacion)
            informes.append({"ruta": ruta} | resultado.resumir())

        confiables = sum(1 for i in informes if i.get("confiable"))
        return {
            "ok": True,
            "total": len(informes),
            "confiables": confiables,
            "con_reparos": len(informes) - confiables,
            "documentos": informes,
        }

    @servidor.tool()
    def analizar_cdc(codigo: str) -> dict[str, Any]:
        """Descompone un Código de Control (CDC) de 44 dígitos.

        Devuelve el tipo de documento, el RUC del emisor, el número, la fecha
        de emisión y el resto de sus partes. Verifica el dígito verificador.

        Args:
            codigo: los 44 dígitos del CDC, con o sin espacios.
        """
        try:
            cdc = Cdc.parse(codigo)
        except SifenError as error:
            return _fallo(str(error))
        return {
            "ok": True,
            "cdc": cdc.valor,
            "tipo": cdc.tipo_documento.descripcion,
            "ruc_emisor": f"{cdc.ruc_emisor}-{cdc.dv_ruc}",
            "numero": cdc.numero_documento,
            "emitido": cdc.fecha_emision.isoformat(),
            "tipo_emision": cdc.tipo_emision.descripcion,
        }

    @servidor.tool()
    def buscar_campo(texto: str) -> dict[str, Any]:
        """Busca en qué grupo del documento vive un campo del SIFEN.

        Útil para no adivinar: el documento tiene 49 grupos y más de 400
        campos. Busca por nombre de campo o por su descripción.

        Args:
            texto: nombre del campo, por ejemplo 'dTotGralOpe', o parte de su
                descripción, por ejemplo 'timbrado'.
        """
        aguja = texto.lower()
        encontrados = [
            {
                "grupo": nombre,
                "elemento": modelo._etiqueta,
                "campo": campo,
                "obligatorio": info.is_required(),
                "descripcion": info.description or "",
            }
            for nombre, modelo in sorted(grupos_disponibles().items())
            for campo, info in modelo.model_fields.items()
            if aguja in campo.lower() or aguja in (info.description or "").lower()
        ]
        return {"ok": True, "busqueda": texto, "resultados": encontrados[:40]}

    @servidor.tool()
    def describir_grupo(nombre: str) -> dict[str, Any]:
        """Describe un grupo del documento: sus campos, tipos y obligatoriedad.

        La descripción sale del esquema oficial de la DNIT, no de una copia.

        Args:
            nombre: el nombre del grupo, por ejemplo 'CamItem' o 'TotSub'.
                Usar buscar_campo o listar_grupos si no se conoce.
        """
        disponibles = grupos_disponibles()
        modelo = disponibles.get(nombre)
        if modelo is None:
            parecidos = [n for n in disponibles if nombre.lower() in n.lower()]
            return _fallo(
                f"no existe el grupo {nombre!r}."
                + (f" Parecidos: {', '.join(parecidos[:5])}" if parecidos else "")
            )
        return {
            "ok": True,
            "grupo": nombre,
            "elemento": modelo._etiqueta,
            "descripcion": (modelo.__doc__ or "").strip().split("\n")[0],
            "campos": [
                {
                    "campo": campo,
                    "obligatorio": info.is_required(),
                    "descripcion": info.description or "",
                }
                for campo, info in modelo.model_fields.items()
            ],
        }

    @servidor.tool()
    def listar_grupos() -> dict[str, Any]:
        """Lista los 49 grupos que componen un documento electrónico."""
        return {
            "ok": True,
            "grupos": [
                {"grupo": n, "elemento": m._etiqueta, "campos": len(m.model_fields)}
                for n, m in sorted(grupos_disponibles().items())
            ],
        }

    return servidor


def main(argumentos: list[str] | None = None) -> int:
    """Levanta el servidor MCP.

    Args:
        argumentos: los argumentos de consola. Por omisión, los reales.

    Returns:
        ``0`` si terminó bien, ``1`` si faltaba el extra.
    """
    analizador = argparse.ArgumentParser(
        prog="pysifen-mcp",
        description=(
            "Servidor MCP para leer y verificar documentos tributarios "
            "electrónicos del Paraguay. Sin estado entre llamadas."
        ),
    )
    analizador.add_argument("--version", action="version", version=__version__)
    analizador.add_argument(
        "--http",
        action="store_true",
        help="usar Streamable HTTP en vez de stdio",
    )
    analizador.add_argument(
        "--puerto", type=int, default=8000, help="puerto para --http (por omisión 8000)"
    )
    analizador.add_argument(
        "--host",
        default="127.0.0.1",
        help=(
            "interfaz para --http. Por omisión sólo localhost: exponerlo a la "
            "red abre el servidor a cualquiera que la alcance"
        ),
    )
    analizador.add_argument(
        "--herramientas",
        action="store_true",
        help="imprime las herramientas en JSON y sale, sin levantar el servidor",
    )
    opciones = analizador.parse_args(argumentos)

    try:
        servidor = construir_servidor()
    except SifenError as error:
        print(f"error: {error}")
        return 1

    if opciones.herramientas:
        import asyncio

        herramientas = asyncio.run(servidor.list_tools())
        print(
            json.dumps(
                [
                    {"nombre": h.name, "descripcion": h.description}
                    for h in herramientas
                ],
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if opciones.http:
        import asyncio

        # stateless_http corta toda sesión entre pedidos, y json_response evita
        # abrir un flujo SSE para respuestas que se resuelven de una: estas
        # herramientas no emiten progreso.
        asyncio.run(
            servidor.run_streamable_http_async(
                host=opciones.host,
                port=opciones.puerto,
                stateless_http=True,
                json_response=True,
            )
        )
    else:
        servidor.run(transport="stdio")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
