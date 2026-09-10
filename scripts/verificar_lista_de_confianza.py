#!/usr/bin/env python3
"""Compara la Lista de Confianza incluida con la que publica el MIC.

Descarga ``https://www.acraiz.gov.py/tsl/tsl_Py.xml`` y compara su SHA-256, su
número de secuencia y su fecha de próxima actualización contra el manifiesto
``src/pysifen/confianza/checksums.json``.

Por qué esto importa tanto como los esquemas
--------------------------------------------

La lista es lo que convierte "el certificado dice ser de un prestador
cualificado" en "lo es". Si el MIC habilita a un prestador nuevo y la copia
incluida no lo trae, los documentos de ese prestador se rechazan por algo que no
es culpa suya. Si le retira la habilitación a uno y la copia no se actualiza,
pasa lo contrario y es peor.

Además la lista **caduca**: trae su propia fecha de próxima actualización, y una
copia vencida es una copia en la que ya no corresponde confiar.

Uso::

    python scripts/verificar_lista_de_confianza.py          # compara
    python scripts/verificar_lista_de_confianza.py --json   # salida para CI

Devuelve 0 si todo está en orden, 1 si la lista cambió o la copia caducó, 2 si
no se pudo verificar.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

RAIZ = Path(__file__).resolve().parent.parent
MANIFIESTO = RAIZ / "src" / "pysifen" / "confianza" / "checksums.json"
TIEMPO_LIMITE = 45

#: Con cuánta antelación avisar de que la copia está por caducar.
DIAS_DE_AVISO = 30

_TSL = "{http://uri.etsi.org/02231/v2#}"


def descargar(url: str) -> bytes:
    """Baja un archivo y devuelve sus bytes."""
    peticion = urllib.request.Request(  # noqa: S310 - URL fija y https
        url, headers={"User-Agent": "pysifen/verificacion-de-la-lista-de-confianza"}
    )
    with urllib.request.urlopen(peticion, timeout=TIEMPO_LIMITE) as respuesta:  # noqa: S310
        datos: bytes = respuesta.read()
    return datos


def leer_cabecera(contenido: bytes) -> dict[str, str | int]:
    """Extrae la secuencia y las fechas de la lista descargada."""
    raiz = ElementTree.fromstring(contenido)  # noqa: S314 - fuente oficial, sin entidades
    informacion = raiz.find(f"{_TSL}SchemeInformation")
    if informacion is None:
        return {}
    secuencia = informacion.findtext(f"{_TSL}TSLSequenceNumber") or ""
    emitida = informacion.findtext(f"{_TSL}ListIssueDateTime") or ""
    proxima = (
        informacion.findtext(f"{_TSL}NextUpdate/{_TSL}dateTime")
        if informacion.find(f"{_TSL}NextUpdate") is not None
        else ""
    ) or ""
    cabecera: dict[str, str | int] = {"emitida": emitida, "proxima": proxima}
    if secuencia.isdigit():
        cabecera["secuencia"] = int(secuencia)
    return cabecera


def dias_hasta(momento: str) -> int | None:
    """Devuelve cuántos días faltan para una fecha ISO, o ``None``."""
    try:
        limite = datetime.fromisoformat(momento)
    except ValueError:
        return None
    if limite.tzinfo is None:
        limite = limite.replace(tzinfo=UTC)
    return (limite - datetime.now(UTC)).days


def main() -> int:
    """Compara la lista publicada con la incluida y reporta las diferencias."""
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument(
        "--json", action="store_true", help="salida en JSON, para consumir en CI"
    )
    opciones = analizador.parse_args()

    manifiesto = json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    origen = str(manifiesto["origen"])

    problemas: list[str] = []
    avisos: list[str] = []

    # La copia incluida caduca sola, se pueda alcanzar el servidor o no.
    restantes = dias_hasta(str(manifiesto["proxima_actualizacion"]))
    if restantes is None:
        problemas.append("el manifiesto no declara una fecha de caducidad legible")
    elif restantes < 0:
        problemas.append(
            f"la copia incluida caducó hace {-restantes} días: el MIC declaró "
            f"que la actualizaría el {manifiesto['proxima_actualizacion']}"
        )
    elif restantes <= DIAS_DE_AVISO:
        avisos.append(f"la copia incluida caduca en {restantes} días")

    try:
        contenido = descargar(origen)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        salida = {
            "problemas": problemas,
            "avisos": avisos,
            "inaccesible": f"{origen}: {exc}",
        }
        if opciones.json:
            print(json.dumps(salida, indent=2, ensure_ascii=False))
        else:
            for detalle in problemas:
                print(f"  PROBLEMA     {detalle}")
            print(f"  sin acceso   {origen}: {exc}")
        return 1 if problemas else 2

    publicado = hashlib.sha256(contenido).hexdigest()
    cabecera = leer_cabecera(contenido)
    cambio = publicado != manifiesto["sha256"]

    if cambio:
        problemas.append(
            f"la lista publicada cambió: incluida {str(manifiesto['sha256'])[:16]}… "
            f"publicada {publicado[:16]}…"
        )
        if cabecera.get("secuencia"):
            problemas.append(
                f"secuencia: incluida {manifiesto['secuencia']}, "
                f"publicada {cabecera['secuencia']}"
            )

    if opciones.json:
        print(
            json.dumps(
                {
                    "cambio": cambio,
                    "problemas": problemas,
                    "avisos": avisos,
                    "publicado": {"sha256": publicado, **cabecera},
                    "incluido": {
                        "sha256": manifiesto["sha256"],
                        "secuencia": manifiesto["secuencia"],
                        "proxima_actualizacion": manifiesto["proxima_actualizacion"],
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(f"Lista de Confianza verificada contra {origen}\n")
        print(
            f"  incluida   secuencia {manifiesto['secuencia']}, "
            f"vigente hasta {manifiesto['proxima_actualizacion']}"
        )
        if cabecera:
            print(
                f"  publicada  secuencia {cabecera.get('secuencia', '?')}, "
                f"vigente hasta {cabecera.get('proxima', '?')}"
            )
        for detalle in avisos:
            print(f"  aviso        {detalle}")
        for detalle in problemas:
            print(f"  PROBLEMA     {detalle}")

    if problemas:
        print(
            "\nHay que bajar la lista nueva a src/pysifen/confianza/tsl_Py.xml, "
            "regenerar el manifiesto y revisar qué prestadores cambiaron antes "
            "de publicar.",
            file=sys.stderr,
        )
        return 1

    print("\nTodo en orden: la lista incluida es la que publica el MIC.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
