# Servidor MCP

Expone la librería como herramientas que un modelo puede invocar. El caso que
resuelve es el más frecuente en la práctica: **alguien recibe una factura
electrónica y necesita saber qué dice y si puede confiar en ella**.

Verificar no requiere certificado propio ni estar habilitado como facturador:
el documento trae adentro el certificado de quien lo firmó.

## Por qué sin estado

No guarda nada entre llamadas. Cada herramienta recibe el documento, lo procesa
y devuelve el resultado.

No es una simplificación. La revisión **2026-07-28** del protocolo eliminó las
sesiones del transporte HTTP, así que un servidor sin estado es el modelo
natural. Y para este dominio es además lo prudente: los documentos tributarios
traen datos de contribuyentes, y un servidor que no los retiene no tiene nada
que filtrar.

Lo único que se reutiliza es el esquema XSD compilado y el registro de
prestadores, que son datos de la librería y no del usuario. Compilar el esquema
lleva del orden de un segundo; hacerlo por pedido haría inviable un lote.

## Instalación

=== "Escritorio (recomendado)"

    Con `uvx` no hace falta instalar nada: descarga y ejecuta en el momento.

    ```json
    {
      "mcpServers": {
        "pysifen": {
          "command": "uvx",
          "args": ["--from", "pysifen[mcp]", "pysifen-mcp"]
        }
      }
    }
    ```

    Va en el archivo de configuración del cliente de escritorio. Es la forma
    más eficiente: sin entorno virtual que mantener, y se actualiza sola al
    publicarse una versión nueva.

=== "Instalado"

    ```bash
    pip install "pysifen[mcp]"
    ```

    ```json
    {
      "mcpServers": {
        "pysifen": {
          "command": "pysifen-mcp"
        }
      }
    }
    ```

=== "Servidor HTTP"

    ```bash
    pysifen-mcp --http --puerto 8000
    ```

    Levanta Streamable HTTP en `http://127.0.0.1:8000/mcp`, con
    `stateless_http` y `json_response` activados: sin sesión y sin abrir un
    flujo SSE para respuestas que se resuelven de una.

    !!! warning "No lo expongas sin pensarlo"
        Por omisión escucha sólo en `127.0.0.1`. Cambiar `--host` lo abre a
        cualquiera que alcance esa red, y el servidor **no tiene
        autenticación**: quien llegue puede usarlo. Si va a salir de la
        máquina, ponelo detrás de un proxy que autentique.

## Las herramientas

| Herramienta | Para qué |
|---|---|
| `verificar_factura` | Lee un documento y dice si se puede confiar en él |
| `verificar_facturas` | Lo mismo para un lote, compilando el esquema una vez |
| `analizar_cdc` | Descompone un Código de Control de 44 dígitos |
| `buscar_campo` | En qué grupo vive un campo del SIFEN |
| `describir_grupo` | Campos de un grupo, con tipos y obligatoriedad |
| `listar_grupos` | Los 49 grupos del documento |

Para ver las definiciones sin levantar el servidor:

```bash
pysifen-mcp --herramientas
```

## Qué devuelve

Una versión compacta del documento, con el veredicto adelante. Un documento
tributario en XML ocupa unos 10 KB; esto suele quedar en menos de 500 bytes:

```json
{
  "ok": true,
  "confiable": true,
  "cdc": "01800140664044002007120322026082317377733681",
  "tipo": "Factura electrónica",
  "emitido": "2026-08-23T22:27:26",
  "emisor": "SERVICIOS RAPIDOS DEL PARAGUAY S.A.",
  "ruc_emisor": "80014066-4",
  "total": "36500.00000000",
  "verificacion": {
    "esquema": true,
    "firma": true,
    "prestador": "DOCUMENTA S.A.",
    "certificado_vigente_al_firmar": true,
    "ruc_coincide_con_el_certificado": true,
    "cdc_coherente": true,
    "qr_coherente": true
  },
  "limite_de_la_verificacion": "la cadena de confianza no se valida: ..."
}
```

La clave `confiable` va primero a propósito: es la que decide si el resto se
puede usar. Los errores también vuelven como dato, con `"ok": false` y un
mensaje: un modelo maneja mucho mejor un resultado que una traza de excepción.

## Qué significa `confiable`, exactamente

!!! danger "No significa auténtico"
    Significa que **todas las comprobaciones disponibles pasaron**. Todavía no
    se valida la cadena de confianza: el prestador se identifica comparando el
    nombre del emisor del certificado contra una lista, y ese nombre es texto
    que cualquiera puede escribir en un certificado autofirmado.

    Por eso cada respuesta incluye `limite_de_la_verificacion`, para que quien
    la lea —persona o modelo— sepa qué no se comprobó.

Lo que **sí** prueba algo, y mucho: la firma. Si alguien cambió un solo
carácter del documento, la verificación falla. Eso está probado con un test que
altera un dígito y comprueba que se detecta.

La validación de la cadena está en la [hoja de ruta](hoja-de-ruta.md) como
criterio de la 0.6.0.

## Uso desde Python

Si preferís armar tu propio servidor, la maquinaria está disponible:

```python
from pysifen.lectura import verificar_documento, leer_documentos

resultado = verificar_documento(xml_recibido)
resultado.confiable  # el veredicto
resultado.resumir()  # dict compacto, serializable a JSON
resultado.informe()  # texto para mostrar o registrar

informes = leer_documentos(["a.xml", "b.xml"])  # lote, esquema compilado una vez
```
