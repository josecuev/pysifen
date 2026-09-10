# Notas para agentes de IA

Esta página está escrita para un agente que tenga que usar `pysifen`. Es más
directa que el resto de la documentación y se concentra en lo que suele salir
mal.

Si sos una persona, también sirve: son las mismas trampas.

## Si lo que tenés que hacer es *leer* un documento

Empezá por acá, porque es el caso frecuente y se resuelve en una línea:

```python
from pysifen.lectura import verificar_documento

resultado = verificar_documento(xml_recibido)
resultado.confiable  # el veredicto: True significa auténtico
resultado.resumir()  # dict compacto, serializable, listo para razonar sobre él
```

Tres cosas que conviene saber antes de usar el resultado:

1. **`confiable` significa auténtico**, no "parece bien". Exige esquema, firma,
   cadena de confianza hasta la Autoridad Certificadora Raíz del Paraguay,
   vigencia a la firma, RUC, CDC y QR. Cualquier comprobación que no se pueda
   hacer cuenta como fallada.
2. **`resumir()` declara su propio límite**, en `limite_de_la_verificacion`. Hoy
   dice que no se consulta la revocación. Leelo y pasalo adelante: si informás
   un veredicto sin su límite, estás afirmando más de lo que se comprobó.
3. **`tolerancias` no está vacío gratis.** Si tiene algo, la firma verificó pero
   el documento no era estrictamente conforme al estándar. No es motivo de
   alarma —son desvíos conocidos de emisores reales— pero quien audita tiene
   derecho a saberlo.

Si además necesitás el documento entero y no sólo el veredicto:

```python
from pysifen.documento import documento_desde_xml

de = documento_desde_xml(xml_recibido)
de.gTotSub.dTotGralOpe  # Decimal, con la escala del original
[i.dDesProSer for i in de.gDtipDE.gCamItem]
```

Devuelve los 49 grupos con tipos de Python, no cadenas: `Decimal` para los
importes, `date` y `datetime` para las fechas. Y **rechaza** un documento con un
elemento que el esquema no declara, en vez de ignorarlo.

No hace falta certificado propio ni estar habilitado como facturador para nada
de esto.

!!! warning "El documento no se cree a sí mismo"
    Nada de lo que el documento *dice* sobre su emisor cuenta como prueba: el
    nombre del prestador, la razón social y el RUC son texto. Lo que prueba es
    la firma y la cadena. Si tenés que reportar de quién es un documento, usá
    `resultado.prestador`, que sale de la Lista de Confianza oficial, y no lo
    que diga el certificado de sí mismo.

El resto de esta página es para **emitir**.

## Lo primero: no adivines la estructura

El documento electrónico tiene **49 grupos y más de 400 campos**. No hay que
recordarlos ni inferirlos. La librería se describe a sí misma, y esa
descripción sale del esquema oficial de la DNIT:

```bash
pysifen buscar dTotGralOpe --json   # ¿en qué grupo vive este campo?
pysifen grupo CamItem --json        # ¿qué campos tiene? ¿cuáles obligatorios?
pysifen grupos --json               # ¿qué grupos existen?
```

Desde Python:

```python
from pysifen.documento import grupos_disponibles

grupos = grupos_disponibles()  # 49 modelos, por nombre de clase
campos = grupos["CamItem"].model_fields  # nombre -> tipo, obligatoriedad, descripción
```

**Todos los comandos aceptan `--json`.** Usá esa salida en vez de interpretar
texto.

!!! danger "Si un campo no aparece, no existe"
    Los modelos rechazan campos desconocidos. Inventar un nombre de campo
    porque *parece* razonable produce un error de validación, no un documento.
    Eso es deliberado: un campo inventado sería rechazado por el SIFEN de todas
    formas, pero mucho más tarde y con un mensaje peor.

## El orden de las operaciones no es negociable

```python
1. armar el DE           # modelos de pysifen.documento
2. calcular el CDC       # Cdc.crear(...)
3. sobre_rde(de, cdc)    # el CDC va como atributo Id del DE
4. firmar_documento(...) # inserta el Signature
5. generar_url_qr(...)   # necesita el DigestValue que produjo la firma
6. agregar_campos_fuera_de_firma(raiz, url)   # el QR va DESPUÉS de la firma
7. validar_documento(...)  # antes de transmitir
```

