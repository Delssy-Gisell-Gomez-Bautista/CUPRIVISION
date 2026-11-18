# Verificación técnica — 17 de noviembre de 2026

## Completado

- Python: compilación sintáctica de motor y servidor.
- JavaScript: comprobación sintáctica de aplicación y agregación temporal.
- 16 pruebas automatizadas Python: ausencia explícita de EPP, clases, autorización por zona, puntos invisibles, calibración y comprobación independiente, equipo estático, límites de calibración, perfil no revisado, articulaciones ausentes, velocidad y discontinuidad, estado del servidor, página inicial, rechazo de otro origen, autorización de ID inexistente, cámara no conectada y calibración inválida.
- 7 comprobaciones JavaScript: persistencia temporal, agrupación de dimensiones, pendientes excluidos del total, cierre sin prolongar evidencia, interrupción de continuidad, duplicados excluidos y escape de CSV.
- Navegador: apertura de interfaz, formulario de criterios, carga de vídeo técnico, observación manual con captura, revisión como descartado y descarga de CSV. El vídeo de prueba estaba identificado como PRUEBA TÉCNICA; no contiene datos de la investigación y no se incluye en la distribución.
- Inferencia real de YOLO11n-pose sobre la imagen pública de ejemplo de Ultralytics (bus.jpg): devolvió tres personas con ID de seguimiento. Esto comprueba ejecución, no exactitud en tu entorno.
- Carga de los tres modelos: correcta. El modelo EPP Hexmon/vyra-yolo-ppe-detection contiene clases explícitas de presencia/ausencia para casco, chaleco, gafas y guantes. La inferencia conjunta pose+EPP se ejecutó sobre bus.jpg y devolvió un indicio de ausencia de chaleco; no se confirmó como acto inseguro porque la imagen no representa una tarea de la investigación.
- El modelo de maquinaria cargó correctamente. Sin cámara de obra disponible para comprobar su eficacia.
- Guardado local: el evento técnico descartado persistió después de recargar la página.

## Pendiente de validación con el usuario

- Conexión real a tu webcam y a tu cámara IP/RTSP.
- Instalación de extremo a extremo en tu Windows y rendimiento de tu equipo.
- Calibración real sobre el suelo del lugar de trabajo.
- Precisión de EPP, posturas y maquinaria en tus vídeos y condiciones de visibilidad.
- Evaluación etiquetada de TP, FP, FN, precisión, sensibilidad, F1, latencia y reglas por tarea.
- Detección automática de uso incorrecto cuando no haya una clase entrenada explícita.

Pruebas locales:

```text
python -m unittest discover -s tests -v
node tests/test_episodes.cjs
```

Node solo se necesita para esta última prueba de desarrollo; no es necesario para usar el programa.
