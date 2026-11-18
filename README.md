# CUPRIVISION · Monitor de seguridad

Aplicación web local para observar las cuatro dimensiones de actos inseguros de la tesis. Incluye una interfaz privada accesible desde el navegador y un motor Python para ejecutar los modelos en tu computadora.

## Inicio en Windows

1. Instala Python 3.11 desde https://www.python.org/downloads/.
2. Extrae TODO el ZIP en una carpeta, por ejemplo Documentos/CUPRIVISION.
3. Ejecuta INICIAR_WINDOWS.bat. La primera ejecución instala dependencias y necesita internet. Mantén abierta esa consola.
4. Abre http://127.0.0.1:8765 en Chrome o Edge.
5. Pulsa Estado y modelos → Cargar / reintentar modelos. Espera a que se informe su disponibilidad; una descarga fallida se muestra explícitamente.
6. Carga un vídeo o concede acceso a tu webcam. Para cámaras IP, introduce su URL RTSP en IP / RTSP. El equipo donde se ejecuta Python debe tener acceso a la red de la cámara.
7. Configura la tarea, el responsable, el EPP requerido y los criterios revisados. Los límites en cero están desactivados: no representan valores recomendados para tu investigación.
8. Dibuja zonas sobre la imagen y confirma el encuadre. Para D4, calibra un rectángulo real del suelo con cuatro esquinas y un quinto punto independiente, e introduce separación, umbral de movimiento y radio envolvente conservador de los equipos.
9. Inicia el análisis. Los avisos se guardan como pendientes. Deténlo para revisar, asignar una dimensión principal y confirmar, descartar o marcar como indeterminado/duplicado.
10. Exporta el proyecto JSON para conservar eventos y capturas. CSV sirve para análisis posterior; filtra estado=confirmed para contar actos confirmados.

Instalación manual:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe local\server.py
```

La interfaz descargada es la misma que la publicada. La página privada permite cargar vídeo, revisar y exportar sin Python; para inferencia y RTSP necesita el motor local. Algunos navegadores bloquean el acceso de una página HTTPS a servicios locales. En ese caso abre directamente http://127.0.0.1:8765: interfaz y motor usan el mismo origen.

## Dimensiones y alcance

- D1: **Ausencia o uso inadecuado de equipos de protección personal**. Casco, chaleco, protección ocular y guantes según requisitos de tarea. Se utilizan clases explícitas de presencia/ausencia/uso incorrecto del modelo. La ausencia de una detección no demuestra ausencia de EPP; una clase positiva no acredita colocación correcta. Si no existe una clase entrenada de uso incorrecto, se necesita revisión humana o un modelo especializado. Asociación espacial con articulaciones visibles; asociaciones ambiguas se descartan.
- D2: **Aproximación a áreas restringidas**. Zonas separadas de restricción y aproximación; anclaje inferior de la persona con tobillos visibles. Una autorización temporal puede suprimir el aviso para una trayectoria; los IDs no son identidad personal. Las autorizaciones se anulan al reiniciar o perder la trayectoria. Falta de autorización registrada significa autorización no acreditada, no una infracción confirmada.
- D3: **Posturas y posiciones inseguras**. Inclinación 2D de tronco, elevación 2D del brazo, ángulo mínimo de rodilla y zonas posicionales por tarea. No implementa una evaluación ergonómica RULA/REBA validada. Los criterios deben corresponder al ángulo de cámara y al trabajo. El revisor debe distinguir conducta del trabajador y condiciones impuestas por el puesto.
- D4: **Trabajo cerca de vehículos y equipos en movimiento**. Calibración del plano del suelo, comprobación independiente, velocidad temporal del anclaje del equipo y separación estimada respecto a una envolvente circular configurada. Solo opera dentro del área calibrada. Considera acercamiento relativo cuando existe trayectoria suficiente. No reconstruye en 3D la geometría exacta del vehículo ni detecta por sí solo todas las tareas o controles de seguridad.

## Registro y persistencia

- Un episodio automático agrupa dimensiones simultáneas para un ID. El revisor elige una principal; el total se cuenta por eventos confirmados únicos.
- La pérdida o cambio de ID puede fragmentar episodios. Revisa duplicados y vincúlalos al ID COMPLETO de un original confirmado.
- Las capturas automáticas corresponden al fotograma enviado al análisis; se conserva evidencia por dimensión.
- El navegador guarda eventos y revisiones en IndexedDB, y criterios en localStorage. Son datos de ese navegador y origen. Exporta JSON antes de cambiar navegador, borrar datos o mover de sitio privado a localhost. Importar recupera eventos, no sustituye automáticamente criterios actuales.
- Si falla el guardado local, la interfaz avisa; no cierres sin exportar.
- Los vídeos no se suben a la nube y no se incluyen en los proyectos JSON. El motor recibe únicamente fotogramas JPEG cuando se activa el análisis.
- Credenciales RTSP en memoria: no se guardan en proyecto ni en el código. No se distribuyen grabaciones, datos de usuarios ni secretos en este ZIP.
- La reproducción de vídeo se muestrea mientras avanza; no garantiza analizar todos los fotogramas. La persistencia usa tiempo del vídeo. Si hay intervalos grandes, se corta el episodio. Para análisis exhaustivo habría que añadir procesamiento por lotes secuencial.
- Webcam/IP dependen de permisos, códec, disponibilidad de red y hardware. La velocidad depende del equipo. El motor usa CPU por compatibilidad.

## Modelos y referencias

Se descargan al pulsar Cargar modelos, no están redistribuidos en el ZIP:

1. Pose: Ultralytics YOLO11n-pose.
   https://docs.ultralytics.com/tasks/pose/
2. Seguimiento: ByteTrack mediante Ultralytics.
   https://docs.ultralytics.com/modes/track/
3. EPP: Hexmon/vyra-yolo-ppe-detection, best.pt.
   https://huggingface.co/Hexmon/vyra-yolo-ppe-detection
4. Equipos: best.pt del proyecto Construction-Site-Safety-PPE-Detection.
   https://github.com/snehilsanyal/Construction-Site-Safety-PPE-Detection

Los modelos y dependencias conservan sus propias licencias y atribuciones. Consulta sus términos antes de redistribuir pesos o publicar una distribución comercial. La disponibilidad de un repositorio público no acredita precisión en tu centro de trabajo.

Puedes aportar modelos compatibles colocándolos antes de arrancar en:
- local/models/ppe.pt
- local/models/maquinaria.pt
- local/models/yolo11n-pose.pt

Los nombres de clases se interpretan en gear_class(), local/engine.py. Nombres no reconocidos se omiten; revisa las clases mostradas en Estado y modelos.

## Verificación

Consulta VALIDACION.md para las pruebas realizadas y las limitaciones. Las pruebas técnicas no equivalen a validar sensibilidad, precisión o eficacia de la intervención de la tesis. No hay métricas científicas inventadas.
