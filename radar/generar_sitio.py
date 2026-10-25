"""Genera el sitio estático en docs/ a partir de datos/ y config/.

Produce:
    docs/index.html            página completa con los datos incrustados (funciona sin servidor)
    docs/datos.json            los mismos datos, por si alguien quiere reutilizarlos
    datos/resumen_semanal.json resumen de los últimos 7 días, solo con cifras y enlaces
"""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from . import almacen, config
from .utilidades import ZONA_RD, a_iso, ahora_rd, desde_iso

PLANTILLA = Path(__file__).resolve().parent / "plantilla" / "index.html"
DIAS_EN_PAGINA = 548  # 18 meses de historial incrustado en la página
DIAS_RESUMEN = 7
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def fecha_larga(dt: datetime) -> str:
    return f"{dt.day} de {MESES[dt.month - 1]} de {dt.year}"


def fecha_hora_larga(dt: datetime) -> str:
    return f"{fecha_larga(dt)}, {dt:%H:%M} (hora de República Dominicana)"


def _item_pagina(noticia: dict) -> dict:
    return {
        "id": noticia["id"],
        "titulo": noticia["titulo"],
        "medio": noticia["medio"],
        "fuente_id": noticia.get("fuente_id"),
        "categoria": noticia.get("categoria", "medio"),
        "tipo": noticia.get("tipo", "noticia"),
        "fecha": noticia["fecha"],
        "precision": noticia.get("precision_fecha", "dia"),
        "enlace": noticia["enlace"],
        "sectores": noticia.get("sectores", []),
        "tema": noticia.get("tema", config.TEMA_POR_DEFECTO),
        "empresas": noticia.get("empresas", []),
        "tambien_en": noticia.get("tambien_en", []),
    }


def resumen_semanal(items: list[dict], ahora: datetime) -> dict:
    inicio = (ahora - timedelta(days=DIAS_RESUMEN)).replace(hour=0, minute=0, second=0, microsecond=0)
    semana = [i for i in items if (desde_iso(i["fecha"]) or inicio) >= inicio]
    por_sector: Counter = Counter()
    por_tema: Counter = Counter()
    empresas: Counter = Counter()
    medios: Counter = Counter()
    for item in semana:
        for sector in item["sectores"]:
            por_sector[sector] += 1
        por_tema[item["tema"]] += 1
        for empresa in item["empresas"]:
            empresas[empresa] += 1
        medios[item["medio"]] += 1
    regulatorias = [
        {"id": i["id"], "titulo": i["titulo"], "medio": i["medio"], "enlace": i["enlace"],
         "fecha": i["fecha"], "precision": i["precision"], "tema": i["tema"], "tipo": i["tipo"]}
        for i in semana if i["categoria"] == "organismo"
    ]
    return {
        "periodo": {
            "inicio": a_iso(inicio),
            "fin": a_iso(ahora),
            "texto": f"del {fecha_larga(inicio)} al {fecha_larga(ahora)}",
        },
        "total": len(semana),
        "de_medios": sum(1 for i in semana if i["categoria"] == "medio"),
        "de_organismos": len(regulatorias),
        "por_sector": dict(por_sector.most_common()),
        "por_tema": dict(por_tema.most_common()),
        "empresas_mas_mencionadas": empresas.most_common(10),
        "medios_mas_activos": medios.most_common(10),
        "regulatorias": regulatorias,
    }


def _estado_para_pagina(estado: dict) -> list[dict]:
    filas = []
    for id_fuente, registro in estado.items():
        filas.append({
            "id": id_fuente,
            "nombre": registro.get("nombre", id_fuente),
            "tipo": registro.get("tipo"),
            "categoria": registro.get("categoria"),
            "activa": registro.get("activa", True),
            "estado": registro.get("estado", "sin datos"),
            "ultimo_exito": registro.get("ultimo_exito"),
            "ultimo_error": registro.get("ultimo_error"),
            "fallos_consecutivos": registro.get("fallos_consecutivos", 0),
            "mensaje_error": registro.get("mensaje_error"),
            "conteo": registro.get("conteo_ultima_lectura"),
        })
    filas.sort(key=lambda f: (0 if f["categoria"] == "organismo" else 1, f["nombre"], f["id"]))
    return filas


def construir_datos(ahora: datetime | None = None) -> dict:
    ahora = ahora or ahora_rd()
    clasificacion = config.cargar_clasificacion()
    noticias = almacen.cargar_noticias()
    estado = almacen.cargar_estado()
    ultima = almacen.cargar_ultima_corrida()

    limite = ahora - timedelta(days=DIAS_EN_PAGINA)
    visibles = [
        _item_pagina(n) for n in noticias.values()
        if not n.get("excluida") and (desde_iso(n["fecha"]) or ahora) >= limite
    ]
    visibles.sort(key=lambda i: i["fecha"], reverse=True)

    temas = [t["nombre"] for t in clasificacion["temas"]] + [config.TEMA_POR_DEFECTO]
    sectores = list(clasificacion["sectores"].keys())

    repositorio = os.environ.get("GITHUB_REPOSITORY")
    servidor = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    return {
        "meta": {
            "repositorio": f"{servidor}/{repositorio}" if repositorio else None,
            "generado": a_iso(ahora),
            "generado_texto": fecha_hora_larga(ahora),
            "total_historial": len(noticias),
            "total_en_pagina": len(visibles),
            "dias_en_pagina": DIAS_EN_PAGINA,
            "ultima_corrida": {
                "inicio": ultima.get("inicio"),
                "fin": ultima.get("fin"),
                "nuevas": ultima.get("nuevas"),
                "errores": ultima.get("errores"),
            },
        },
        "sectores": sectores,
        "temas": temas,
        "items": visibles,
        "resumen_semanal": resumen_semanal(visibles, ahora),
        "fuentes": _estado_para_pagina(estado),
    }


def incrustar_json(json_texto: str) -> str:
    """Prepara JSON para ir dentro de <script>: un "</script>" o "<!--" en un título
    rompería la página. Se escapan "<", ">" y "&" como \\u003c, \\u003e y \\u0026
    (sigue siendo JSON válido y JSON.parse devuelve el texto original)."""
    return json_texto.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def generar(carpeta_salida: Path = config.CARPETA_SITIO) -> Path:
    datos = construir_datos()
    carpeta_salida.mkdir(parents=True, exist_ok=True)

    json_datos = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    json_incrustado = incrustar_json(json_datos)

    plantilla = PLANTILLA.read_text(encoding="utf-8")
    html = (
        plantilla
        .replace("{{DATOS_JSON}}", json_incrustado)
        .replace("{{GENERADO_TEXTO}}", datos["meta"]["generado_texto"])
        .replace("{{GENERADO_ISO}}", datos["meta"]["generado"])
    )
    (carpeta_salida / "index.html").write_text(html, encoding="utf-8", newline="\n")
    (carpeta_salida / "datos.json").write_text(json_datos + "\n", encoding="utf-8", newline="\n")
    (carpeta_salida / ".nojekyll").touch()

    config.CARPETA_DATOS.mkdir(parents=True, exist_ok=True)
    (config.CARPETA_DATOS / "resumen_semanal.json").write_text(
        json.dumps(datos["resumen_semanal"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(
        f"Sitio generado en {carpeta_salida / 'index.html'}: {datos['meta']['total_en_pagina']} noticias en la página, "
        f"{datos['resumen_semanal']['total']} en los últimos {DIAS_RESUMEN} días"
    )
    return carpeta_salida / "index.html"