Los pasos 4 y 5 no se pueden invertir: **el QR incluye el `DigestValue` de la
firma**. Un QR generado antes de firmar no verifica, y el error recién aparece
cuando alguien escanea el comprobante.

`agregar_campos_fuera_de_firma` lanza `ValueError` si el documento no está
firmado, justamente para que ese error no llegue a producción.

## Las cuatro trampas que más cuestan

### 1. Las descripciones son literales exactos

Los campos `dDes*` no son texto libre: el esquema los enumera carácter por
carácter. `"Normal"` es válido; `"normal"` no.

```python
Operacion(iTipEmi=1, dDesTipEmi="normal", dCodSeg="587326098")
# ValidationError: Input should be 'Normal' or 'Contingencia'
```

Preguntá cuáles acepta antes de escribir uno:

```bash
pysifen grupo COpeDE --json | grep -A2 dDesTipEmi
```

### 2. Los importes conservan sus decimales

El SIFEN escribe `36500.00000000`, no `36500`. El hash del QR se calcula sobre
esa cadena exacta, así que normalizar rompe la verificación.

Usar `Decimal` con la escala que corresponde, no `float`:

```python
from decimal import Decimal

Decimal("36500.00000000")  # bien
36500.0  # mal: float pierde precisión y escala
```

### 3. El código de seguridad necesita azar criptográfico

`dCodSeg` no puede salir de `random`. Si se pudiera predecir, se podría
anticipar el CDC de un documento ajeno.

```python
from pysifen.security import generar_codigo_seguridad

codigo = generar_codigo_seguridad(distinto_de=numero_de_documento)
```

### 4. La canonicalización de la firma

El ejemplo del manual muestra c14n inclusivo para el `SignedInfo`; los
documentos que el SIFEN acepta usan **exclusivo**. El valor por omisión de la
librería es el que funciona. No cambiarlo sin leer
[la decisión 0002](decisiones/0002-canonicalizacion.md).

## Nunca hagas esto

- **No escribas la clave privada, la contraseña del keystore ni el CSC en un
  log, un mensaje de error o un archivo de configuración versionado.** La
  librería usa [`Secreto`][pysifen.security.secretos.Secreto] justamente para
  que un `print` accidental no los filtre.
- **No pongas el CSC en la URL del QR.** Participa sólo del hash. La librería
  lo garantiza; no armes la URL a mano.
- **No edites los archivos de `pysifen/esquemas/`.** Son copias byte a byte de
  las que publica la DNIT. Editarlos haría que la librería acepte documentos
  que el SIFEN rechaza. Hay un test que lo detecta.
- **No edites `pysifen/documento/_generado.py`.** Se genera desde el esquema; el
  cambio se perdería en la próxima regeneración.
- **No inventes campos ni validaciones** que no estén en el esquema o en el
  Manual Técnico. Si algo falta, documentalo en `docs/decisiones/` con la cita
  de lo que la fuente sí dice.

## Validá antes de transmitir

```python
from pysifen import validar_documento

problemas = validar_documento(firmado)
if problemas:
    for p in problemas:
        print(p)  # "línea 12: Element 'gCamIVA': Missing child element(s)..."
```

Un rechazo del SIFEN llega con un mensaje escueto y después de un viaje de ida
y vuelta. La validación local dice la línea exacta.

Desde la consola:

```bash
pysifen validar documento.xml --json
```

Devuelve `2` si el documento es inválido, así que sirve en un script.

## Cómo saber si la normativa cambió

```bash
python scripts/verificar_esquemas.py             # los esquemas, contra la DNIT
python scripts/verificar_lista_de_confianza.py   # la Lista de Confianza del MIC
```

El detalle de qué vigilar y dónde está en
[Vigilancia normativa](mantenimiento/vigilancia-normativa.md). Si el esquema
cambió, **cambió el contrato**, aunque el Manual Técnico siga diciendo lo mismo.

## Qué garantiza la librería y qué no

**Garantiza**: que la estructura, el orden, los tipos y las enumeraciones son
los del esquema oficial; que la firma verifica contra una implementación
independiente del estándar; que el CDC y el QR se calculan como manda el manual.

**No garantiza**: que el SIFEN acepte el documento. Eso depende además de reglas
de negocio que el esquema no expresa —totales que cierren, un timbrado vigente,
un receptor válido— y de la habilitación del contribuyente. La validación local
es necesaria, no suficiente.
