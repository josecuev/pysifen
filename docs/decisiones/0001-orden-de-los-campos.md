# 0001 · De dónde sale el orden de los campos del XML

**Fecha**: 10 de setiembre de 2026
**Estado**: superada en parte por el hallazgo del XSD de producción
(ver [0003](0003-esquemas-oficiales.md))

## Contexto

El XML del documento electrónico se valida contra un esquema, y en un esquema
con `xs:sequence` el **orden de los elementos importa**: un documento con los
campos correctos en el orden equivocado se rechaza igual que uno al que le
faltan campos.

El orden debería salir del XSD oficial. Pero el paquete `Estructura_DE xsd.rar`
que publica el portal de la DNIT es de 2018 y describe una estructura que ya no
existe: tiene nodos `gCiODE`, `gDTim` y `gCamOC` que no aparecen en el Manual
Técnico v150 vigente. No sirve como fuente.

Queda entonces la tabla de campos del propio manual, que sí es la fuente
vigente. El problema práctico es que el manual se publica en PDF con las tablas
maquetadas en columnas, y al extraer el texto las columnas se entrelazan. Por
ejemplo, en el grupo del timbrado la columna de identificadores sale
`C005, C006, C007, C010, C008, C009` mientras la columna de campos sale
`dEst, dPunExp, dNumDoc, dSerieNum, dFeIniT, dFeFinT`.

## Decisión

**El orden de declaración de los campos en el modelo es el orden de la columna
"Campo" de la tabla del manual, no el orden numérico de los identificadores.**

Los identificadores no son consecutivos dentro de una secuencia porque las notas
técnicas agregan campos al medio de estructuras ya publicadas: `dSerieNum` lleva
el identificador C010 pero se ubica entre C007 y C008. El número dice *cuándo se
creó el campo*; la posición en la tabla dice *dónde va en el XML*. Ordenar por
número produciría un XML que se rechaza.

Además:

1. Cada campo lleva su identificador del manual en la metadata del modelo, de
   modo que la correspondencia quede explícita y auditable.
2. Los grupos cuyo orden no se pudo leer sin ambigüedad **no se implementan**
   hasta poder confirmarlos. No se completa por inferencia.
3. Antes de emitir en producción hay que contrastar contra un documento validado
   por el ambiente de test de la DNIT.

## Consecuencias

**A favor.** El orden queda trazable a una fuente oficial concreta y citable. La
metadata permite generar la matriz de trazabilidad desde el código en vez de
mantenerla a mano en un documento que se desactualiza.

**En contra.** El avance es más lento: cada grupo hay que leerlo con cuidado en
vez de transcribirlo de corrido. Y queda una incertidumbre residual hasta el
primer documento aceptado por el ambiente de test.

**Riesgo asumido y cómo se cierra.** La incertidumbre se elimina del todo cuando
se disponga de un certificado habilitado y se transmita un documento al ambiente
de test: la respuesta del SIFEN es la confirmación definitiva. Hasta entonces,
el estado de cada grupo se declara en el README.
