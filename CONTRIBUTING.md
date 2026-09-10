# Cómo contribuir

Gracias por el interés. Este documento explica cómo trabajar en el proyecto.

## Antes de escribir código

Para un cambio de comportamiento, abrí primero un *issue* describiendo el caso.
Para una corrección evidente o una mejora de documentación, mandá el *pull
request* directamente.

## Entorno

```bash
git clone https://github.com/josecuev/pysifen.git
cd pysifen
python -m venv .venv
source .venv/bin/activate      # en Windows: .venv\Scripts\activate
pip install -e .
pip install pytest pytest-cov mypy ruff
```

## Verificación

Estos cuatro comandos son los mismos que corre integración continua. Tienen que
pasar antes de mandar el *pull request*:

```bash
ruff check .
ruff format --check .
mypy
pytest
```

## La regla que importa

> **La fuente de verdad es el Manual Técnico oficial de la DNIT.**

Concretamente:

- La referencia vigente es el **Manual Técnico v150** con las **Notas Técnicas
  001 a 027** aplicadas de forma acumulativa.
- El paquete de XSD publicado en el portal **está desactualizado** (es de 2018) y
  no se usa como referencia.
- Todo módulo que implemente una regla del manual cita el apartado en su
  docstring: `"""Implementa el apartado 10.3 del Manual Técnico SIFEN v150."""`
- Todo cambio de comportamiento cita en el mensaje de commit o en el *pull
  request* el apartado o la nota técnica que lo justifica.
- Cuando el manual no dice algo, se documenta la decisión en `docs/decisiones/`
  con la cita de lo que sí dice. **No se inventan campos ni validaciones.**

Los detalles con fechas están en
[docs/normativa-vigente.md](docs/normativa-vigente.md).

## Convenciones

**Nombres.** Los símbolos van en inglés, salvo los nombres de campo del SIFEN,
que se escriben exactamente como en el manual: `dCodSeg`, `gCamFuFD`,
`iTipEmi`. No se traducen ni se normalizan, para que buscar un campo en el
manual y en el código dé lo mismo.

**Idioma.** Documentación, docstrings y mensajes de error en castellano.

**Tipado.** `mypy --strict` sin excepciones. Si hace falta un `type: ignore`,
lleva el código específico del error y un comentario que explique por qué.

**Tests.** Todo aporte trae tests. Cuando el manual publica un ejemplo, ese
ejemplo es el caso de prueba: así la implementación se valida contra el
documento oficial y no contra sí misma. La cobertura no baja del umbral
configurado.

Los tests que dependen de red o de un certificado real van marcados:

```python
@pytest.mark.red
@pytest.mark.certificado
```

**Commits.** En castellano, en imperativo, sin emojis. Una línea de asunto
breve y, si hace falta, un cuerpo que explique el porqué:

```
Agregar validación D208c del receptor innominado

La NT-024 del 17/12/2024 prohíbe el receptor innominado cuando el total
en guaraníes supera 7.000.000, salvo muestras médicas.
```

## Seguridad

**Nunca** subas al repositorio un certificado real, una clave privada, una
contraseña de keystore ni un Código de Seguridad del Contribuyente. Tampoco en
tests, fixtures ni ejemplos de documentación. Para los tests se usan
certificados autofirmados generados al vuelo.

Si encontrás una vulnerabilidad, no abras un *issue* público: seguí lo que
indica [SECURITY.md](SECURITY.md).
