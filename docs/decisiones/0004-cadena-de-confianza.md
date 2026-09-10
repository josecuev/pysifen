# 0004 — La cadena de confianza se valida contra la Lista oficial

**Estado**: aceptada · **Fecha**: 2026-09-10

## Contexto

Hasta la 0.3.0, para decir de qué prestador venía un certificado la librería
comparaba el nombre del emisor contra una lista escrita a mano. Un test dejaba
constancia de que eso no probaba nada:

```python
def test_identificar_al_prestador_no_prueba_nada(firmante):
    # El certificado de prueba es AUTOFIRMADO y aun así se lo identifica
    # como DOCUMENTA, porque así dice su campo de emisor.
    assert verificar_documento(...).prestador == "DOCUMENTA S.A."
```

El campo de emisor de un certificado es **texto libre**. Cualquiera puede
generar un certificado autofirmado que diga `CN=CA-DOCUMENTA S.A.` en treinta
segundos y sin que DOCUMENTA intervenga. La librería lo aceptaba y lo informaba
como confiable.

Lo que no se puede falsificar es la **firma de la autoridad** sobre el
certificado. Comprobarla exige tener el certificado de esa autoridad, de una
fuente que no sea el documento que se está verificando.

## De dónde salen las anclas

La Ley 4017/2010 de validez jurídica de la firma digital pone al **Ministerio de
Industria y Comercio** como administrador de la Autoridad Certificadora Raíz del
Paraguay, y obliga a los prestadores cualificados a publicar su cadena.

El MIC publica esa información en un solo lugar y en un formato estándar: la
**Lista de Confianza (TSL)** en formato ETSI TS 119 612, en
<https://www.acraiz.gov.py/tsl/tsl_Py.xml>. Trae, por cada prestador, los
certificados de sus autoridades certificadoras y el **estado de cada servicio**.

Se evaluaron tres opciones:

| Opción | Por qué no |
|---|---|
| Bajar la cadena de cada prestador de su propio sitio | Nueve sitios, nueve formatos, nueve momentos de actualización. Y cada sitio es una fuente distinta que hay que autenticar por separado |
| Confiar en el almacén de certificados del sistema | La Raíz del Paraguay no está en los almacenes de Windows, macOS ni en `ca-certificates`. Y si estuviera, aceptaría además cientos de raíces ajenas al SIFEN |
| **La Lista de Confianza del MIC** | Una sola fuente, oficial, estándar, con el estado de cada servicio |

## Decisión

**Se incluye una copia de la Lista de Confianza en el paquete y se valida la
cadena contra ella, comprobando la firma de cada eslabón.**

En cada paso se llama a `verify_directly_issued_by()`: el certificado tiene que
estar **realmente firmado** por el siguiente, no llamarse parecido. Se sigue
hasta llegar a un certificado autofirmado que la lista reconozca como raíz
nacional.

El prestador que se informa sale de la lista, no del certificado. Es el dato
autoritativo.

### Sólo la jerarquía tributaria

La lista trae más de una jerarquía, y no todas firman documentos tributarios:

| Servicio | Raíz | Qué es | ¿Sirve acá? |
|---|---|---|---|
| `QC` | Autoridad Certificadora Raíz del Paraguay | Certificados cualificados de firma | **Sí** |
| `QTST` | la propia del prestador | Sellos de tiempo | No: sellan, no firman documentos |
| `PKC` | AC RAIZ MITIC | Firma de funcionarios públicos | No: otra raíz y otro propósito |

Aceptar las tres sería aceptar de más. Un certificado de funcionario público
encadena perfecto contra su raíz, y eso no habilita a nadie a facturar. Por eso
`SERVICIOS_TRIBUTARIOS` acota las anclas por omisión, y el parámetro `servicios`
permite ampliarlas a propósito, dejándolo escrito en el código de quien lo hace.

### La vigencia se evalúa a la fecha de la firma

Una autoridad que venció el mes pasado no invalida lo que firmó estando
vigente. Es el mismo criterio del apartado 7.8 del Manual Técnico para el
certificado del emisor.

### La copia se vigila

`scripts/verificar_lista_de_confianza.py` compara la copia incluida contra la
publicada —SHA-256 y número de secuencia— y avisa cuando está por caducar. Corre
semanalmente en el workflow de vigilancia normativa.

Una copia desactualizada falla de las dos maneras: si el MIC habilitó a un
prestador nuevo, sus documentos se rechazan sin culpa; si le retiró la
habilitación a otro, se aceptan cuando no corresponde. La segunda es la grave.

## Consecuencias

**A favor:**

- `confiable` pasa a significar **auténtico**. Antes significaba "las
  comprobaciones que sé hacer pasaron".
- Un certificado autofirmado que dice ser de DOCUMENTA se rechaza. Hay un test
  que lo prueba.
- Cuando el MIC habilita a un prestador nuevo, alcanza con actualizar la copia
  de la lista: no se toca código.
- Que el estado del servicio venga de la lista significa que una habilitación
  retirada se refleja sola.

**En contra:**

- Un archivo de 170 KB más en el paquete.
- La copia caduca. Sin la vigilancia automática, esto se pudre en silencio, que
  es la peor manera de pudrirse.
- Sigue faltando la **revocación** del certificado del emisor, que necesita red
  y va aparte. Un certificado revocado con cadena válida hoy se informa como
  confiable.

## Lo que esto no prueba

Que la cadena cierre no dice nada sobre si el documento fue aprobado por el
SIFEN. Son dos cosas distintas: la firma prueba **quién lo emitió y que no fue
alterado**; la aprobación es un trámite ante la DNIT que se consulta aparte.

## Fuentes

- Ley 4017/2010 y su Decreto reglamentario 7369/2011
- Lista de Confianza del Paraguay: <https://www.acraiz.gov.py/tsl/tsl_Py.xml>
- Prestadores habilitados: <https://www.mic.gov.py/> (Firma Digital)
- ETSI TS 119 612 — *Trusted Lists*
- Manual Técnico SIFEN v150, apartado 7.8
