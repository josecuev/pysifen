# Normativa vigente

Revisión hecha el **10 de setiembre de 2026** contra fuentes primarias: los PDF
originales publicados por la DNIT en `dnit.gov.py` y el registro de la Autoridad
Certificadora Raíz en `acraiz.gov.py`. Todo lo que sigue está verificado contra
el documento oficial, no contra resúmenes de terceros.

## Estado técnico

| Documento | Versión | Fecha | Estado |
|---|---|---|---|
| Manual Técnico SIFEN | **v150** | 10/09/2019 | Vigente |
| Notas Técnicas | **NT 001 a 027** | última: 09/03/2026 | Vigentes, acumulativas |

!!! warning "No existe un Manual Técnico v160"
    El manual base sigue siendo el v150 de 2019 y se enmienda por Notas
    Técnicas. La implementación correcta es *MT v150 + NT 001…027 aplicadas en
    orden*. La NT-006 no figura publicada en el portal; las otras 26 sí.

!!! danger "El paquete de XSD publicado está desactualizado"
    El archivo `Estructura_DE xsd.rar` del portal es de 2018 y describe nodos
    (`gCiODE`, `gDTim`, `gCamOC`) que ya no existen en la estructura vigente. No
    sirve como fuente de verdad. La estructura válida es la de las tablas de
    campos del MT v150 con sus notas técnicas.

### Cambios recientes que impactan la implementación

**NT-027 — 09/03/2026.** Evento de Nominación de Factura Electrónica: agrega
`iTipIDRec` (GENFE010) y `dDTipIDRec` (GENFE011), obligatorios si
`GENFE004 = 2`. Códigos admitidos: 1 cédula paraguaya, 2 pasaporte, 3 cédula
extranjera, 4 carnet de residencia, 6 tarjeta diplomática de exoneración fiscal,
9 otro.

**NT-026 — 06/06/2025.** Compras públicas (B2G): `gCompPub` (E020), `dDncpG`
(E704) y `dDncpE` (E705) pasan a ser **opcionales** cuando `D202 = 3`. Se
eliminan las validaciones 1400, 1401, 1800 y 1801 que los exigían.

**NT-025 — 23/04/2025.** Se elimina la validación GEC002c (código 4004). Ahora
el emisor puede cancelar un DE aunque el receptor ya lo haya confirmado.

**NT-024 — 17/12/2024.** Validación D208c (código 1321): el receptor **no puede
ser Innominado** (`D2085`) cuando el total de la operación en guaraníes es
`>= 7.000.000`, salvo que la transacción sea de Muestras médicas (`D01113`).
Base legal: Decreto n.° 872/2023, artículo 6, numeral 2, inciso ii.

## Estado normativo

### Marco legal

| Norma | Contenido |
|---|---|
| Ley n.° 125/1991, Libro V | Régimen tributario base |
| Ley n.° 6380/2019 | Modernización y simplificación del sistema tributario |
| **Ley n.° 6822/2021** | Servicios de confianza para transacciones electrónicas y documento electrónico |
| **Decreto n.° 7576/2022** | Reglamenta la Ley 6822/2021 |
| Ley n.° 7143/2023 | Crea la DNIT, que sucede a la SET |
| **Decreto n.° 872/2023** | Reglamenta la emisión electrónica a través del SIFEN |
| Ley n.° 7021/2022 | Contrataciones públicas; dispara obligatoriedad |

!!! note "El marco de firma digital cambió y el manual no lo refleja"
    El MT v150 todavía cita la **Ley 4017/2010** de firma digital, pero las
    resoluciones vigentes se apoyan en la **Ley 6822/2021 de servicios de
    confianza** y su Decreto 7576/2022. Para el diseño del módulo de PKI manda
    la 6822, que es la que define la figura de *prestador cualificado de
    servicios de confianza*.

### Resoluciones de obligatoriedad

| Resolución | Fecha | Qué hace |
|---|---|---|
| RG n.° 105/2021 | 2021 | Medidas administrativas para DTE y primeras designaciones |
| RG DNIT n.° 06/2024 | 2024 | Reglamenta e-Kuatia'i, la solución gratuita |
| RG DNIT n.° 21/2024 | 2024 | Designaciones y medidas para adhesión obligatoria y voluntaria |
| RG DNIT n.° 41/2025 | 2025 | Obligatoriedad para quienes contraten con sujetos del art. 2° de la Ley 7021/2022, desde el 02/01/2026 |
| **RG DNIT n.° 52/2026** | **05/05/2026** | Designa los grupos 19 a 24 y modifica el art. 2° de la RG 21/2024 |

#### Calendario de la RG DNIT n.° 52/2026

| Anexo | Grupo | Fecha de inicio |
|---|---|---|
| I | 19 | 01 de junio de 2026 |
| II | 20 | 01 de setiembre de 2026 |
| III | 21 | 01 de diciembre de 2026 |
| IV | 22 | 02 de marzo de 2027 |
| V | 23 | 01 de junio de 2027 |
| VI | 24 | 01 de setiembre de 2027 |

