<h1 align="center">pysifen</h1>

<p align="center">
  <em>Facturación electrónica del Paraguay (SIFEN) en Python.</em>
</p>

<p align="center">
  <a href="https://github.com/josecuev/pysifen/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/josecuev/pysifen/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://pypi.org/project/pysifen/"><img alt="PyPI" src="https://img.shields.io/pypi/v/pysifen.svg"></a>
  <a href="https://pypi.org/project/pysifen/"><img alt="Python" src="https://img.shields.io/pypi/pyversions/pysifen.svg"></a>
  <a href="https://github.com/josecuev/pysifen/blob/master/LICENSE"><img alt="Licencia" src="https://img.shields.io/pypi/l/pysifen.svg"></a>
  <a href="https://josecuev.github.io/pysifen/"><img alt="Documentación" src="https://img.shields.io/badge/docs-mkdocs--material-blue.svg"></a>
  <a href="https://github.com/astral-sh/ruff"><img alt="Ruff" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json"></a>
  <a href="https://mypy-lang.org/"><img alt="mypy" src="https://img.shields.io/badge/mypy-strict-2a6db2.svg"></a>
  <a href="https://hub.docker.com/r/josecuev/pysifen"><img alt="Docker" src="https://img.shields.io/docker/v/josecuev/pysifen?label=docker&logo=docker"></a>
</p>

---

Librería para **leer, verificar y emitir** documentos tributarios electrónicos
contra el **Sistema Integrado de Facturación Electrónica Nacional** de la
Dirección Nacional de Ingresos Tributarios: armado del XML, Código de Control,
firma XMLDSig, código QR y comunicación con los web services.

Verificar una factura recibida **no requiere certificado propio ni estar
habilitado como facturador**: el documento trae adentro el certificado de quien
lo firmó, y la cadena se valida contra la Lista de Confianza oficial del
Ministerio de Industria y Comercio.

La implementación sigue el **Manual Técnico v150** con las **Notas Técnicas 001
a 027** aplicadas de forma acumulativa. Cada módulo cita en su docstring el
apartado del manual que implementa.

## Instalación

```bash
pip install pysifen
```

O sin instalar nada, el servidor MCP en Docker (165 MB, sin root):

```bash
docker run --rm -p 127.0.0.1:8000:8000 josecuev/pysifen
```

## Ejemplo

Verificar una factura que llegó por correo:

```python
from pysifen.lectura import verificar_documento

resultado = verificar_documento(open("factura.xml", "rb").read())
resultado.confiable  # True significa auténtico, no "parece bien"
resultado.prestador  # "Documenta SA", según la Lista de Confianza del MIC
print(resultado.informe())
```

Y armar el Código de Control de uno propio:

```python
from datetime import date

from pysifen import Cdc, TipoContribuyente, TipoDocumento
from pysifen.security import generar_codigo_seguridad

cdc = Cdc.crear(
    tipo_documento=TipoDocumento.FACTURA,
    ruc_emisor="80012345-6",
    establecimiento="001",
    punto_expedicion="001",
    numero="0000123",
    tipo_contribuyente=TipoContribuyente.PERSONA_JURIDICA,
    fecha_emision=date.today(),
    codigo_seguridad=generar_codigo_seguridad(),
)

print(cdc.valor)  # 44 dígitos
print(cdc.formateado)  # en grupos de cuatro, como va impreso en el KuDE
```

## Estado

> [!WARNING]
> Versión 0.6.0. Lee y verifica documentos recibidos de punta a punta, y arma y
> firma documentos propios, pero **todavía no los transmite al SIFEN**. La API
> puede cambiar mientras la versión empiece en `0.`. Ver la
> [hoja de ruta](https://josecuev.github.io/pysifen/hoja-de-ruta/).

| Componente | Estado |
|---|---|
| Código de Control (CDC) y dígito verificador | Listo |
| Código de seguridad `dCodSeg` | Listo |
| Código QR del KuDE | Listo |
| Tablas de códigos del Manual Técnico | Parcial |
| Armado del XML: sobre, firma y campos fuera de firma | Listo |
| Línea de comandos | Listo |
| Modelos de los 49 grupos, generados desde el esquema | Listo |
| Validación contra el esquema oficial de la DNIT | Listo |
| Lectura y verificación de documentos recibidos | Listo |
| Servidor MCP sin estado (stdio y HTTP) | Listo |
| Cadena de confianza hasta la Raíz del Paraguay | Listo |
| Imagen de Docker del servidor MCP | Listo |
| Firma XMLDSig | Listo |
| Custodia de la clave (F1, F2, F3) y auditoría | Listo |
| Lectura de certificados y prestadores cualificados | Listo |
| Lectura completa del documento a los modelos | Listo |
| Revocación (OCSP con respaldo en CRL) | Listo |
| Web services (recepción, lote, consultas, eventos) | Pendiente |

## Línea de comandos

La librería se describe a sí misma, así que no hace falta saberse el manual:

```bash
pysifen buscar dTotGralOpe    # ¿en qué grupo vive este campo?
pysifen grupo CamItem         # ¿qué campos tiene? ¿cuáles obligatorios?
pysifen validar factura.xml   # ¿lo acepta el esquema oficial?
pysifen cdc 0144444401700...  # descompone un Código de Control
```

Todos los comandos aceptan `--json`, para consumirlos desde otro programa.

## Principios

- **La fuente de verdad es el manual oficial.** Nada se implementa de oído.
  Cuando el manual no dice algo, se documenta la decisión con la cita de lo que
  sí dice.
- **La clave privada es sagrada.** Toda firma pasa por un puerto abstracto y la
  librería no expone ninguna forma de exportar material de clave.
- **Los prestadores son intercambiables.** El soporte de prestadores
  cualificados es un punto de extensión declarado por *entry points*: agregar
  uno nuevo no requiere tocar el núcleo.
- **Los nombres del SIFEN se respetan.** Los campos se llaman `dCodSeg`,
  `gCamFuFD`, `iTipEmi` como en el manual, para que buscar un campo en el manual
  y en el código dé lo mismo.

## Documentación

<https://josecuev.github.io/pysifen/>

- [Normativa vigente](https://josecuev.github.io/pysifen/normativa-vigente/) —
  qué está en vigor, con fechas y citas de fuentes primarias.
- [Custodia del certificado](https://josecuev.github.io/pysifen/seguridad/custodia/) —
  cómo se protege la clave privada y por qué.
- [Vigilancia normativa](https://josecuev.github.io/pysifen/mantenimiento/vigilancia-normativa/) —
  dónde mirar cuando la DNIT cambie algo.

## Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md). En resumen: `ruff check .`, `mypy` y
`pytest` tienen que pasar, y todo cambio de comportamiento cita el apartado del
Manual Técnico que lo justifica.

## Licencia

[MIT](LICENSE).

## Aviso

Proyecto independiente. No está afiliado ni respaldado por la Dirección Nacional
de Ingresos Tributarios del Paraguay.
