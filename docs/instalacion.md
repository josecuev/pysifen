# Instalación

## Requisitos

- Python 3.12 o superior.

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

El proyecto resuelve sus dependencias con
[Poetry](https://python-poetry.org/). El archivo `poetry.lock` fija el árbol
completo, así que todos los entornos instalan exactamente lo mismo.

```bash
git clone https://github.com/josecuev/pysifen.git
cd pysifen
poetry install --with dev,test,docs
```

## Entorno de desarrollo

Verificación completa, que es la misma que corre en integración continua:

```bash
poetry check --strict
poetry check --lock
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy
poetry run pytest
```

Para agregar o subir una dependencia, siempre a través de Poetry, de modo
que el lock quede en sintonía:

```bash
poetry add lxml
poetry add --group dev ruff
poetry update
```

Los tests que necesitan red o un certificado real están marcados y quedan fuera
de la corrida por omisión:

```bash
poetry run pytest -m "not red and not certificado"   # comportamiento por defecto
pytest -m red                             # sólo los que salen a la red
```

## Documentación local

```bash
poetry install --with docs
poetry run mkdocs serve
```

La referencia de la API se genera desde el código en cada compilación, así que
no hay páginas que mantener a mano.