Puntos operativos de esa resolución:

- El contribuyente designado debe emitir **todos** sus documentos tributarios
  sólo en formato electrónico, por e-Kuatia o e-Kuatia'i. **Se exceptúa** el
  Comprobante de Retención virtual.
- **Prórroga**: por única vez, hasta tres meses, y sólo si la adhesión es al
  Sistema Transaccional. Se solicita con nota presentada **30 días hábiles
  antes** de la fecha de inicio, con cédula, nota de autorización si
  corresponde, y carta de compromiso más cronograma firmados por el
  contribuyente **y el desarrollador informático**.
- El timbrado de documentos preimpresos o autoimpresos **pierde vigencia al día
  siguiente** de la fecha de inicio. No hay convivencia entre papel y
  electrónico.
- Si otra norma ya obligaba en una fecha anterior, **prevalece la anterior**.

## Prestadores cualificados habilitados

Fuente: registro de la Autoridad Certificadora Raíz del Paraguay, administrada
por el Ministerio de Industria y Comercio.

| Prestador | Resolución | Tipos que emite |
|---|---|---|
| VIT S.A. | 774/2014 | F1, F2, F3 |
| CODE100 S.A. | 187/2015 | F1, F2, F3, sellos de tiempo, sellos electrónicos, identificación remota |
| DOCUMENTA S.A. | 20/2016 | F1, F2, F3, sellos de tiempo, sellos electrónicos, identificación remota |
| Ministerio del Interior (Dpto. de Identificaciones) | 381/2023 | Sólo F2 |
| CONFIRMA S.A. | 510/2023 | F1, F2, F3, sellos de tiempo, identificación remota |
| ITTI S.A.E.C.A. | 530/2024 | F1, F3, identificación remota |
| SOS Tecnología y Gestión de Información Ltda. | 0365/2025 | F1, F2, F3, sellos de tiempo, identificación remota |

Tipos de certificado:

- **F1** — firma digital por software. El archivo `.p12` clásico.
- **F2** — firma digital por hardware. Token o HSM.
- **F3** — firma remota. La clave privada vive en el HSM del prestador y nunca
  sale de ahí.

!!! warning "El F3 es posterior al manual"
    El MT v150 (§7.5) contempla sólo **F1 y F2**. La firma producida por un F3
    es igualmente XMLDSig válida, así que a nivel de documento es aceptable,
    pero la **autenticación mutua TLS** contra los web services necesita una
    clave utilizable para `clientAuth`. Eso hay que confirmarlo con el prestador
    antes de comprometerse a un esquema puramente remoto.

## Requisitos técnicos del manual

### Certificado digital

Apartados 7.5, 7.7 y 7.9:

- X.509 v3 emitido por un prestador habilitado por el MIC.
- RSA **2048** por software; **2048 o 4096** por hardware.
- Se usa para dos cosas distintas: firmar el XML y **autenticarse por TLS
  mutuo**. Para lo segundo el certificado necesita `Extended Key Usage` con
  `clientAuth`.
- El RUC se informa siempre con el formato `RUCXXXXXXXXX-X`: la palabra `RUC` en
  mayúsculas, el número, un guion y el dígito verificador, sin espacios.
    - **Persona jurídica** → en `Subject`, atributo `SerialNumber` (OID 2.5.4.5).
    - **Persona física** → en `SubjectAlternativeName`, `SerialNumber`
      (OID 2.5.4.5). Además el certificado debe llevar nombre y RUC de la
      entidad donde presta servicio el titular.

### Firma digital

Apartados 7.6 y 7.7:

- XMLDSig **enveloped** sobre el grupo `A001`, o sea el elemento `DE`,
  identificado por el atributo `Id` **cuyo valor es el CDC**.
- `Reference URI` = `#` seguido del CDC.
- `CanonicalizationMethod` = `http://www.w3.org/TR/2001/REC-xml-c14n-20010315`,
  o sea c14n **inclusivo**.
- `Transforms` = `enveloped-signature` seguido de
  `http://www.w3.org/2001/10/xml-exc-c14n#`, o sea c14n **exclusivo**.
- `SignatureMethod` = `rsa-sha256`. `DigestMethod` = `sha256`.
- `KeyInfo` sólo con `X509Data/X509Certificate`.
- **Prohibidos**: `X509SubjectName`, `X509IssuerSerial`, `X509IssuerName`,
  `X509SKI`, `KeyValue`, `RSAKeyValue`, `Modulus`, `Exponent`.
- No hay que adjuntar la lista de certificados revocados: el SIFEN la consulta
  por su cuenta al validar.

!!! note "La mezcla de canonicalizaciones no es un error de tipeo"
    El manual pide c14n **inclusivo** en `CanonicalizationMethod` y c14n
    **exclusivo** en el `Transform` de la `Reference`. Es una particularidad del
    SIFEN y hay que respetarla tal cual.

### Comunicación

Apartados 7.9 y 7.10:

