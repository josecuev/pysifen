# Hoja de ruta

El versionado sigue [SemVer](https://semver.org/lang/es/). Mientras la versión
empiece en `0.`, **la API pública puede cambiar sin aviso** entre versiones
menores.

Cada hito tiene un criterio verificable, no una impresión. Un hito está cumplido
cuando se puede demostrar, no cuando parece que sí.

## Dónde estamos

### 0.5.0 — leer y verificar de verdad (actual)

Lo que hay hoy:

| Componente | Estado |
|---|---|
| Código de Control (CDC) y dígito verificador | Verificado contra el ejemplo del manual |
| Código de seguridad `dCodSeg` | Generador criptográfico |
| Código QR del KuDE | Verificado contra el ejemplo del manual |
| Modelos de los 49 grupos | Generados desde el esquema oficial |
| Validación contra el esquema oficial | 5 documentos reales validan |
| Firma XMLDSig | Verificada con una implementación independiente |
| Custodia de la clave (F1, F2, F3) y auditoría | Los tres backends |
| Lectura de certificados y prestadores cualificados | Probada contra un certificado real |
| Cadena de confianza hasta la Raíz del Paraguay | 5 certificados reales encadenan; un autofirmado que dice ser de DOCUMENTA se rechaza |
| Lectura completa del documento a los modelos | 4 documentos reales dan la vuelta sin perder nada |
| Servidor MCP sin estado | 6 herramientas, stdio y Streamable HTTP |
| Imagen de Docker | 165 MB, sin root, sin vulnerabilidades con arreglo |
| Línea de comandos | Operación y auto-descripción |

Lo que **no** hay: revocación, transmitir.

## Lo que falta

## El criterio que ordena todo

**La 1.0.0 es leer y validar. La 2.0.0 es emitir.**

No es un orden arbitrario. Leer y validar se puede completar y demostrar **sin
certificado propio y sin estar habilitado como facturador**: el documento trae
adentro el certificado de quien lo firmó. Emitir, en cambio, depende de un
trámite ante la DNIT y de un certificado cualificado, o sea de hechos que el
proyecto no controla.

Además es lo que más gente necesita: una empresa recibe muchos más documentos
de los que emite.

El código de emisión que ya existe —CDC, firma, QR, modelos— sigue ahí y sigue
probado, pero queda marcado como **en desarrollo**: la promesa de estabilidad de
la 1.0.0 no lo cubre.

## Camino a la 1.0.0 — leer y validar

### 0.3.0 — la cadena de confianza ✔

**Criterio**: un certificado autofirmado que dice ser de DOCUMENTA es
rechazado; uno realmente emitido por DOCUMENTA es aceptado.

**Cumplido.** Las anclas salen de la [Lista de Confianza][tsl] que publica el
Ministerio de Industria y Comercio en formato ETSI TS 119 612, y en cada eslabón
se comprueba la firma, no el nombre. Los cinco certificados reales encadenan
hasta la Autoridad Certificadora Raíz del Paraguay; el autofirmado no encadena
con nadie. Ver [la decisión 0004](decisiones/0004-cadena-de-confianza.md).

  [tsl]: https://www.acraiz.gov.py/tsl/tsl_Py.xml

### 0.4.0 — entender por qué fallan las firmas reales ✔

**Criterio**: explicación documentada de cada caso, y si resulta ser de la
librería, corregido. Si resulta del camino por correo o del emisor, dicho con
evidencia.

**Cumplido.** Eran dos desvíos del lado del emisor, ninguno de la librería: el
`SignedInfo` canonicalizado en aislamiento —el emisor arma la firma como
documento aparte antes de insertarla— y el XML indentado después de firmar. El
verificador los tolera y **declara cuál toleró**, en `tolerancias`. El quinto
documento no corresponde a su propio resumen bajo ninguna interpretación, y se
rechaza.

### 0.5.0 — lectura completa a modelos ✔

**Criterio**: un documento leído y vuelto a serializar produce un XML
equivalente.

**Cumplido.** `documento_desde_xml()` interpreta el documento entero a los 49
grupos, y los cuatro documentos reales vuelven a salir con los mismos 156, 138,
151 y 147 elementos, mismos nombres, mismos textos y mismos atributos.

La lectura es genérica y no una tabla de 49 entradas: los modelos ya saben su
etiqueta, sus campos y sus tipos, y el generador garantiza que el nombre del
campo **es** la etiqueta del elemento. Un grupo nuevo en el esquema aparece solo
al regenerar.

De paso destapó un error que también afectaba a la emisión: `dCodSeg` estaba
tipado como entero, y el esquema lo declara `xs:integer` con `pattern
[0-9]{9}`. Un patrón restringe la forma **léxica**, así que `000166795` es
válido y `166795` no: la librería podía producir un XML que el SIFEN rechaza.
Son ocho los campos así, y ahora van como cadena.

### 0.6.0 — revocación

Consultar la lista de certificados revocados del prestador. Es la única
comprobación que necesita red, así que va explícita y nunca por omisión.

**Criterio**: un certificado revocado se detecta; sin red, se informa que no se
pudo comprobar en vez de darlo por bueno.

### 1.0.0 — leer y validar, al 100%

**Criterio**:

- [x] 0.3.0 — cadena de confianza.
- [x] 0.4.0 — firmas reales explicadas.
- [x] 0.5.0 — lectura completa a modelos.
- [ ] 0.6.0 — revocación.
- [ ] Verificación completa: esquema, firma, cadena de confianza, vigencia a la
      firma, revocación, coherencia de CDC y QR.
- [ ] Documentos reales de emisores distintos verificados correctamente.
- [x] `confiable` significa **auténtico**, no "las comprobaciones que sé hacer
      pasaron". Falta sólo la revocación, que se declara en cada respuesta.
- [ ] La API pública de lectura, estable.

A partir de acá, un cambio incompatible en la API de lectura obliga a subir la
versión mayor.

## Camino a la 2.0.0 — emitir

### 1.x — la API de emisión y los eventos

Una fachada que orqueste armar, calcular el CDC, firmar, generar el QR y
validar. Y los eventos: cancelación, inutilización, nominación, conformidad.

### 1.x — servicios web

SOAP 1.2 con TLS mutuo contra los seis servicios del SIFEN.

### 2.0.0 — emitir de verdad

**Criterio**:

- [ ] Un documento emitido por la librería, firmado con un certificado
      cualificado real, **aceptado por el ambiente de test del SIFEN**.
- [ ] Al menos una factura, una nota de crédito y una nota de remisión.
- [ ] Un evento de cancelación aceptado.
- [ ] La respuesta del SIFEN guardada como evidencia.

Es una versión mayor y no menor porque el primer contacto real con el organismo
casi seguro obliga a cambiar algo de la API.

## Lo que no está en la hoja de ruta

- **Ser un proveedor de facturación.** Esto es una librería: arma, firma,
  valida y transmite. No administra timbrados, no lleva numeración, no guarda
  documentos.
- **Interfaz gráfica.**
- **Soporte para versiones del Manual Técnico anteriores a la v150.**
