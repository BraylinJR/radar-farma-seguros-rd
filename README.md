# Radar Farma & Seguros RD

Página pública, gratuita y de actualización automática que reúne los indicadores del
Banco Central, los documentos regulatorios y los titulares de República Dominicana sobre
**farmacias, laboratorios farmacéuticos, medicamentos y seguros**.

Proyecto personal e independiente. No representa la posición de ninguna empresa.
Las noticias pertenecen a sus medios; aquí solo se enlazan.

> Página: <https://braylinjr.github.io/radar-farma-seguros-rd/>

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
4. Asigna una **prioridad** (alta, media o baja) con reglas explícitas y muestra el motivo
   (ver *Prioridad*).
5. Elimina repetidas (misma URL o título muy parecido en fechas cercanas). Cuando la misma
   noticia sale en varios medios se conserva la primera y se anotan los otros enlaces.
6. Lee seis **indicadores económicos** de archivos oficiales del BCRD (ver *Indicadores*).
7. Acumula el historial en `datos/noticias.jsonl`, los indicadores en
   `datos/indicadores.json` y el estado de cada fuente en `datos/estado_fuentes.json`.

## Prioridad

Las reglas están en la sección `prioridad` de `config/clasificacion.yaml` y se aplican igual
a todas las fuentes, sobre el título y las etiquetas:

1. **Alta** si menciona una ley, decreto, resolución, circular o norma con número
   (por ejemplo "Ley 87-01" o "Ley núm. 146-02"), o una reforma, tarifa, cambio de
   cobertura, cierre de una aseguradora o impuesto sobre los seguros.
2. **Baja** si es un comunicado institucional (campañas, aniversarios, premios, talleres),
   o una nota de un medio sin ninguna empresa u organismo de la lista y con tema "Otros".
3. **Media** en los demás casos.

La página muestra la prioridad alta en su propia sección y oculta la baja por defecto
(se puede mostrar con el filtro). La lista de noticias muestra por defecto solo **medios**;
las publicaciones de los organismos están en *Regulación* y en el filtro *Organismos*.

## Indicadores

| Tarjeta | Archivo del BCRD | Cálculo |
|---|---|---|
| Inflación interanual | IPC general base 2019-2020 | Variación de 12 meses publicada |
| Inflación acumulada | IPC general base 2019-2020 | Variación respecto de diciembre publicada |
| Tasa de política monetaria | Serie de la TPM | Tasa vigente y desde cuándo rige |
| Actividad económica (IMAE) | IMAE base 2018 | Variación interanual publicada |
| Actividad salud (PIB real) | PIB por sectores de origen base 2018 | Variación interanual del índice trimestral del sector salud |
| Inflación salud | IPC por grupos | Variación de 12 meses del índice del grupo Salud |

- Cuando el BCRD anuncia el IMAE de un mes en una nota de prensa antes de actualizar el
  archivo, la tarjeta usa la cifra del **título** de esa nota y lo aclara.
- El BCRD no publica un IMAE mensual por sector en archivo de datos. Las notas de prensa
  mencionan salud solo a veces y sin dejar claro si es el mes o el acumulado, así que la
  tarjeta de salud usa la serie trimestral oficial del PIB del sector.
- Las flechas indican la dirección frente a la comparación de cada tarjeta, no un juicio.
- Si un archivo falla, se conserva el último valor bueno marcado como desactualizado, y
  el archivo aparece con error en el panel de fuentes (con aviso a los 3 fallos).
- Las direcciones de los archivos están en `config/indicadores.yaml`.

## Estructura

```
config/
  fuentes.yaml          fuentes a leer (editar aquí para agregar o quitar)
  clasificacion.yaml    palabras clave de sectores, temas, empresas y reglas de prioridad
  correcciones.yaml     correcciones manuales de clasificación
  indicadores.yaml      archivos del BCRD para los indicadores económicos
radar/                  código Python (recolectar, clasificar, deduplicar, almacén, CLI)
datos/
  noticias.jsonl        historial completo (una noticia por línea)
  indicadores.json      últimas tarjetas de indicadores del BCRD
  estado_fuentes.json   último éxito, último error y fallos seguidos por fuente
  ultima_corrida.json   resumen de la última ejecución
docs/
  estilos.css, app.js   estilos y lógica de la página (filtros, gráfico, resumen)
  index.html            página generada en cada corrida (no se guarda en git)
  datos.json            datos de la página, generados en cada corrida (no se guarda en git)
radar/plantilla/        plantilla HTML que usa el generador
tests/                  pruebas automáticas
.github/workflows/
  radar.yml             corrida cada 6 horas: recolecta, guarda, avisa y publica
  pruebas.yml           pruebas del código en cada cambio
```

## La página

