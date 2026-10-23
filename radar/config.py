"""Carga de los archivos de configuración (config/*.yaml) y rutas del proyecto."""

from __future__ import annotations

from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_CONFIG = RAIZ / "config"
CARPETA_DATOS = RAIZ / "datos"
CARPETA_SITIO = RAIZ / "docs"

ARCHIVO_FUENTES = CARPETA_CONFIG / "fuentes.yaml"
ARCHIVO_CLASIFICACION = CARPETA_CONFIG / "clasificacion.yaml"
ARCHIVO_CORRECCIONES = CARPETA_CONFIG / "correcciones.yaml"

ARCHIVO_NOTICIAS = CARPETA_DATOS / "noticias.jsonl"
ARCHIVO_ESTADO = CARPETA_DATOS / "estado_fuentes.json"
ARCHIVO_ULTIMA_CORRIDA = CARPETA_DATOS / "ultima_corrida.json"

TIPOS_VALIDOS = {"rss", "sitemap_noticias", "html_documentos"}
CATEGORIAS_VALIDAS = {"medio", "organismo"}
SECTOR_ORGANISMO = "Regulación y gobierno"
TEMA_POR_DEFECTO = "Otros"


def _leer_yaml(ruta: Path) -> dict:
    with ruta.open("r", encoding="utf-8") as archivo:
        contenido = yaml.safe_load(archivo)
    return contenido or {}


def cargar_fuentes(solo_activas: bool = True) -> list[dict]:
    datos = _leer_yaml(ARCHIVO_FUENTES)
    fuentes = datos.get("fuentes") or []
    ids = set()
    validas = []
    for fuente in fuentes:
        faltantes = [c for c in ("id", "nombre", "tipo", "url", "categoria") if not fuente.get(c)]
        if faltantes:
            raise ValueError(f"Fuente incompleta en fuentes.yaml (faltan {faltantes}): {fuente}")
        if fuente["tipo"] not in TIPOS_VALIDOS:
            raise ValueError(f"Tipo desconocido '{fuente['tipo']}' en la fuente {fuente['id']}")
        if fuente["categoria"] not in CATEGORIAS_VALIDAS:
            raise ValueError(f"Categoría desconocida '{fuente['categoria']}' en la fuente {fuente['id']}")
        if fuente["id"] in ids:
            raise ValueError(f"Id repetido en fuentes.yaml: {fuente['id']}")
        ids.add(fuente["id"])
        fuente.setdefault("activa", True)
        if solo_activas and not fuente["activa"]:
            continue
        validas.append(fuente)
    return validas


def cargar_clasificacion() -> dict:
    datos = _leer_yaml(ARCHIVO_CLASIFICACION)
    for clave in ("sectores", "temas", "empresas"):
        if clave not in datos:
            raise ValueError(f"Falta la sección '{clave}' en clasificacion.yaml")
    if SECTOR_ORGANISMO not in datos["sectores"]:
        raise ValueError(f"clasificacion.yaml debe definir el sector '{SECTOR_ORGANISMO}'")
    return datos


def cargar_correcciones() -> list[dict]:
    if not ARCHIVO_CORRECCIONES.exists():
        return []
    datos = _leer_yaml(ARCHIVO_CORRECCIONES)
    return datos.get("correcciones") or []
