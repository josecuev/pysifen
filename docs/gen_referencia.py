"""Genera la referencia de la API a partir del código.

Recorre ``src/pysifen`` y crea una página por módulo, más el archivo de
navegación que consume ``mkdocs-literate-nav``. De este modo la referencia nunca
queda desfasada respecto del código: se arma en cada compilación de la
documentación.
"""

from __future__ import annotations

from pathlib import Path

import mkdocs_gen_files

RAIZ = Path(__file__).parent.parent
PAQUETE = RAIZ / "src"

navegacion = mkdocs_gen_files.Nav()

for archivo in sorted(PAQUETE.rglob("*.py")):
    ruta_modulo = archivo.relative_to(PAQUETE).with_suffix("")
    ruta_doc = archivo.relative_to(PAQUETE).with_suffix(".md")
    destino = Path("referencia", ruta_doc)

    partes = tuple(ruta_modulo.parts)

    if partes[-1] == "__init__":
        partes = partes[:-1]
        ruta_doc = ruta_doc.with_name("index.md")
        destino = destino.with_name("index.md")
    elif partes[-1].startswith("_"):
        continue

    if not partes:
        continue

    navegacion[partes] = ruta_doc.as_posix()

    with mkdocs_gen_files.open(destino, "w") as pagina:
        pagina.write(f"::: {'.'.join(partes)}\n")

    mkdocs_gen_files.set_edit_path(destino, archivo.relative_to(RAIZ))

with mkdocs_gen_files.open("referencia/RESUMEN.md", "w") as resumen:
    resumen.writelines(navegacion.build_literate_nav())
