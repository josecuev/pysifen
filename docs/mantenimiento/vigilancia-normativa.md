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

## 4. Los esquemas XSD — la fuente que más importa

<https://ekuatia.set.gov.py/sifen/xsd/>

**Es la fuente definitiva.** El XSD es contra lo que el SIFEN valida cada
documento que recibe: si el Manual Técnico y el XSD se contradicen, gana el XSD.

Los archivos publicados son once, encadenados por `xs:include`:

```
siRecepDE_v150.xsd          wrapper de 395 bytes, declara <rDE>
└── DE_v150.xsd             estructura completa del documento
    ├── DE_Types_v150.xsd   tipos y enumeraciones
    ├── Paises_v100.xsd
    ├── Departamentos_v141.xsd
    ├── Monedas_v150.xsd
    └── Unidades_Medida_v141.xsd

siRecepEvento_v150.xsd      wrapper, declara <gGroupGesEve>
└── Evento_v150.xsd         todos los eventos en un solo archivo
    └── Evento_Types_v150.xsd
```

La librería trae copias **byte a byte idénticas** en
`src/pysifen/esquemas/`, con sus checksums en `checksums.json`. El script
compara las copias contra el servidor:

```bash
python scripts/verificar_esquemas.py
```

Devuelve distinto de cero si algo cambió. El workflow de vigilancia lo corre
todas las semanas.

!!! danger "Dos copias que circulan y no sirven"
    - **`Estructura_DE xsd.rar`** del portal de documentación técnica: es de
      2018 y describe nodos (`gCiODE`, `gDTim`, `gCamOC`) que ya no existen.
    - **El paquete `20190910_XSD_v150`** que aparece en repositorios públicos:
      es la publicación original del v150 y no trae las enmiendas de las notas
      técnicas. Se verificó que documentos reales de producción **no validan**
      contra él: rechaza `dBasExe` (agregado por la NT-013), el grupo `gOblAfe`
      y el valor `IVA - Renta` de `dDesTImp`.

    Los esquemas del servidor en vivo sí validan documentos reales de 2026.

Los WSDL de los servicios web, en cambio, **no** se pueden consultar: devuelven
HTTP 302 sin certificado cliente, porque están detrás del TLS mutuo del
apartado 7.9.

## 5. Servidores de hora

El apartado 7.11 fija `aravo1.set.gov.py` y `aravo2.set.gov.py` como servidores
NTP oficiales. La fecha de la firma tiene que ser anterior a la de transmisión,
así que un reloj corrido produce rechazos difíciles de diagnosticar.

## Chequeo automático

El workflow `.github/workflows/vigilancia.yml` corre cada lunes y abre un
issue si aparece una nota técnica nueva, si cambia la versión del manual, o
—lo más importante— **si cambia alguno de los esquemas publicados**. No
reemplaza mirar, pero evita enterarse tarde.

## Resumen

| Qué | Dónde | Hoy |
|---|---|---|
| Manual Técnico | `dnit.gov.py/web/e-kuatia/documentacion-tecnica` | v150 |
| Notas técnicas | misma página, o probar la URL de la siguiente | NT-027 |
| Resoluciones | `dnit.gov.py/web/portal-institucional/resoluciones` | RG 52/2026 |
| Prestadores | `acraiz.gov.py/html/Certif_1PrestaServ.html` | 7 habilitados |
| Versión real en uso | `schemaLocation` de cualquier DTE recibido | `siRecepDE_v150.xsd` |
| **Esquemas XSD** | `ekuatia.set.gov.py/sifen/xsd/` | 11 archivos, verificados |
