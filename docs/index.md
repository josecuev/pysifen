# pysifen

Librería Python para el **Sistema Integrado de Facturación Electrónica Nacional
(SIFEN)** de Paraguay.

Arma el XML del documento electrónico, calcula el Código de Control, lo firma
con XMLDSig, genera el código QR y lo transmite a los web services de la
Dirección Nacional de Ingresos Tributarios.

---

## Estado

!!! warning "En desarrollo"
    La versión publicada todavía no cubre el ciclo completo de emisión. Ver el
    [CHANGELOG](https://github.com/josecuev/pysifen/blob/master/CHANGELOG.md)
    para lo que ya está disponible.

| Componente | Estado |
|---|---|
| Código de Control (CDC) y dígito verificador | Listo |
| Código de seguridad `dCodSeg` | Listo |
| Código QR del KuDE | Listo |
| Tablas de códigos del Manual Técnico | Parcial |
| Armado del XML del DE | En curso |
| Firma XMLDSig | En curso |
| Lectura de certificados y prestadores cualificados | Listo |
| Cadena de confianza y revocación | En curso |
| Web services (recepción, lote, consultas, eventos) | Pendiente |

## Qué implementa

La implementación sigue el **Manual Técnico v150** con las **Notas Técnicas 001
a 027** aplicadas de forma acumulativa. Cada módulo indica en su docstring el
apartado del manual que implementa, de modo que se pueda auditar contra el
documento oficial.

El detalle de lo que está vigente, con fechas y citas, está en
[Normativa vigente](normativa-vigente.md).

## Ejemplo

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
print(cdc.formateado)  # en grupos de cuatro, como va en el KuDE
```

## Principios

**La fuente de verdad es el manual oficial.** Nada se implementa de oído. Cuando
el manual no dice algo, se documenta la decisión con la cita de lo que sí dice.

**La clave privada es sagrada.** Toda firma pasa por un puerto abstracto y la
librería no expone ninguna forma de exportar material de clave. Ver
[Custodia del certificado](seguridad/custodia.md).

**Los prestadores son intercambiables.** El soporte de prestadores cualificados
es un punto de extensión declarado por *entry points*: agregar uno nuevo no
requiere tocar el núcleo.

**Los nombres del SIFEN se respetan.** Los campos se llaman `dCodSeg`,
`gCamFuFD`, `iTipEmi` como en el manual. No se traducen ni se normalizan, para
que buscar un campo en el manual y en el código dé lo mismo.

## Licencia

MIT.
