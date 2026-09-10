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

Lo único que se reutiliza es el esquema XSD compilado y la Lista de Confianza,
que son datos de la librería y no del usuario. Compilar el esquema lleva del
orden de un segundo; hacerlo por pedido haría inviable un lote.

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
    "prestador": "Documenta SA",
    "cadena_de_confianza": true,
    "certificado_vigente_al_firmar": true,
    "ruc_coincide_con_el_certificado": true,
    "cdc_coherente": true,
    "qr_coherente": true
  },
  "limite_de_la_verificacion": "no se consulta la lista de certificados
  revocados, que requiere red. Todo lo demás está verificado, incluida la
  cadena de confianza hasta la Autoridad Certificadora Raíz del Paraguay."
}
```

La clave `confiable` va primero a propósito: es la que decide si el resto se
puede usar. Los errores también vuelven como dato, con `"ok": false` y un
mensaje: un modelo maneja mucho mejor un resultado que una traza de excepción.

## Qué significa `confiable`, exactamente

Significa **auténtico**: el documento lo emitió quien dice, y nadie lo tocó
después. Para llegar ahí tienen que pasar todas estas, y cualquiera que no se
pueda comprobar cuenta como que no pasó:

| Comprobación | Qué prueba |
|---|---|
| Esquema | Que el documento tiene la estructura oficial |
| Firma | Que **ni un carácter** cambió desde que se firmó |
| Cadena de confianza | Que el certificado lo emitió de verdad un prestador cualificado habilitado, hasta la Autoridad Certificadora Raíz del Paraguay |
| Vigencia a la firma | Que el certificado estaba vigente *cuando se firmó*, no hoy |
| RUC | Que el documento no lo firmó otro contribuyente |
| CDC y QR | Que el código de control y el QR corresponden al documento |

La cadena se valida contra la [Lista de Confianza][tsl] que publica el
Ministerio de Industria y Comercio, comprobando la firma de cada eslabón. Un
certificado autofirmado que *dice* ser de DOCUMENTA se rechaza; uno que
DOCUMENTA firmó de verdad se acepta. Ver
[la decisión 0004](decisiones/0004-cadena-de-confianza.md).

  [tsl]: https://www.acraiz.gov.py/tsl/tsl_Py.xml

!!! warning "Lo único que queda afuera: la revocación"
    No se consulta la lista de certificados revocados del prestador, porque es
    la única comprobación que necesita salir a la red. Un certificado revocado
    con cadena válida se informa hoy como confiable.

    Por eso cada respuesta incluye `limite_de_la_verificacion`, para que quien
    la lea —persona o modelo— sepa exactamente qué no se comprobó.

## Por qué verificar si el SIFEN ya aprobó el documento

Es la objeción razonable, y cada vez más: desde que los sistemas de facturación
consultan la aprobación antes de enviar, a un administrativo casi no le llega un
documento que el SIFEN haya rechazado.

Pero son dos cosas distintas. La aprobación dice que **el emisor declaró ese
documento ante la DNIT**. La firma dice que **el archivo que tenés en la mano es
ese documento y no otro**. Entre una cosa y la otra hay un correo, un reenvío,
una carpeta compartida y, a veces, alguien con interés en cambiar un importe.

Lo que esta verificación detecta no es el error del emisor —eso ya lo filtró el
SIFEN— sino la alteración posterior y el documento fabricado: el XML que nunca
existió del lado de la DNIT pero llega con aspecto de factura. Ninguna de las
dos cosas la ve el ojo, y las dos las ve la firma.

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
