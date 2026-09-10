# 0002 · Qué canonicalización usa el `SignedInfo`

**Fecha**: 10 de setiembre de 2026
**Estado**: aceptada
**Reemplaza**: la lectura literal del ejemplo del apartado 7.6

## Contexto

El apartado 7.6 del Manual Técnico v150 trae un ejemplo de firma que muestra
esto:

```xml
<CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
...
<Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>
<Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
```

O sea: canonicalización **inclusiva** para el `SignedInfo` y **exclusiva** para
la `Reference`. La implementación inicial siguió el ejemplo al pie de la letra.

Después se pudo examinar un **documento tributario electrónico real**, emitido
por un contribuyente y firmado con un certificado cualificado de DOCUMENTA S.A.
Ese documento declara:

```xml
<CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
```

Exclusiva en los dos lugares. Y su `DigestValue` **sólo cierra con
canonicalización exclusiva**: recalculado con la inclusiva, no coincide.

## Decisión

**El valor por omisión del `CanonicalizationMethod` es el exclusivo**
(`http://www.w3.org/2001/10/xml-exc-c14n#`).

El del manual queda disponible pasando `canonicalizacion=C14N_INCLUSIVO` a
`firmar_documento` o a `firmar_elemento`.

El criterio general es: cuando el manual y un documento realmente aceptado por
el SIFEN se contradicen, **manda el documento aceptado**, y la discrepancia se
documenta. Un manual con un ejemplo desactualizado sigue siendo la referencia
para todo lo demás; lo que no puede es hacer que se emita algo que se rechaza.

## Por qué la firma igual verifica en los dos casos

El algoritmo se **declara** dentro de la propia firma, así que quien valida
aplica el que el documento dice. Las dos variantes producen firmas internamente
consistentes y verificables. La diferencia no es de corrección criptográfica
sino de compatibilidad con lo que el receptor espera.

Por eso el parámetro existe: si en algún caso el SIFEN exigiera el valor del
manual, se cambia con un argumento y sin tocar el resto.

## Consecuencias

**A favor.** El valor por omisión es el que hay evidencia empírica de que
funciona en producción, no el que salió de un ejemplo de 2019.

**En contra.** Queda una divergencia declarada respecto de la letra del manual.
Está documentada acá y en el docstring del módulo de firma, para que no parezca
un descuido.

**Verificación.** El documento real se verificó de tres maneras: el
`DigestValue` recalculado coincide con la canonicalización exclusiva y no con la
inclusiva; la firma completa valida con `signxml`, una implementación
independiente; y el certificado se leyó con nuestra propia capa PKI, que extrajo
el RUC del `SubjectAlternativeName`, identificó al prestador y no encontró
problemas de aptitud.

> El documento usado como referencia contiene datos de contribuyentes reales y
> **no se incorpora al repositorio**. Las pruebas usan documentos sintéticos con
> la misma estructura.
