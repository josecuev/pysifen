# Hoja de ruta

El versionado sigue [SemVer](https://semver.org/lang/es/). Mientras la versión
empiece en `0.`, **la API pública puede cambiar sin aviso** entre versiones
menores.

Cada hito tiene un criterio verificable, no una impresión. Un hito está cumplido
cuando se puede demostrar, no cuando parece que sí.

## Dónde estamos

### 0.2.0 — el núcleo estructural (publicada)

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
| Línea de comandos | Operación y auto-descripción |

Lo que **no** hay: transmitir.

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

### 0.3.0 — la cadena de confianza

Es el hueco que hoy impide decir "auténtico".

El prestador se identifica comparando el nombre del emisor del certificado
contra una lista, y ese nombre es texto que cualquiera escribe en un
certificado autofirmado. Sirve para clasificar, no para probar.

Qué hace falta: los certificados raíz de los siete prestadores habilitados, y
verificar la ruta de confianza desde el certificado del documento hasta uno de
ellos.

**Criterio**: un certificado autofirmado que dice ser de DOCUMENTA es
rechazado; uno realmente emitido por DOCUMENTA es aceptado.

### 0.4.0 — entender por qué fallan las firmas reales

De cinco documentos reales de cinco emisores distintos, **cuatro no verifican
su firma**. No es un error del verificador: una implementación independiente
falla en los mismos cuatro.

Hasta saber por qué, la herramienta no se puede recomendar: diría "no
confiable" sobre documentos legítimos.

**Criterio**: explicación documentada de cada caso, y si resulta ser de la
librería, corregido. Si resulta del camino por correo o del emisor, dicho con
evidencia.

### 0.5.0 — lectura completa a modelos

Hoy se extraen los campos que identifican al documento con caminos XPath. Falta
interpretar el documento entero a los modelos generados, sin perder nada.

**Criterio**: un documento leído y vuelto a serializar produce un XML
equivalente.

### 0.6.0 — revocación

Consultar la lista de certificados revocados del prestador. Es la única
comprobación que necesita red, así que va explícita y nunca por omisión.

**Criterio**: un certificado revocado se detecta; sin red, se informa que no se
pudo comprobar en vez de darlo por bueno.

### 1.0.0 — leer y validar, al 100%

**Criterio**:

- [ ] Las cuatro anteriores.
- [ ] Verificación completa: esquema, firma, cadena de confianza, vigencia a la
      firma, revocación, coherencia de CDC y QR.
- [ ] Documentos reales de emisores distintos verificados correctamente.
- [ ] `confiable` significa **auténtico**, no "las comprobaciones que sé hacer
      pasaron".
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
