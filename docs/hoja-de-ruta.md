# Hoja de ruta

El versionado sigue [SemVer](https://semver.org/lang/es/). Mientras la versión
empiece en `0.`, **la API pública puede cambiar sin aviso** entre versiones
menores.

Cada hito tiene un criterio verificable, no una impresión. Un hito está cumplido
cuando se puede demostrar, no cuando parece que sí.

## Dónde estamos

### 0.2.0 — el núcleo estructural

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

### 0.3.0 — la API de emisión

Una fachada que orqueste el ciclo completo en vez de obligar a encadenar siete
llamadas en el orden correcto.

**Criterio**: emitir una factura completa y válida en una sola llamada, con los
ejemplos de la documentación corriendo como tests.

### 0.4.0 — eventos

Cancelación, inutilización, nominación, conformidad y disconformidad. Los
esquemas ya están incluidos (`Evento_v150.xsd`); falta modelarlos y armarlos.

**Criterio**: cada tipo de evento se arma y valida contra su esquema.

### 0.5.0 — servicios web

SOAP 1.2 con TLS mutuo contra los seis servicios: recepción, lote, consulta de
lote, consulta de DE, consulta de RUC y eventos.

**Criterio**: los seis clientes implementados, con sus respuestas modeladas y
sus errores traducidos.

### 0.6.0 — leer y verificar documentos recibidos

El otro lado del negocio, y el que más gente necesita: **recibir**. Una empresa
recibe muchos más documentos de los que emite, y cada uno hay que leerlo,
verificar que sea auténtico y extraer sus datos.

Esta capacidad **no necesita certificado propio ni habilitación**: se puede
entregar y demostrar de forma completa.

Qué incluye:

- Leer un documento recibido a los modelos, sin perder nada.
- Verificar la firma: recalcular el resumen y comprobar la firma con el
  certificado que el propio documento trae.
- Verificar el certificado: que sea de un prestador cualificado, y que
  estuviera **vigente al momento de la firma**, que es la fecha que importa, no
  la de hoy.
- Verificar la coherencia interna: que el CDC cierre, que el RUC del CDC sea el
  del certificado, que el QR declare los mismos totales que el documento.
- Procesar lotes sin releer el esquema en cada documento.

**Criterio**: verificar documentos reales de emisores distintos, y detectar una
alteración de un solo carácter.

Estado: la lectura, la verificación de firma y el servidor MCP ya están. Falta
lo más importante: **validar la cadena de confianza**. Hoy el prestador se
identifica por el nombre del emisor del certificado, que es falsificable.
Hasta que eso se resuelva, `confiable` significa «todas las comprobaciones
disponibles pasaron», no «auténtico».

### 0.9.0 — contra el ambiente de test de la DNIT

Acá deja de ser una librería que *cree* estar bien y pasa a ser una que *está*
bien.

**Criterio**:

- [ ] Un documento emitido por la librería, firmado con un certificado
      cualificado real, **aceptado por el ambiente de test del SIFEN**.
- [ ] Al menos una factura, una nota de crédito y una nota de remisión.
- [ ] Un evento de cancelación aceptado.
- [ ] La respuesta del SIFEN guardada como evidencia.

Hasta que eso pase, ninguna cantidad de tests locales alcanza. La validación
contra el esquema es necesaria pero no suficiente: el SIFEN aplica además
reglas de negocio que el esquema no expresa.

### 1.0.0 — API estable

**Criterio**:

- [ ] Todo lo anterior: emitir, leer, verificar y transmitir.
- [ ] La API pública sin cambios incompatibles durante un ciclo de versión
      menor completo.
- [ ] La representación gráfica (KuDE) o una decisión documentada de dejarla
      fuera del alcance.

A partir de acá, un cambio incompatible obliga a subir la versión mayor.

La 1.0.0 **no** espera a que alguien emita en producción. Ese es un hecho
comercial, no técnico, y hacer depender el número de versión de algo que el
proyecto no controla dejaría la librería en 0.x para siempre. Lo que la 1.0.0
promete es que la API es estable y que todo lo que la librería dice hacer, lo
hace y está probado.

### 2.0.0 — probada en producción

**Criterio**:

- [ ] Al menos un contribuyente emitiendo en **producción** con la librería, de
      forma sostenida.
- [ ] Los ajustes que ese uso real haya obligado a hacer, que casi seguro
      incluyen algún cambio incompatible: por eso es una versión mayor y no una
      menor.

## Lo que no está en la hoja de ruta

- **Ser un proveedor de facturación.** Esto es una librería: arma, firma,
  valida y transmite. No administra timbrados, no lleva numeración, no guarda
  documentos.
- **Interfaz gráfica.**
- **Soporte para versiones del Manual Técnico anteriores a la v150.**
