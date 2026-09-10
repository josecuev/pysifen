# Imagen del servidor MCP de pysifen.
#
# Lee facturas electronicas del Paraguay y las verifica: esquema, firma,
# cadena de confianza hasta la Autoridad Certificadora Raiz, vigencia, RUC,
# CDC y QR. No necesita certificado propio: el documento trae el de quien lo
# firmo.
#
#   docker run --rm -p 127.0.0.1:8000:8000 josecuev/pysifen
#
# Construccion en dos etapas: la primera arma la rueda con Poetry, la segunda
# solo la instala. Asi ni Poetry ni el codigo fuente terminan en la imagen que
# se publica.
#
# Sobre Alpine y no sobre Debian slim
# -----------------------------------
#
# La base slim son 189 MB contra 55 de Alpine, y esa diferencia se traslada
# entera a la imagen final: 274 MB contra 165. La objecion clasica a Alpine es
# que obliga a compilar las dependencias nativas, pero ya no aplica: lxml,
# cryptography y pydantic-core publican ruedas musllinux, asi que la
# instalacion no compila nada.
#
# Se midio lo que importa antes de cambiar. Los mismos documentos reales dan el
# mismo veredicto en las dos, el escaneo pasa de tres vulnerabilidades altas a
# ninguna, y verificar sale en 4,8 ms por documento contra 6,3. No hay
# contrapartida que pagar.

# --- etapa 1: construir la rueda -------------------------------------------
FROM python:3.13-alpine AS constructor

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=2.4.3

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /origen
COPY pyproject.toml poetry.lock README.md LICENSE ./
COPY src ./src

# --no-cache para que no quede el arbol de dependencias resuelto en la capa.
RUN poetry build --format wheel --no-cache


# --- etapa 2: la imagen que se publica -------------------------------------
FROM python:3.13-alpine

# Etiquetas OCI: son lo que hace que la imagen se pueda rastrear hasta su
# fuente. Sin esto, un binario publicado es un binario sin procedencia.
LABEL org.opencontainers.image.title="pysifen" \
      org.opencontainers.image.description="Servidor MCP para leer y verificar documentos tributarios electronicos del Paraguay (SIFEN)" \
      org.opencontainers.image.source="https://github.com/josecuev/pysifen" \
      org.opencontainers.image.documentation="https://josecuev.github.io/pysifen/mcp/" \
      org.opencontainers.image.licenses="MIT"

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# libxml2 y libxslt las necesita lxml, que es lo que valida contra el XSD.
#
# El upgrade no sobra: la imagen base se publica cada tantas semanas y Alpine
# saca parches de seguridad entre medio. Sin esta linea, una imagen construida
# hoy sale con los CVE que Alpine ya arreglo: son cuatro altos de util-linux.
RUN apk upgrade --no-cache \
    && apk add --no-cache libxml2 libxslt

COPY --from=constructor /origen/dist/*.whl /tmp/
# El [mcp] va entre comillas o el shell lo lee como una clase de caracteres.
#
# Y despues se saca pip. No es cosmetico: pip trae copias vendorizadas de
# msgpack y setuptools que aparecen en cualquier escaneo de vulnerabilidades
# aunque este servidor no las importe nunca. Una imagen de un solo proposito no
# instala nada en caliente, asi que pip ahi es superficie de ataque y ruido en
# el informe.
RUN rueda="$(ls /tmp/*.whl)" \
    && pip install "${rueda}[mcp]" \
    && pip uninstall --yes pip \
    && rm -f /tmp/*.whl

# Nada de esto necesita root. Un servidor que procesa documentos que le
# manda cualquiera, menos todavia.
RUN adduser --disabled-password --uid 10001 pysifen
USER pysifen
WORKDIR /home/pysifen

EXPOSE 8000

# El servidor responde a un GET con 4xx porque espera POST: que conteste algo
# ya prueba que esta escuchando y que el proceso vive.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request as u, urllib.error as e; \
exec('try:\n u.urlopen(\"http://127.0.0.1:8000/mcp\", timeout=3)\nexcept e.HTTPError:\n pass')"

ENTRYPOINT ["pysifen-mcp"]

# Dentro del contenedor hay que escuchar en 0.0.0.0 o el mapeo de puertos no
# llega. Quien decide la exposicion es el operador, publicando el puerto solo
# en loopback: -p 127.0.0.1:8000:8000. El servidor NO tiene autenticacion.
CMD ["--http", "--host", "0.0.0.0"]
