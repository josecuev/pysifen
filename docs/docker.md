# Imagen de Docker

`josecuev/pysifen` levanta el [servidor MCP](mcp.md) sin instalar nada: lee
facturas electrónicas del Paraguay y dice si se puede confiar en ellas.

```bash
docker run --rm -p 127.0.0.1:8000:8000 josecuev/pysifen
```

Queda escuchando en `http://127.0.0.1:8000/mcp`, en Streamable HTTP, sin estado
entre llamadas.

!!! danger "El puerto va publicado en loopback"
    El servidor **no tiene autenticación**: quien llegue al puerto puede usarlo.
    Por eso el ejemplo dice `-p 127.0.0.1:8000:8000` y no `-p 8000:8000`, que lo
    abriría a cualquiera que alcance la máquina. Si tiene que salir de ahí, va
    detrás de un proxy que autentique.

Dentro del contenedor el servidor escucha en `0.0.0.0` porque de otro modo el
mapeo de puertos no llegaría. Quien decide la exposición es el operador.

## Verificar un archivo local

```bash
docker run --rm -v "$PWD/facturas:/facturas:ro" \
  josecuev/pysifen --herramientas
```

El montaje va en **sólo lectura**: la herramienta lee documentos, nunca los
modifica.

## La línea de comandos

La imagen también trae el comando `pysifen`:

```bash
docker run --rm --entrypoint pysifen josecuev/pysifen grupos --json
docker run --rm --entrypoint pysifen -v "$PWD:/w:ro" -w /w \
  josecuev/pysifen validar factura.xml
```

## Cómo está armada

| Decisión | Por qué |
|---|---|
| Alpine, no Debian slim | La base slim son 189 MB contra 55, y esa diferencia se traslada entera: 274 MB contra 165 |
| Dos etapas | Poetry y el código fuente se quedan en la primera. Lo que se publica sólo tiene la rueda instalada |
| Usuario `pysifen` (uid 10001) | Nada de esto necesita root, y menos un servidor que procesa documentos que le manda cualquiera |
| `apk upgrade` en la construcción | La imagen base se publica cada tantas semanas; Alpine saca parches entre medio |
| Sin `pip` en la imagen final | Sus copias vendorizadas de `msgpack` y `setuptools` aparecen en todo escaneo aunque nunca se importen. Una imagen de un solo propósito no instala nada en caliente |
| Sin estado | No guarda nada entre llamadas. Los documentos tributarios traen datos de contribuyentes: lo que no se retiene no se filtra |

### Sobre Alpine

La objeción clásica a Alpine es que obliga a compilar las dependencias
nativas. Ya no aplica: `lxml`, `cryptography` y `pydantic-core` publican ruedas
`musllinux`, así que la instalación no compila nada y la construcción tarda
menos de un minuto.

Se midió antes de cambiar, sobre los mismos documentos reales:

| | Debian slim | Alpine |
|---|---|---|
| Tamaño | 274 MB | **165 MB** |
| Vulnerabilidades | 3 altas, 6 medias, 31 bajas | **0 altas, 0 medias, 3 bajas** |
| Verificar un documento | 6,3 ms | **4,8 ms** |
| Veredicto sobre los documentos reales | idéntico | idéntico |

No hubo contrapartida que pagar.

### Hasta dónde se puede achicar

Los 165 MB son lo que ocupa **descomprimida en disco**. Lo que `docker pull`
transfiere son **40,8 MB**, que es el número que le importa a quien la baja.

De esos 165, unos 121 son la base `python:3.13-alpine` —Python mismo son 47— y
44 son las dependencias del proyecto. Adentro de esos 44 mandan `cryptography`
(15 MB), `lxml` (12) y `pydantic` con su núcleo (9). Ninguna se puede cambiar
por algo más chico sin perder lo que hace la librería: X.509 y RSA la primera,
validación contra el XSD y canonicalización la segunda, los 49 grupos del
documento la tercera.

Se probaron tres recortes más y **los tres se descartaron con la medición
hecha**:

| Intento | Resultado |
|---|---|
| Borrar de la stdlib lo que no se usa (`idlelib`, `tkinter`, `ensurepip`) | **+11 MB.** Borrar un archivo que vive en una capa inferior no lo saca: agrega una marca de borrado y el archivo sigue ocupando lugar abajo |
| `strip` a las extensiones nativas | **+3 MB.** Instalar `binutils` y reescribir los `.so` cuesta más de lo que ahorran los símbolos |
| Instalar sin bytecode (`--no-compile`) | −15 MB en disco, pero sólo −1,9 MB de descarga, y el arranque pasa de 693 ms a 910 ms. Se paga en **cada** ejecución, y un servidor MCP por stdio arranca una vez por sesión |

El último es el único que ahorraba algo de verdad, y aun así el precio es peor
que el premio: 1,9 MB menos de descarga, una sola vez, a cambio de 217 ms más
cada vez que alguien lo levanta.

## Seguridad

Cada construcción se escanea con [Trivy](https://trivy.dev/) —vulnerabilidades,
secretos y configuración— y **no se publica nada que no haya pasado el
escaneo**. El corte es sobre lo que tiene arreglo publicado: cortar por lo que
todavía no lo tiene convertiría la puerta en algo que todos aprenden a saltear.

El escaneo también corre semanalmente sin que nadie toque el repositorio, porque
una imagen publicada hace un mes se vuelve vulnerable sola.

Cada imagen publicada viaja con su **SBOM** y su **procedencia**, así que se
puede comprobar de qué commit salió y qué trae adentro:

```bash
docker buildx imagetools inspect josecuev/pysifen:latest \
  --format "{{ json .Provenance }}"
docker scout sbom josecuev/pysifen:latest
```

## Etiquetas

| Etiqueta | Qué es |
|---|---|
| `latest` | La última publicada |
| `0.4.0` | Una versión exacta. **Es la que conviene fijar en producción** |
| `0.4` | La última correctiva de esa serie |

Arquitecturas: `linux/amd64` y `linux/arm64`.

## Qué verifica

Esquema oficial, firma digital, cadena de confianza hasta la Autoridad
Certificadora Raíz del Paraguay, vigencia del certificado al momento de la
firma, RUC, coherencia del CDC y del QR. No hace falta certificado propio: el
documento trae adentro el de quien lo firmó.

Lo único que no comprueba es la revocación, que necesita salir a la red del
prestador, y cada respuesta lo declara.

- Documentación: <https://josecuev.github.io/pysifen/>
- Código: <https://github.com/josecuev/pysifen>
- Licencia: MIT
