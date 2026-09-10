# Registro de cambios

Todos los cambios notables de este proyecto se documentan acá.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y
el versionado sigue [SemVer](https://semver.org/lang/es/).

## [No publicado]

### Agregado

- Código de Control (CDC): armado, descomposición y dígito verificador por
  módulo 11. Verificado contra el ejemplo del apartado 10.1 del Manual Técnico
  v150.
- Generación y validación del código de seguridad `dCodSeg` con generador
  aleatorio criptográfico, según el apartado 10.3.
- Código QR del KuDE según el apartado 13.8, con la conversión a hexadecimal de
  la fecha de emisión y del `DigestValue`, y el hash SHA-256 que incorpora el
  CSC sin exponerlo en la URL.
- Envoltorio `Secreto` para material sensible: no aparece en `repr`, `str` ni
  interpolación, y se niega a serializarse.
- Tablas de códigos `Ambiente`, `TipoDocumento`, `TipoEmision` y
  `TipoContribuyente` con sus descripciones normadas.
- Documentación pública con MkDocs Material y referencia de API generada desde
  el código.
- Revisión de la normativa vigente contra fuentes primarias, con fechas y citas.

### Cambiado

- Migración a disposición `src/`.
- Migración de los metadatos del paquete a PEP 621.
- El núcleo dejó de depender de FastAPI; el microservicio pasó a ser el extra
  opcional `pysifen[api]`.

## [0.1.0] — 2023

### Agregado

- Reserva del nombre en PyPI.

[No publicado]: https://github.com/josecuev/pysifen/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/josecuev/pysifen/releases/tag/v0.1.0
