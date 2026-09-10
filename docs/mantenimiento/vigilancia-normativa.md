# Dónde mirar si algo cambió

El SIFEN se enmienda seguido y sin aviso a los integradores. Esta página lista
las fuentes que hay que vigilar, con la URL exacta y qué se busca en cada una.

Última verificación completa: **10 de setiembre de 2026**.

## 1. Manual Técnico y Notas Técnicas

**Fuente principal**

<https://www.dnit.gov.py/web/e-kuatia/documentacion-tecnica>

Ahí se publican el Manual Técnico y todas las notas técnicas. Qué mirar:

- **Versión del Manual Técnico.** Hoy es la **150** (10/09/2019). Si aparece una
  160 o superior, es un cambio de fondo y hay que releer todo.
- **Nota técnica de número más alto.** Hoy es la **027** (09/03/2026).

**Truco para detectar una nota nueva sin abrir el portal**

Las notas siguen un patrón de URL predecible. Basta pedir la siguiente y ver si
existe:

```bash
curl -sSL -f -o /dev/null \
  "https://www.dnit.gov.py/documents/20123/420595/NT_E_KUATIA_028_MT_V150.pdf" \
  && echo "salió la NT-028"
```

Reemplazar `028` por el número siguiente al último conocido. Un `404` significa
que todavía no hay nada nuevo.

!!! note "La NT-006 no existe"
    Hay un hueco en la numeración: la 006 nunca se publicó. No es un error de
    descarga.

**Verificación cruzada con la realidad**

La forma más confiable de saber qué versión está realmente en producción es
mirar un documento tributario recién recibido. El `schemaLocation` lo declara:

```xml
xsi:schemaLocation="http://ekuatia.set.gov.py/sifen/xsd siRecepDE_v150.xsd"
```

Una factura de agosto de 2026 seguía declarando `v150`. Si empiezan a llegar
documentos con otro número, cambió algo aunque el portal no lo diga todavía.

## 2. Resoluciones de la DNIT

<https://www.dnit.gov.py/web/portal-institucional/resoluciones>

Qué mirar: resoluciones generales que designen nuevos grupos de facturadores
electrónicos, cambien fechas de obligatoriedad o modifiquen el régimen. La
última relevante es la **RG DNIT n.° 52/2026** (05/05/2026), que designa los
grupos 19 a 24 con vencimientos escalonados hasta setiembre de 2027.

El calendario vigente está en [Normativa vigente](../normativa-vigente.md).

## 3. Prestadores cualificados

<https://www.acraiz.gov.py/html/Certif_1PrestaServ.html>

Registro de la Autoridad Certificadora Raíz, administrada por el Ministerio de
Industria y Comercio. Qué mirar: prestadores nuevos habilitados, o alguno que
pierda la habilitación.

Hoy son **siete**. Cuando aparezca el octavo, se agrega una fábrica en
`pysifen/pki/prestadores.py` y su *entry point* en el `pyproject.toml`. No hace
falta tocar nada más: ver
[Custodia del certificado](../seguridad/custodia.md).

## 4. El XSD — la fuente que falta

**El paquete que publica el portal está desactualizado.** `Estructura_DE xsd.rar`
es de 2018 y describe nodos (`gCiODE`, `gDTim`, `gCamOC`) que ya no existen. No
sirve.

Los WSDL de los servicios web **no se pueden consultar sin certificado**:

```
https://sifen.set.gov.py/de/ws/sync/recibe.wsdl?wsdl        -> HTTP 302
https://sifen-test.set.gov.py/de/ws/sync/recibe.wsdl?wsdl   -> HTTP 302
```

Están detrás del TLS mutuo que exige el apartado 7.9, así que tampoco se puede
sacar el esquema de ahí.

Dónde conseguirlo entonces:

- **Del prestador o del proveedor de software habilitado.** A los integradores
  certificados se les entrega el paquete de esquemas.
- **Del ambiente de test**, una vez que se tenga un certificado habilitado. La
  respuesta del SIFEN a un documento transmitido es la confirmación definitiva.
- **De implementaciones ya en producción** en otros lenguajes, que suelen
  incluir el XSD en su repositorio.

Mientras tanto, el orden de los campos de la factura electrónica está derivado
de documentos reales; ver
[Orden de los campos](../decisiones/0001-orden-de-los-campos.md).

## 5. Servidores de hora

El apartado 7.11 fija `aravo1.set.gov.py` y `aravo2.set.gov.py` como servidores
NTP oficiales. La fecha de la firma tiene que ser anterior a la de transmisión,
así que un reloj corrido produce rechazos difíciles de diagnosticar.

## Chequeo automático

El workflow `.github/workflows/vigilancia.yml` corre cada lunes y avisa si
aparece una nota técnica nueva o si cambia la página de documentación técnica.
No reemplaza mirar, pero evita enterarse tarde.

## Resumen

| Qué | Dónde | Hoy |
|---|---|---|
| Manual Técnico | `dnit.gov.py/web/e-kuatia/documentacion-tecnica` | v150 |
| Notas técnicas | misma página, o probar la URL de la siguiente | NT-027 |
| Resoluciones | `dnit.gov.py/web/portal-institucional/resoluciones` | RG 52/2026 |
| Prestadores | `acraiz.gov.py/html/Certif_1PrestaServ.html` | 7 habilitados |
| Versión real en uso | `schemaLocation` de cualquier DTE recibido | `siRecepDE_v150.xsd` |
