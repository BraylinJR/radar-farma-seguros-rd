# Reglas de trabajo: Radar Farma & Seguros RD

Estas reglas aplican a cualquier persona o asistente que trabaje en este repositorio.

## Qué es

Proyecto personal e independiente que reúne titulares y documentos regulatorios públicos
de República Dominicana sobre farmacias, laboratorios, medicamentos y seguros, y los
publica en una página estática. No representa la posición de ninguna empresa.

## Aprobación humana

- Preguntar al dueño del proyecto antes de publicar la página o cualquier cambio en
  GitHub Pages, y antes de crear o modificar el repositorio remoto, los flujos de
  GitHub Actions o los secretos.
- No enviar correos, formularios ni mensajes en nombre del dueño.
- No instalar nada fuera del entorno virtual `.venv` del proyecto.

## Datos y derechos de autor

- De cada noticia se guarda únicamente: título, medio, fecha, enlace original y etiquetas
  de clasificación (sector, tema, empresas). Nunca el texto, el resumen ni imágenes.
- El resumen que traen los feeds solo se usa en memoria para decidir el sector y se descarta.
- Los enlaces apuntan siempre al medio original. La página no reproduce contenido.
- Respetar robots.txt y los términos de cada sitio. Si una fuente no se puede leer de forma
  legítima, se desactiva en `config/fuentes.yaml` y se anota el motivo.
- Google Noticias no se usa: su robots.txt no permite la ruta `/rss` a procesos automáticos.

## Tono y neutralidad

- Todo el sitio en español, tono neutral y descriptivo. No valorar empresas, organismos
  ni personas. El resumen semanal solo contiene datos (conteos, temas, enlaces).

## Cómo cambiar el comportamiento

- Fuentes y palabras clave viven en `config/`. Cambiar la configuración antes que el código.
- Las correcciones manuales de clasificación van en `config/correcciones.yaml`, nunca
  editando `datos/noticias.jsonl` a mano.
- El historial `datos/noticias.jsonl` es acumulativo: no borrarlo ni reescribirlo salvo
  decisión explícita del dueño.

## Ejecución

- Python en `.venv` (`.venv\Scripts\python.exe -m radar ...`). Comandos: `recolectar`,
  `reclasificar`, `probar "título"`, `estado`, `indicadores`, `generar`, `avisos --simular`.
- Indicadores: solo archivos oficiales del BCRD (`config/indicadores.yaml`). No usar una
  cifra cuyo período sea ambiguo; documentar en la tarjeta cualquier sustitución.
- La prioridad se decide solo con las reglas de `config/clasificacion.yaml`. No ordenar ni
  destacar titulares a mano.
- No commitear `datos/` desde la copia local: lo escribe el flujo de Actions cada 6 horas y
  un commit local provocaría conflictos.
- Pruebas: `python -m unittest discover -s tests`. Deben pasar antes de cada commit.
- En GitHub Actions (`.github/workflows/radar.yml`) la corrida es: recolectar,
  reclasificar, generar, commit de `datos/`, avisos y publicación en Pages.
- Una fuente que falla nunca detiene a las demás. El estado por fuente queda en
  `datos/estado_fuentes.json`.