`python -m radar generar` construye `docs/index.html` a partir de `datos/` y `config/`.
De arriba abajo: indicadores económicos del BCRD; cabecera con cifras; *Prioridad alta*;
*Regulación* (con filtro por organismo); noticias con buscador y filtros (medios u
organismos, sector, tema, empresa, fechas y prioridad); gráfico por semana y tema;
empresas y organismos más mencionados; resumen semanal solo con datos; estado de las
fuentes; metodología. Tiene botón de modo claro u oscuro (recuerda la elección),
ilustraciones propias en SVG por tema y sector (no se copian imágenes de los medios) y
funciona en el celular. Solo usa una fuente tipográfica de Google Fonts; lo demás va
incluido.

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
| `python -m radar indicadores` | Lee los archivos del BCRD y actualiza `datos/indicadores.json`. |
| `python -m radar avisos --simular` | Muestra qué avisos (issues) se abrirían, sin llamar a GitHub. |
| `python -m unittest discover -s tests` | Ejecuta las pruebas. |

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
4. No hace falta hacer nada para el aviso: una fuente con 3 fallos seguidos abre un
   *issue* en GitHub con la etiqueta `fuente-caida`, asignado a ti (te llega por correo).
   Cuando la fuente vuelve a funcionar, o la desactivas, el issue se cierra solo.

## Automatización

El flujo `.github/workflows/radar.yml` corre en GitHub Actions, gratis:

- **Cuándo:** cada 6 horas (02:17, 08:17, 14:17 y 20:17, hora de RD), cuando cambias
  algo en `config/`, `radar/` o los estilos, y a mano desde la pestaña *Actions*
  (*Radar* > *Run workflow*).
- **Qué hace:** recolecta y clasifica; lee los indicadores del BCRD; vuelve a aplicar las
  reglas y las correcciones de `config/` a todo el historial; genera la página; guarda
  `datos/` en el repositorio con
  un commit; abre o cierra los avisos por fuentes caídas; publica la página en GitHub Pages.
- **Si una fuente falla**, las demás siguen. Si fallan todas (por ejemplo, un corte de
  red), el flujo igual guarda el estado, avisa y vuelve a publicar.
- El flujo `pruebas.yml` ejecuta las pruebas cada vez que cambias el código.

GitHub desactiva los flujos programados de un repositorio sin actividad durante 60 días.
Aquí no debería pasar, porque cada corrida guarda datos con un commit, pero si ocurre
basta con entrar en *Actions* y pulsar *Enable workflow*.

## Cómo publicarlo (una sola vez)

1. **Crear el repositorio.** En GitHub Desktop: *File* > *Add local repository* > elegir
   esta carpeta > *Publish repository*. Nombre: `radar-farma-seguros-rd`. Desmarca
   *Keep this code private*: GitHub Pages es gratis en repositorios públicos.
2. **Activar Pages.** En github.com, dentro del repositorio: *Settings* > *Pages* >
   *Build and deployment* > *Source*: **GitHub Actions**.
3. **Primera corrida.** *Actions* > *Radar* > *Run workflow*. Al publicar el repositorio
   puede arrancar una corrida antes del paso 2 y fallar en *Configurar Pages*: es normal,
   basta con volver a ejecutarla.
4. **Enlace público:** <https://braylinjr.github.io/radar-farma-seguros-rd/>. Aparece
   también en *Settings* > *Pages* y en el resumen de cada corrida.

Nota: la sección *Pages* de la configuración de tu **cuenta** (dominios verificados) no
hace falta. La que importa es *Settings* > *Pages* dentro del **repositorio**, que
aparece después del paso 1.

Los avisos por correo usan las notificaciones normales de GitHub: revisa en
*Settings* (de tu cuenta) > *Notifications* que estén activados los correos de
*Issues* y de *Actions*.

## Fuentes verificadas

- **Medios (23 de octubre de 2026):** Diario Libre, Listín Diario, elDinero, El Día, Hoy,
  N Digital, Acento.
- **Medios agregados (25 de octubre de 2026):** El Nuevo Diario, Noticias SIN, Arecoa,
  Revista Mercado, De Último Minuto, Panorama y Diario Salud.
- **Organismos:** SISALRIL, DIGEMAPS, Superintendencia de Seguros, CNSS, Pro Consumidor,
  Promese/Cal.
- **Indicadores:** archivos públicos del Banco Central de la República Dominicana.
- **Descartados:** Google Noticias, porque su `robots.txt` no permite leer `/rss` con
  procesos automáticos; CDN y El Nacional, porque su `robots.txt` no permite leer el feed;
  El Caribe, porque su feed viene vacío; el Ministerio de Salud, porque su sitio no
  respondía.

## Si cambias el diseño

Los enlaces a `estilos.css` y `app.js` llevan una huella de su contenido (`?v=...`), así
que los visitantes reciben la versión nueva en cuanto se publica, sin caché vieja.

## Licencia

Código bajo licencia MIT. Los titulares y documentos enlazados pertenecen a sus
respectivos medios y organismos.
