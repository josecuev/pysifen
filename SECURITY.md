# Política de seguridad

## Versiones soportadas

El proyecto está en desarrollo. Sólo se da soporte a la última versión
publicada.

| Versión | Soportada |
|---|---|
| 0.2.x | Sí |
| 0.1.x | No |

## Cómo reportar una vulnerabilidad

**No abras un issue público.**

Reportá la vulnerabilidad de forma privada por el
[formulario de asesorías de seguridad de GitHub](https://github.com/josecuev/pysifen/security/advisories/new).

Incluí, en lo posible:

- Descripción del problema y de su impacto.
- Pasos para reproducirlo.
- Versión afectada.
- Cualquier mitigación que se te ocurra.

Vas a recibir acuse de recibo. Una vez confirmada, se coordina la publicación
de la corrección junto con el aviso.

## Qué se considera vulnerabilidad

Este proyecto maneja el certificado tributario del contribuyente, que es la
firma de la empresa. Se tratan como vulnerabilidad, entre otros:

- Cualquier camino por el que material de clave privada salga de la librería.
- Cualquier filtración de la contraseña del keystore o del Código de Seguridad
  del Contribuyente hacia logs, mensajes de error, trazas o serializaciones.
- Que el CSC llegue a la URL del código QR.
- Fallas en la validación de la firma o de la cadena de confianza que permitan
  aceptar un documento no auténtico.
- Aceptar un certificado revocado o vencido.
- Degradación de la autenticación mutua TLS contra los servicios del SIFEN.

## Qué no es una vulnerabilidad de este proyecto

- Configuraciones inseguras hechas de forma explícita por el usuario, como
  habilitar a mano el uso de un `.p12` en texto plano. La librería lo desalienta
  y lo advierte, pero la decisión es de quien opera.
- Problemas de los servicios de la DNIT, que corresponden a la DNIT.
- Vulnerabilidades de dependencias de terceros; reportalas río arriba y avisanos
  para fijar la versión.

## Buenas prácticas

La guía de custodia de la clave está en
[docs/seguridad/custodia.md](docs/seguridad/custodia.md), con la lista de
control previa a producción.
