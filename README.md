ISCLA QUIZ · ISCLA 0708
Juego de preguntas para el aula. El docente crea una partida por materia y comparte un QR o un código. Cada estudiante entra desde su propio navegador con un alias. El docente inicia la partida y sigue la clasificación en vivo. Cada respuesta correcta suma 100 puntos. Las incorrectas y omitidas suman 0.

¿Vas a continuar el desarrollo? Empezá por la guía para reutilizar el frontend. Ahí están las pantallas listas, los archivos que podés editar y el punto de conexión con el backend.

Para una clase en el aula
Descomprimí este ZIP en la computadora del docente. Necesitás Python 3.10 o posterior. No hay paquetes que instalar.
En Windows, abrí Iniciar-ISCLA-QUIZ.cmd. En macOS o Linux, abrí una terminal en la carpeta y ejecutá python3 servidor/app.py.
En la consola, definí un código de registro docente de al menos 8 caracteres. Compartilo solo con los profesores que vayan a usar el panel. No es la contraseña de una cuenta ni el código de una partida. No cierres esa ventana durante la clase.
Abrí http://localhost:8000 en la computadora docente. Entrá a Panel docente → Crear cuenta docente. Si es tu primera vez, registrá tu nombre, correo y contraseña personal con el código que definiste en la consola. Después, usá tu correo y contraseña para ingresar. Dentro del panel, abrí Partidas.
Elegí Cultura general para jugar con 20 preguntas de películas, música, videojuegos, comidas, fútbol y astrología. Si editaste el cuestionario anterior, el nuevo aparece como Cultura general · Desafío y tus cambios se conservan. También siguen disponibles los demás cuestionarios. Elegí cuántas preguntas querés usar.
Creá la partida y abrí Abrir sala docente. Proyectá el QR o tocá Ampliar QR. Cada estudiante abre la cámara de su celular, escanea y escribe un alias.
Cerrá la ampliación para ver la lista de participantes. Tocá Iniciar partida. El ranking se actualiza mientras responden. La partida se cierra cuando todos terminan, o podés cerrarla manualmente para conservar los puntajes ya registrados.
Cada estudiante tiene 15 segundos por pregunta desde que la abre. Si no confirma una opción a tiempo, se registra como omitida. La devolución se muestra 7 segundos y el juego avanza automáticamente a la siguiente pregunta o al ranking. Recargar la pregunta no reinicia el cronómetro de respuesta. Si la pregunta tiene una explicación, se muestra junto con la opción correcta.
Las cuentas docentes son individuales y los cuestionarios y las partidas siguen en el panel compartido de la institución. El registro no envía correos ni pide que los estudiantes creen una cuenta.

Red y alternativas al QR
En modo local, conectá los celulares y la PC a la misma red Wi-Fi. La red debe permitir la comunicación entre dispositivos. Probá el QR con un teléfono antes de la clase.
Si la red escolar bloquea el acceso o la PC tiene más de una interfaz, probá abrir el sitio docente desde la dirección IP de la PC en esa red (por ejemplo, http://192.168.1.20:8000, sustituyendo la IP por la real). Creá la partida desde ahí. También podés fijar la dirección con ISCLA_URL_PUBLICA antes de arrancar.
Si Windows pide permiso de red, autorizá Python en la red privada de confianza que vayas a usar. Si el QR no escanea, compartí el enlace de ingreso o abrí la web por su dirección y escribí el código de seis caracteres.
Si la red no permite conectar equipos, usá una instancia publicada con HTTPS. Para probar el flujo desde un solo equipo, abrí el panel en una pestaña y el ingreso de estudiante en otra. La segunda puede usar la misma dirección y escribir el código manualmente.
Archivos del proyecto
Requisito	Archivo	Función
F01	templates/inicio.html	Portada y selección de rol
F02	templates/acceso.html	Ingreso con código, desde QR o manual, y alias
F03	templates/docente.html	Inicio de sesión y creación de cuentas docentes
F04	templates/admin.html	Cuestionarios, banco editable e historial
F05	templates/partida.html	Elegir materia, cantidad y generar invitación
F06	templates/sala.html	Sala de espera, QR proyectable y control docente
F07	templates/jugar.html	Preguntas y registro de respuestas
F08	templates/resultado.html	Devolución y avance
F09	templates/ranking.html	Clasificación provisional y final
static/ contiene el frontend y el logo institucional. servidor/ contiene la API, SQLite y el banco inicial. La aplicación crea los datos locales al iniciar.
docs/INTEGRACION.md describe cómo desplegarla y cómo se conecta el frontend a la API.
