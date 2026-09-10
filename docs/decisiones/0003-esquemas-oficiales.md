# 0003 · Los esquemas oficiales se incluyen en el paquete

**Fecha**: 10 de setiembre de 2026
**Estado**: aceptada
**Supera en parte**: [0001 · De dónde sale el orden de los campos](0001-orden-de-los-campos.md)

## Contexto

Hasta esta decisión, el proyecto trabajaba sin XSD. Se creía que no había uno
vigente y accesible, porque:

- El paquete `Estructura_DE xsd.rar` del portal de documentación técnica es de
  2018 y describe nodos que ya no existen.
- Los WSDL de los servicios web devuelven HTTP 302 sin certificado cliente,
  porque están detrás del TLS mutuo del apartado 7.9.

El orden de los campos se estaba derivando de documentos reales, con la
incertidumbre que eso deja.

Resultó que **sí hay un XSD publicado y accesible**, en
`https://ekuatia.set.gov.py/sifen/xsd/`, que es exactamente adonde apunta el
`schemaLocation` de todos los documentos electrónicos. Son once archivos
encadenados por `xs:include`.

### La verificación

Se probaron dos paquetes distintos contra cinco documentos tributarios reales,
emitidos entre mayo y setiembre de 2026 por cinco contribuyentes distintos, cada
uno con su propio proveedor de software:

| Paquete | Resultado |
|---|---|
| `20190910_XSD_v150` (publicación original, en repositorios públicos) | **Los 5 fallan** |
| `ekuatia.set.gov.py/sifen/xsd/` (servidor en vivo) | **Los 5 validan** |

Los errores del paquete de 2019 son informativos: rechaza `dBasExe` (que agregó
la NT-013), el grupo `gOblAfe`, y el valor `IVA - Renta` de `dDesTImp`. O sea
que el paquete de 2019 es la publicación original del v150, **sin las enmiendas
de las notas técnicas**, mientras que el del servidor las tiene aplicadas.

## Decisión

**Los esquemas del servidor en vivo se incluyen en el paquete**, en
`src/pysifen/esquemas/`, y son la fuente de verdad estructural del proyecto.

1. **Las copias son byte a byte idénticas** a las del servidor. No se editan,
   ni siquiera para "arreglar" los `xs:include` con URL absoluta: esos se
   resuelven en código, con un resolver de lxml que los redirige a las copias
   locales. Así validar no necesita red y las copias siguen siendo comparables
   con el original.
2. **Hay un manifiesto** `checksums.json` con el SHA-256 de cada archivo. Un
   test verifica que las copias no fueron modificadas, y el script
   `scripts/verificar_esquemas.py` las compara contra el servidor.
3. **Cuando el manual y el XSD se contradigan, gana el XSD.** Es contra lo que
   el SIFEN valida de verdad. La divergencia se documenta.
4. **La librería valida antes de transmitir**, con
   [`validar_documento`][pysifen.validacion.validar_documento]. Un rechazo
   remoto, con su mensaje escueto y su viaje de ida y vuelta, se convierte en un
   error local con la línea exacta.

## Consecuencias

**A favor.** Se acabó la inferencia: hay estructura, tipos, longitudes,
enumeraciones y obligatoriedad para **todos** los tipos de documento, incluidos
los que no se podían modelar por falta de ejemplos —autofactura, notas de
crédito y débito, nota de remisión, documentos asociados, operaciones a crédito,
transporte y los grupos de sectores especiales— y para todos los eventos.

**En contra.** El paquete crece unos 340 KB. Es un costo aceptable para poder
validar sin red.

**Riesgo y cómo se cubre.** Un esquema que cambie en el servidor y no acá
produciría documentos rechazados. Por eso el workflow de vigilancia compara los
checksums todas las semanas y abre un issue si algo se movió. Ver
[Vigilancia normativa](../mantenimiento/vigilancia-normativa.md).

**Sobre la procedencia.** Son documentos regulatorios publicados por la DNIT
para que los integradores los usen. Se incluyen sin modificar y con su origen y
fecha declarados en `esquemas/checksums.json`.
