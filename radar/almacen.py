"""Lectura y escritura de los archivos de datos (JSONL y JSON)."""

from __future__ import annotations

import json
from pathlib import Path

from .config import ARCHIVO_ESTADO, ARCHIVO_NOTICIAS, ARCHIVO_ULTIMA_CORRIDA, CARPETA_DATOS


def cargar_noticias(ruta: Path = ARCHIVO_NOTICIAS) -> dict[str, dict]:
    """Devuelve las noticias como diccionario {id: noticia}, en el orden del archivo."""
    noticias: dict[str, dict] = {}
    if not ruta.exists():
        return noticias
    with ruta.open("r", encoding="utf-8") as archivo:
        for numero, linea in enumerate(archivo, start=1):
            linea = linea.strip()
            if not linea:
                continue
            try:
                noticia = json.loads(linea)
            except json.JSONDecodeError as error:
                raise ValueError(f"Línea {numero} de {ruta.name} no es JSON válido: {error}") from error
            noticias[noticia["id"]] = noticia
    return noticias


def guardar_noticias(noticias: dict[str, dict], ruta: Path = ARCHIVO_NOTICIAS) -> None:
    """Escribe el historial ordenado por fecha ascendente (diffs estables en git)."""
    CARPETA_DATOS.mkdir(parents=True, exist_ok=True)
    ordenadas = sorted(noticias.values(), key=lambda n: (n.get("fecha") or "", n["id"]))
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    with temporal.open("w", encoding="utf-8", newline="\n") as archivo:
        for noticia in ordenadas:
            archivo.write(json.dumps(noticia, ensure_ascii=False, sort_keys=True))
            archivo.write("\n")
    temporal.replace(ruta)


def _cargar_json(ruta: Path, por_defecto):
    if not ruta.exists():
        return por_defecto
    with ruta.open("r", encoding="utf-8") as archivo:
        return json.load(archivo)


def _guardar_json(ruta: Path, datos) -> None:
    CARPETA_DATOS.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    with temporal.open("w", encoding="utf-8", newline="\n") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2, sort_keys=True)
        archivo.write("\n")
    temporal.replace(ruta)


def cargar_estado() -> dict[str, dict]:
    return _cargar_json(ARCHIVO_ESTADO, {})


def guardar_estado(estado: dict[str, dict]) -> None:
    _guardar_json(ARCHIVO_ESTADO, estado)


def cargar_ultima_corrida() -> dict:
    return _cargar_json(ARCHIVO_ULTIMA_CORRIDA, {})


def guardar_ultima_corrida(datos: dict) -> None:
    _guardar_json(ARCHIVO_ULTIMA_CORRIDA, datos)