- SOAP **1.2**, WS-I Basic Profile 1.1, estilo Document/Literal.
- **TLS 1.2 con autenticación mutua** por certificado digital.

| Servicio | Ruta |
|---|---|
| Recepción de DE | `/de/ws/sync/recibe.wsdl` |
| Recepción de lote | `/de/ws/async/recibe-lote.wsdl` |
| Eventos | `/de/ws/eventos/evento.wsdl` |
| Consulta de lote | `/de/ws/consultas/consulta-lote.wsdl` |
| Consulta de DE | `/de/ws/consultas/consulta.wsdl` |
| Consulta de RUC | `/de/ws/consultas/consulta-ruc.wsdl` |

Los hosts son `sifen.set.gov.py` para producción y `sifen-test.set.gov.py` para
test. Servidores NTP oficiales: `aravo1.set.gov.py` y `aravo2.set.gov.py`. La
DNIT se reserva limitar el acceso por contribuyente o por dirección IP.

### Código de Control

Apartados 10.1 a 10.3. Son 44 dígitos:

| Posición | Largo | Campo |
|---|---|---|
| 1 | 2 | Tipo de documento electrónico |
| 3 | 8 | RUC del emisor sin dígito verificador |
| 11 | 1 | Dígito verificador del RUC |
| 12 | 3 | Establecimiento |
| 15 | 3 | Punto de expedición |
| 18 | 7 | Número del documento |
| 25 | 1 | Tipo de contribuyente |
| 26 | 8 | Fecha de emisión `AAAAMMDD` |
| 34 | 1 | Tipo de emisión |
| 35 | 9 | Código de seguridad |
| 44 | 1 | Dígito verificador del CDC |

El dígito verificador se calcula por módulo 11 con pesos cíclicos de 2 a 11
aplicados de derecha a izquierda. Verificado contra el ejemplo del propio
manual: el CDC `0144 4444 0170 0100 1001 4528 2201 7012 5158 7326 0988` cierra
con dígito `8`, y el RUC `44444401` con dígito `7`.

El código de seguridad `dCodSeg` debe ser un número positivo de nueve dígitos,
aleatorio, **no secuencial**, distinto para cada documento, sin relación con
ningún dato del documento ni del emisor, y distinto del número de documento
`dNumDoc`.

!!! danger "El código de seguridad es un requisito criptográfico"
    El manual pide *un algoritmo de complejidad suficiente para evitar la
    reproducción del valor*. Si el código se pudiera predecir, se podría
    anticipar el CDC de un documento ajeno. Hay que generarlo con el generador
    aleatorio criptográfico del sistema, no con un PRNG común.

### Código QR

Apartado 13.8:

- Estándar ISO/IEC 18004. Ancho mínimo de impresión 25 mm: 22 de contenido más
  3 de margen seguro. Si se agranda, el margen es el 10% del ancho total.
- El contenido va en el campo `J002`.
- Base de consulta: `https://ekuatia.set.gov.py/consultas/qr?` en producción y
  `https://ekuatia.set.gov.py/consultas-test/qr?` en test.
- Parámetros, en este orden: `nVersion`, `Id`, `dFeEmiDE`,
  `dRucRec` o `dNumIDRec`, `dTotGralOpe`, `dTotIVA`, `cItems`, `DigestValue`,
  `IdCSC`, y al final `cHashQR`.
- `dFeEmiDE` y `DigestValue` van convertidos a **hexadecimal**.
- Si `dTotGralOpe` o `dTotIVA` no tienen valor, se completa con `0`.
- `cHashQR` es SHA-256 sobre la cadena de parámetros **con el CSC concatenado al
  final**, expresado en hexadecimal.
- El CSC tiene 32 caracteres alfanuméricos, lo entrega el SIFEN, y se permiten
  hasta dos códigos activos a la vez.

!!! danger "El CSC nunca viaja en la URL"
    El manual es explícito: el contribuyente no debe compartir su código de
    seguridad ni enviarlo concatenado como parte de la URL del QR. Participa
    sólo del cálculo del hash. Merece el mismo tratamiento de custodia que la
    clave privada.

## Fuentes

Descargadas y leídas en original el 10 de setiembre de 2026:

- Manual Técnico SIFEN v150 —
  [dnit.gov.py](https://www.dnit.gov.py/documents/20123/420592/Manual+T%C3%A9cnico+Versi%C3%B3n+150.pdf)
- Notas Técnicas 001 a 027 —
  [dnit.gov.py](https://www.dnit.gov.py/web/e-kuatia/documentacion-tecnica)
- Guía de Pruebas para e-Kuatia — portal de documentación técnica de la DNIT
- Resolución General DNIT n.° 52/2026 y n.° 21/2024 —
  [dnit.gov.py](https://www.dnit.gov.py/web/portal-institucional/resoluciones)
- Registro de prestadores cualificados —
  [acraiz.gov.py](https://www.acraiz.gov.py/html/Certif_1PrestaServ.html)
