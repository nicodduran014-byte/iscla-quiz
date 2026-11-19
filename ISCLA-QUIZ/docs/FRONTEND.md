# ISCLA QUIZ | Guía para reutilizar el frontend

Las pantallas del docente y del estudiante ya están conectadas y se pueden usar como base para terminar la app. El frontend está hecho en HTML, CSS y JavaScript sin framework ni compilación. Podés mantener el servidor incluido o conectar las mismas pantallas a otro backend, como el de Flask propuesto en el diseño original.

## 1. Probá lo que ya está hecho

Desde la carpeta principal, iniciá el servidor incluido. Usa Python 3.10 o posterior y no requiere instalar paquetes.

**Windows (CMD)**

```cmd
py -3 servidor\app.py
```

**macOS o Linux**

```bash
python3 servidor/app.py
```

Si el servidor te pide un código docente, definí uno propio de al menos ocho caracteres para la prueba. La consola no muestra los caracteres mientras los escribís. Después abrí [la página de inicio](http://127.0.0.1:8000/) en el navegador. No abras los HTML con doble clic ni uses solo Live Server para probar una partida, porque las pantallas necesitan las rutas `/api`.

1. Creá una cuenta docente de prueba con el código que definiste, entrá al panel y generá una partida de dos preguntas de **Cultura general**.
2. En otra pestaña, elegí **Ingresar a una partida** desde la página de inicio. Entrá con el código de la partida y un alias. Si probás desde un celular con el QR, conectalo a la misma red que la PC.
3. Volvé a la sala docente e iniciá la partida. Probá una respuesta, dejá vencer el tiempo de la otra y verificá que aparezcan la devolución y el ranking. El recorrido actual usa 15 segundos para responder y 7 segundos de devolución antes de avanzar.

## 2. Ubicá qué archivo tocar

| Si querés cambiar… | Trabajá en… |
| --- | --- |
| Portada e ingreso del estudiante | `templates/inicio.html`, `templates/acceso.html` |
| Acceso docente, cuestionarios e historial | `templates/docente.html`, `templates/admin.html` |
| Creación de partidas y sala de espera | `templates/partida.html`, `templates/sala.html` |
| Pregunta, devolución y ranking | `templates/jugar.html`, `templates/resultado.html`, `templates/ranking.html` |
| Estilos base, diseño adaptable e imágenes | `static/css/estilo.css`, `static/css/interfaz.css`, `static/img/` |
| Clics, formularios, navegación y actualización de pantalla | `static/js/juego.js` |
| Solicitudes al backend, formatos de respuesta y manejo de errores de la API | `static/js/servicio.js` |

Cada pantalla tiene un atributo `data-page` en el `<body>` que `juego.js` usa para elegir qué función ejecutar. Si cambiás un `id`, un `name` de formulario o el `data-page`, buscá primero dónde se usa en JavaScript y actualizá las referencias juntas. Para retocar colores, textos o tamaños, normalmente alcanza con editar el HTML y el CSS.

## 3. Conectá el backend sin rehacer las pantallas

El recorrido del código es `templates/*.html` → `juego.js` → `servicio.js` → `/api/...`. Las páginas no se conectan directamente a SQLite. `juego.js` llama a las funciones de `window.ISCLA`, que están definidas en `servicio.js`.

- **Si continuás con el servidor incluido**, trabajá sobre `servidor/app.py` y mantené `servicio.js` como punto de conexión.
- **Si el backend nuevo mantiene las rutas y respuestas actuales**, serví los HTML en `/templates/`, los recursos en `/static/` y la API en `/api/`, todos desde el mismo origen. Podés mantener las pantallas y ambos archivos JavaScript.
- **Si el backend nuevo usa otras rutas o nombres de campos**, adaptalos en `servicio.js`. Mantené las funciones que ya llama `juego.js`, como `joinRoom`, `getRoom`, `startRoom`, `openQuestion` y `submitAnswer`. Así podés conservar la interfaz y concentrar los cambios de integración en un solo archivo.

En la integración, comprobá los permisos del docente y el acceso de cada jugador, y dejá en el servidor la validación de respuestas, el plazo y el cálculo del puntaje. El navegador muestra el estado y envía las acciones. La [guía de integración](INTEGRACION.md#api) enumera las rutas y explica qué envía cada rol.

## 4. Punto de partida para terminarla

- Elegí una pantalla o un flujo a la vez. Si vas a cambiar el backend, conectá primero **acceso → sala → pregunta → devolución → ranking** con una partida corta antes de seguir con el resto.
- Si solo necesitás cambiar preguntas, usá el editor docente. `servidor/preguntas.json` es el banco inicial y editarlo no reemplaza automáticamente todos los cuestionarios que ya se guardaron en SQLite.
- Al terminar un cambio, probalo en PC y en celular. Para confirmar que sigue funcionando la partida completa, ejecutá `py -3 -m unittest discover -s tests -v` en Windows o `python3 -m unittest discover -s tests -v` en macOS o Linux. Si tenés Node.js, `node --test tests/test_feedback.cjs` comprueba la cuenta regresiva de devolución y el avance automático.
- Podés trabajar con una base local nueva y un código docente de prueba. No necesitás copiar la base real ni usar una contraseña institucional para modificar el frontend.
