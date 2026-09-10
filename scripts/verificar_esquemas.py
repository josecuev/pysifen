#!/usr/bin/env python3
"""Compara los esquemas incluidos con los que publica la DNIT.

Descarga cada XSD de ``https://ekuatia.set.gov.py/sifen/xsd/`` y compara su
SHA-256 contra el manifiesto ``src/pysifen/esquemas/checksums.json``.

Un cambio ahí es lo más significativo que puede pasarle a este proyecto: el XSD
es contra lo que el SIFEN valida de verdad, así que si cambia, cambió el
contrato, aunque el Manual Técnico siga diciendo lo mismo.

Uso::

    python scripts/verificar_esquemas.py            # compara
    python scripts/verificar_esquemas.py --json     # salida para CI

Devuelve 0 si todo coincide, 1 si algo cambió, 2 si no se pudo verificar.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MANIFIESTO = RAIZ / "src" / "pysifen" / "esquemas" / "checksums.json"
TIEMPO_LIMITE = 45


def descargar(url: str) -> bytes:
    """Baja un archivo y devuelve sus bytes."""
    peticion = urllib.request.Request(  # noqa: S310 - URL fija y https
        url, headers={"User-Agent": "pysifen/verificacion-de-esquemas"}
    )
    with urllib.request.urlopen(peticion, timeout=TIEMPO_LIMITE) as respuesta:  # noqa: S310
        datos: bytes = respuesta.read()
    return datos


def main() -> int:
    """Compara cada esquema y reporta las diferencias."""
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument(
        "--json", action="store_true", help="salida en JSON, para consumir en CI"
    )
    opciones = analizador.parse_args()

    manifiesto = json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    origen = manifiesto["origen"]

    cambiados: list[str] = []
    inaccesibles: list[str] = []
    iguales: list[str] = []

    for nombre, esperado in sorted(manifiesto["archivos"].items()):
        url = esperado.get("origen") or f"{origen}{nombre}"
        try:
            actual = hashlib.sha256(descargar(url)).hexdigest()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            inaccesibles.append(f"{nombre}: {exc}")
            continue

        if actual == esperado["sha256"]:
            iguales.append(nombre)
        else:
            cambiados.append(
                f"{nombre}: incluido {esperado['sha256'][:16]}… "
                f"publicado {actual[:16]}…"
            )

    if opciones.json:
        print(
            json.dumps(
                {
                    "cambiados": cambiados,
                    "inaccesibles": inaccesibles,
                    "iguales": len(iguales),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(f"Esquemas verificados contra {origen}\n")
        for nombre in iguales:
            print(f"  sin cambios  {nombre}")
        for detalle in cambiados:
            print(f"  CAMBIO       {detalle}")
        for detalle in inaccesibles:
            print(f"  sin acceso   {detalle}")

    if cambiados:
        print(
            f"\n{len(cambiados)} esquema(s) cambiaron en el servidor de la DNIT.",
            file=sys.stderr,
        )
        print(
            "Bajar las versiones nuevas, regenerar el manifiesto y revisar qué "
            "cambió antes de publicar.",
            file=sys.stderr,
        )
        return 1

    if inaccesibles:
        print(
            f"\nNo se pudo verificar {len(inaccesibles)} esquema(s).",
            file=sys.stderr,
        )
        return 2

    print(f"\nTodo coincide: {len(iguales)} esquemas sin cambios.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
