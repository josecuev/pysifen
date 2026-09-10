# Custodia del certificado

La clave privada del certificado tributario es el activo crítico de cualquier
integración con el SIFEN. Quien la tiene puede emitir documentos tributarios a
nombre del contribuyente. No es una credencial más: es la firma de la empresa.

Esta página explica cómo `pysifen` la trata y por qué.

## El principio

> La librería nunca ve la clave privada si puede evitarlo, y cuando la ve, no la
> deja salir.

De ahí se derivan tres reglas que atraviesan todo el código:

1. **Toda firma pasa por el puerto [`Firmante`][pysifen.signing.ports.Firmante].** Ningún módulo consume una clave
   directamente. El armador de XML sabe *qué* hay que firmar; no sabe *cómo* ni
   *dónde* vive la clave.
2. **No existe ninguna API que exporte material de clave privada.** No hay
   `firmante.clave_privada`, no hay `.exportar()`, no hay `__repr__` que la
   muestre. Hay tests que lo verifican.
3. **Los secretos no se imprimen.** El CSC y las contraseñas de keystore se
   manejan con [`Secreto`][pysifen.security.secretos.Secreto], que oculta su
   valor en `repr`, `str`, interpolación de cadenas y trazas de excepción, y se
   niega a serializarse con `pickle`.

## Por qué un puerto y no una clase

El Manual Técnico contempla dos tipos de certificado, F1 por software y F2 por
hardware, y los prestadores hoy emiten además F3 de firma remota. Son tres
mecanismos con propiedades de seguridad muy distintas, y la elección depende del
volumen de emisión, del presupuesto y de qué le vende el prestador al
contribuyente.

Atar la librería a uno solo sería atarla a la decisión de compra de un cliente.
Por eso el módulo de firma define un puerto y los mecanismos son adaptadores
intercambiables: la dependencia apunta a la abstracción, no al revés.

## Los niveles de custodia

Ordenados de más a menos protegido.

### 1. Firma remota cualificada (F3)

La clave se genera y vive dentro del HSM del prestador cualificado. Nunca
existe fuera de ahí. El sistema del contribuyente pide una firma y recibe la
firma, no la clave.

- **Exposición de la clave**: ninguna. No hay nada que robar del servidor.
- **Contra**: depende de la disponibilidad del prestador, y hay que verificar
  con él si el mismo certificado sirve para `clientAuth` en el TLS mutuo contra
  los web services. El MT v150 es anterior al F3 y no lo menciona.

### 2. HSM de red o token por hardware (F2), vía PKCS#11

La clave se genera dentro del dispositivo y está marcada como no exportable. El
dispositivo firma; la clave no sale.

- **Exposición de la clave**: ninguna mientras el módulo sea confiable. Lo que
  se compromete si cae el servidor es el *acceso* a firmar, no la clave.
- **Contra**: un token USB en un servidor es frágil de operar. Para volumen
  conviene un HSM de red.

### 3. Keystore cifrado en disco (F1) con la clave envuelta

El `.p12` se guarda cifrado con una clave de cifrado que a su vez está protegida
por un servicio de gestión de claves. La contraseña no está en el código, ni en
el repositorio, ni en una variable de entorno de un `docker-compose` versionado.

- **Exposición de la clave**: real. Si alguien obtiene el archivo y la clave que
  lo envuelve, tiene la firma del contribuyente.
- **Cuándo**: cuando el prestador sólo entregó un F1 y todavía no hay HSM.

### 4. `.p12` en texto plano

Es lo que hace casi todo el mundo y es lo que hay que dejar de hacer.

`pysifen` **no** acepta esta configuración por omisión:

```python
FirmantePkcs12.desde_archivo("cert.p12", contrasena)
# ConfiguracionError: Cargar la clave privada desde un archivo PKCS#12 la deja
# expuesta: quien obtenga el archivo y su contraseña puede emitir documentos
# tributarios a nombre del contribuyente. Si entendés y aceptás esa exposición,
# pasá permitir_clave_en_disco=True...
```

Hay que habilitarla de forma explícita, y la librería emite un `AvisoDeCustodia`
cada vez que se usa. La fricción es deliberada: quien la desactiva sabe lo que
está aceptando.

## Cómo se elige el nivel en el código

Cada backend declara su nivel, y una aplicación puede exigir un mínimo en el
arranque en vez de confiar en que nadie configure mal:

```python
from pysifen.signing import NivelDeCustodia, exigir_nivel

firmante = exigir_nivel(construir_firmante(), NivelDeCustodia.CLAVE_EN_DISPOSITIVO)
```

Si el firmante configurado es un `.p12`, eso falla en el arranque con un mensaje
que dice qué nivel se exigía y cuál se recibió. No falla en producción a la hora
de emitir.

| Backend | Certificado | Nivel |
|---|---|---|
| `FirmanteRemoto` | F3 | `CLAVE_FUERA_DEL_ALCANCE` |
| `FirmantePkcs11` | F2 | `CLAVE_EN_DISPOSITIVO` |
| `FirmantePkcs12` | F1 | `CLAVE_EN_MEMORIA` |

## Auditoría de las firmas

Firmar un documento tributario es un acto con consecuencias jurídicas. Saber
cuántas veces se firmó, cuándo y con qué certificado es lo que permite detectar
un uso indebido: si el registro muestra firmas a las tres de la mañana de un
domingo, algo pasó.

```python
from pysifen.signing import FirmanteAuditado

firmante = FirmanteAuditado(firmante, registrar=guardar_en_la_base)
```

Es un decorador, no una clase base: envuelve cualquier backend sin que ninguno
se entere, y no cambia el nivel de custodia.

Se registra el **hecho**: cuándo, con qué certificado, si salió bien, y un
resumen SHA-256 de lo firmado que permite correlacionar sin revelar nada. **No**
se registra el contenido, ni la firma, ni la clave. Un registro de auditoría que
filtra lo que audita no sirve para nada.

## Qué no hace la librería

- No genera claves privadas. Las claves de un certificado cualificado las genera
  el prestador o el dispositivo, no una librería de facturación.
- No guarda certificados por su cuenta ni inventa un formato de almacén propio.
- No manda la clave, la contraseña ni el CSC por la red hacia ningún destino que
  no sea el propio SIFEN o el HSM configurado.
- No escribe secretos en el log, ni siquiera en nivel `DEBUG`.

## El CSC merece el mismo trato

El Código de Seguridad del Contribuyente no es una clave privada, pero es un
secreto compartido con la DNIT que autentica el QR. Si se filtra, se pueden
fabricar QR que parezcan auténticos.

Por eso [`generar_url_qr`][pysifen.qr.generar_url_qr] recibe el CSC como
`Secreto` y no como `str`: hace falta un `revelar()` explícito para obtener el
valor, y ese `revelar()` ocurre en una sola línea, dentro del cálculo del hash.
El CSC nunca llega a la URL resultante, y hay un test que lo verifica.

## Lista de control antes de producción

- [ ] La clave privada no está en el repositorio ni en la imagen del contenedor.
- [ ] La contraseña del keystore no está en una variable de entorno versionada.
- [ ] El CSC no está en el código ni en el log.
- [ ] El certificado tiene `clientAuth` en `Extended Key Usage`, que es lo que
      exige el TLS mutuo del apartado 7.9 del manual.
- [ ] El RUC del certificado coincide con el del emisor, en `SerialNumber` del
      `Subject` si es persona jurídica o en el `SubjectAlternativeName` si es
      persona física.
- [ ] Hay un procedimiento escrito de rotación y de revocación.
- [ ] Está registrado quién puede pedir una firma y queda traza de cada pedido.
