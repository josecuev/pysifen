# Instalación

## Requisitos

- Python 3.11 o superior.

## Desde PyPI

```bash
pip install pysifen
```

### Extras opcionales

El núcleo no arrastra dependencias de servidor. Los agregados se instalan
aparte:

=== "Microservicio HTTP"

    ```bash
    pip install "pysifen[api]"
    ```

    Agrega FastAPI y Uvicorn para exponer la librería como servicio y
    consumirla desde otros sistemas.

=== "Firma con token o HSM"

    ```bash
    pip install "pysifen[pkcs11]"
    ```

    Agrega el enlace PKCS#11 para firmar con la clave dentro de un dispositivo,
    sin que salga de él. Ver [Custodia del certificado](seguridad/custodia.md).

=== "Todo"

    ```bash
    pip install "pysifen[api,pkcs11]"
    ```

## Desde el repositorio

```bash
git clone https://github.com/josecuev/pysifen.git
cd pysifen
python -m venv .venv
source .venv/bin/activate      # en Windows: .venv\Scripts\activate
pip install -e ".[api,pkcs11]"
```

## Entorno de desarrollo

El proyecto usa grupos de dependencias declarados en `pyproject.toml`.

```bash
pip install -e .
pip install pytest pytest-cov mypy ruff
```

Verificación completa, que es la misma que corre en integración continua:

```bash
ruff check .
ruff format --check .
mypy
pytest
```

Los tests que necesitan red o un certificado real están marcados y quedan fuera
de la corrida por omisión:

```bash
pytest -m "not red and not certificado"   # comportamiento por defecto
pytest -m red                             # sólo los que salen a la red
```

## Documentación local

```bash
pip install mkdocs mkdocs-material "mkdocstrings[python]" mkdocs-gen-files mkdocs-literate-nav
mkdocs serve
```

La referencia de la API se genera desde el código en cada compilación, así que
no hay páginas que mantener a mano.
