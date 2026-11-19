# ISCLA QUIZ · Despliegue e integración

Esta versión incluye servidor Python y SQLite para una instancia institucional y un panel docente compartido. No requiere servicios externos para generar los QR. Conectá los celulares a la misma instancia para compartir sala, respuestas y ranking.

## Configuración del servicio

| Variable | Uso |
| --- | --- |
| `ISCLA_CODIGO_DOCENTE` | Código institucional de registro de 8 a 128 caracteres. En hosting guardalo como variable secreta. En local se solicita en consola si no está configurado. No es la contraseña de los docentes. |
| `ISCLA_URL_PUBLICA` | Origen público completo sin ruta, por ejemplo `https://quiz.ejemplo.edu.ar`. Configuralo al desplegar para que los QR abran la dirección correcta y las sesiones docentes usen cookies Secure. |
| `PORT` | Puerto HTTP interno. Predeterminado 8000. |
| `ISCLA_HOST` | Interfaz de escucha. Predeterminada `0.0.0.0` para permitir el acceso desde el aula. |
| `ISCLA_DB` | Ruta del archivo SQLite. En local `datos/iscla.sqlite3`. En Docker `/datos/iscla.sqlite3`. |

Ejecutá una sola instancia con el SQLite en un volumen persistente. Para publicación, usá HTTPS con un proxy inverso o la TLS gestionada por el hosting. No des acceso de Internet directo al proceso HTTP local. Podés cambiar el código de registro antes de reiniciar el servicio para renovar las invitaciones. Eso no modifica las cuentas existentes. Conservá el volumen SQLite al actualizar. Las cuentas y las sesiones usan tablas nuevas, sin borrar cuestionarios ni partidas. Los accesos anteriores con clave única deben pasar por el registro una vez. Si el despliegue ya usaba `ISCLA_CLAVE_DOCENTE`, sustituila por `ISCLA_CODIGO_DOCENTE` con un nuevo valor. Usá aliases para la actividad y definí cuánto tiempo vas a conservar los datos del curso.

## API

El adaptador `static/js/servicio.js` comunica los HTML de `templates/` con la API. Todos los POST usan JSON con el encabezado `X-ISCLA-Request: 1`. El panel recibe la sesión en una cookie HttpOnly. El registro valida el código institucional y guarda un hash con sal de cada contraseña. El panel y el banco de preguntas siguen compartidos entre los docentes autorizados. Cada jugador tiene un token independiente guardado por pestaña. Los estudiantes no reciben respuestas correctas antes de registrar su respuesta.

| Operación | Ruta |
| --- | --- |
| Registro, sesión y panel | `POST /api/registro`, `GET /api/session`, `POST /api/login`, `POST /api/logout`, `GET /api/panel` |
| Editar el banco | `POST /api/cuestionarios`, `POST /api/preguntas`, `POST /api/preguntas/eliminar` |
| Crear e ingresar | `POST /api/partidas`, `POST /api/unirse` |
| Estado de sala | `GET /api/partidas/{codigo}` y `GET /api/partidas/{codigo}/docente` |
| Invitación QR | `GET /api/partidas/{codigo}/qr.svg`, disponible para el docente |
| Manejo de partida | `POST /api/partidas/{codigo}/iniciar`, `/cerrar` y `/salir` |
| Jugar | `POST /api/partidas/{codigo}/pregunta` entrega la pregunta y el tiempo restante. `POST /api/partidas/{codigo}/responder` registra la opción o la omisión. El servidor valida los 15 segundos por pregunta y por jugador. La explicación se entrega después de registrar la respuesta. |
| Diagnóstico | `GET /api/health` |

El frontend consulta el estado aproximadamente cada 1,4 segundos mientras la pestaña está visible. Las salas aceptan hasta 120 participantes y usan una copia del cuestionario al crearse. Las partidas se cierran al completarse todas las respuestas o cuando el docente las cierra. En los empates se comparte la posición y se ordenan los nombres alfabéticamente dentro de la misma posición.
