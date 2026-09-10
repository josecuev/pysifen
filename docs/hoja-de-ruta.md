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

### 0.9.0 — contra el ambiente de test de la DNIT

Acá deja de ser una librería que *cree* estar bien y pasa a ser una que *está*
bien.

**Criterio**, y es el que importa de verdad:

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

- [ ] Todo lo anterior.
- [ ] Al menos un contribuyente emitiendo en **producción** con la librería.
- [ ] La API pública sin cambios incompatibles durante un ciclo de versión
      menor completo.
- [ ] La representación gráfica (KuDE) o una decisión documentada de dejarla
      fuera del alcance.

A partir de 1.0.0, un cambio incompatible obliga a subir la versión mayor. Por
eso no se llega antes de tiempo: comprometerse con una API que todavía no se
probó contra el organismo sería prometer algo que no se puede sostener.

## Lo que no está en la hoja de ruta

- **Ser un proveedor de facturación.** Esto es una librería: arma, firma,
  valida y transmite. No administra timbrados, no lleva numeración, no guarda
  documentos.
- **Interfaz gráfica.**
- **Soporte para versiones del Manual Técnico anteriores a la v150.**
