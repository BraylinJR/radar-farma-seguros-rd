# Radar Farma & Seguros RD

Página pública, gratuita y de actualización automática que reúne los titulares y los
documentos regulatorios de República Dominicana sobre **farmacias, laboratorios
farmacéuticos, medicamentos y seguros**.

Proyecto personal e independiente. No representa la posición de ninguna empresa.
Las noticias pertenecen a sus medios; aquí solo se enlazan.

> Estado: fases 3 (recolección y clasificación) y 4 (página estática en `docs/`)
> terminadas y probadas en local. La automatización con GitHub Actions y la
> publicación en GitHub Pages (fase 5) se documentan aquí cuando estén listas.

## Qué hace

Cada corrida del radar:

1. Lee las fuentes de `config/fuentes.yaml` (RSS, sitemaps de noticias y páginas de
   documentos de organismos). Si una fuente falla, sigue con las demás.
2. Guarda de cada noticia **solo** título, medio, fecha, enlace original y etiquetas.
   No copia el texto ni el resumen.
3. Clasifica por **sector** (Farmacia, Laboratorios, Seguros de salud (ARS), Seguros
   generales, Regulación y gobierno), por **tema** (Precios, Regulación, Lanzamientos,
   Fusiones y adquisiciones, Resultados financieros, Alertas sanitarias, Otros) y por
   **empresa u organismo** mencionado, usando reglas por palabras clave.
4. Elimina repetidas (misma URL o título muy parecido en fechas cercanas). Cuando la misma
   noticia sale en varios medios se conserva la primera y se anotan los otros enlaces.
5. Acumula el historial en `datos/noticias.jsonl` y el estado de cada fuente en
   `datos/estado_fuentes.json`.

## Estructura

```
config/
  fuentes.yaml          fuentes a leer (editar aquí para agregar o quitar)
  clasificacion.yaml    palabras clave de sectores, temas y empresas
  correcciones.yaml     correcciones manuales de clasificación
radar/                  código Python (recolectar, clasificar, deduplicar, almacén, CLI)
datos/
  noticias.jsonl        historial completo (una noticia por línea)
  estado_fuentes.json   último éxito, último error y fallos seguidos por fuente
  ultima_corrida.json   resumen de la última ejecución
docs/
  index.html            página generada (los datos van incrustados; abre sin servidor)
  datos.json            los mismos datos de la página, reutilizables
  estilos.css, app.js   estilos y lógica de la página (filtros, gráfico, resumen)
radar/plantilla/        plantilla HTML que usa el generador
```

## La página

`python -m radar generar` construye `docs/index.html` a partir de `datos/` y `config/`.
Incluye: sección destacada de Regulación, lista de titulares con buscador y filtros
(sector, tema, empresa u organismo, fechas), gráfico de titulares por semana y tema,
empresas y organismos más mencionados del mes, resumen semanal solo con datos, fecha y
hora de la última actualización y un panel con el estado de cada fuente. Funciona en
el celular y en modo claro u oscuro, sin dependencias externas.

Para verla en tu computadora abre `docs/index.html` en el navegador, o sirve la carpeta:

```bash
python -m http.server 8765 --bind 127.0.0.1 --directory docs
```

La página muestra los titulares de los últimos 18 meses; el historial completo sigue
en `datos/noticias.jsonl`.

## Cómo ejecutarlo en tu computadora

Requiere Python 3.11 o superior.

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m radar recolectar
```

Otros comandos:

| Comando | Qué hace |
|---|---|
| `python -m radar recolectar` | Lee todas las fuentes activas, clasifica y guarda. |
| `python -m radar recolectar --fuente eldinero` | Lee una sola fuente (por su `id`). |
| `python -m radar recolectar --sin-guardar` | Prueba sin escribir en `datos/`. |
| `python -m radar probar "Título de prueba"` | Muestra cómo se clasificaría un título. |
| `python -m radar reclasificar` | Vuelve a clasificar todo el historial con las reglas actuales. |
| `python -m radar estado` | Estado de cada fuente (ok, error, fallos seguidos). |
| `python -m radar generar` | Construye la página en `docs/` y el resumen semanal en `datos/`. |

## Cómo agregar o quitar una fuente

Edita `config/fuentes.yaml`. Cada fuente es un bloque como este:

```yaml
  - id: eldinero            # identificador único, sin espacios
    nombre: elDinero        # nombre que se muestra
    tipo: rss               # rss | sitemap_noticias | html_documentos
    url: https://eldinero.com.do/feed/
    categoria: medio        # medio (se filtra por sector) | organismo (se guarda todo)
    activa: true            # false para desactivarla sin borrarla
```

Antes de agregar una fuente, revisa su `robots.txt` y sus términos de uso. Para páginas
de documentos (`html_documentos`) puedes limitar los enlaces con `patron_enlace` y los
títulos con `patron_titulo` (expresiones regulares), y fijar un tema con `tema_fijo`.

## Cómo agregar o quitar una palabra clave

Edita `config/clasificacion.yaml`:

- **Sectores**: lista de palabras por sector. Una noticia de un medio se guarda solo si
  coincide con algún sector.
- **Temas**: se evalúan en el orden del archivo; se asigna el primero que coincida.
- **Empresas**: nombre a mostrar, sector y palabras con las que se detecta. Usa frases
  completas para nombres ambiguos (`"ARS Humano"` y no `"Humano"`).

Reglas de coincidencia: sin distinguir mayúsculas ni acentos, por palabra completa,
y con `*` al final para admitir terminaciones (`farmac*`).

Después de cambiar palabras clave, ejecuta `python -m radar reclasificar` para aplicar
las reglas nuevas al historial. Prueba una regla con `python -m radar probar "..."`.

## Cómo corregir una clasificación errónea

Agrega una entrada en `config/correcciones.yaml` con el `id` (está en
`datos/noticias.jsonl`) o el `enlace` exacto de la noticia:

```yaml
correcciones:
  - id: 3f2a9c1e7b
    tema: Precios
  - enlace: https://www.ejemplo.com.do/noticia-fuera-del-sector
    excluir: true
```

Las correcciones se aplican en cada corrida y prevalecen sobre las reglas automáticas.

## Qué hacer si una fuente deja de funcionar

1. Revisa el estado con `python -m radar estado` o en `datos/estado_fuentes.json`
   (campo `mensaje_error`).
2. Abre la URL de la fuente en el navegador. Si el feed cambió de dirección, actualiza
   `url` en `config/fuentes.yaml`. Si el sitio ya no ofrece RSS, prueba con su sitemap de
   noticias (`tipo: sitemap_noticias`, suele estar declarado en `robots.txt`).
3. Si la fuente no se puede leer de forma legítima, ponle `activa: false` y anota el
   motivo en `nota`.
4. Cuando la automatización esté activa, una fuente con 3 fallos seguidos genera un
   *issue* en GitHub de forma automática (fase 5).

## Fuentes verificadas (23 de octubre de 2026)

Medios: Diario Libre, Listín Diario, elDinero, El Día, Hoy, N Digital, Acento.
Organismos: SISALRIL, DIGEMAPS, Superintendencia de Seguros, CNSS, Pro Consumidor,
Promese/Cal. El Ministerio de Salud quedó desactivado porque su sitio no respondía.
Google Noticias se descartó porque su `robots.txt` no permite leer `/rss` con procesos
automáticos.

## Licencia

Código bajo licencia MIT. Los titulares y documentos enlazados pertenecen a sus
respectivos medios y organismos.
