"""Lectura de fuentes: RSS/Atom, sitemaps de noticias y páginas HTML con documentos.

Cada lector devuelve una lista de diccionarios "crudos" con las claves:
    titulo, enlace, fecha (datetime o None), etiquetas (lista), resumen (texto, no se guarda),
    tipo ("noticia" o "documento").
"""

from __future__ import annotations

import html
import re
import time
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import PurePosixPath
from urllib.parse import unquote, urljoin, urlsplit

import feedparser
import requests

from .utilidades import desde_iso, desde_struct_time, limpiar_html

AGENTE_USUARIO = (
    "RadarFarmaSegurosRD/0.1 (proyecto personal sin fines comerciales; "
    "lee RSS y sitemaps publicos; solo guarda titulo, fecha y enlace)"
)
TIEMPO_ESPERA = 30
REINTENTOS = 2

TEXTO_GENERICO = re.compile(
    r"^(descarg|download|ver\b|leer\b|aqu[ií]\b|pdf\b|documento\b|abrir\b|click|clic|haga clic|"
    r"pulse|presione|enlace\b|m[aá]s detalles|m[aá]s informaci[oó]n|consultar\b)",
    re.IGNORECASE,
)


def _texto_generico(texto: str) -> bool:
    """True si el texto del enlace no sirve como título ("Descargar", "Click para descargar...")."""
    limpio = texto.strip()
    if len(limpio) < 6:
        return True
    # "Click para descargar circular 05-2026" sí trae información, pero más corta que el nombre del archivo.
    return bool(TEXTO_GENERICO.match(limpio))


class ErrorFuente(Exception):
    """Fallo al leer o interpretar una fuente."""


def descargar(url: str) -> bytes:
    ultimo_error: Exception | None = None
    for intento in range(1, REINTENTOS + 2):
        try:
            respuesta = requests.get(
                url,
                headers={
                    "User-Agent": AGENTE_USUARIO,
                    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.5",
                    "Accept-Language": "es-DO, es;q=0.9",
                },
                timeout=TIEMPO_ESPERA,
            )
            respuesta.raise_for_status()
            if not respuesta.content:
                raise ErrorFuente("respuesta vacía")
            return respuesta.content
        except Exception as error:  # noqa: BLE001 - se informa el error real en el estado
            ultimo_error = error
            if intento <= REINTENTOS:
                time.sleep(3 * intento)
    raise ErrorFuente(f"{type(ultimo_error).__name__}: {ultimo_error}")


# ---------------------------------------------------------------- RSS / Atom

def leer_rss(contenido: bytes, fuente: dict) -> list[dict]:
    datos = feedparser.parse(contenido)
    if not datos.entries:
        if datos.bozo and datos.get("bozo_exception"):
            raise ErrorFuente(f"feed ilegible: {datos.bozo_exception}")
        return []
    elementos = []
    for entrada in datos.entries:
        titulo = limpiar_html(entrada.get("title"))
        enlace = (entrada.get("link") or "").strip()
        if not titulo or not enlace.startswith("http"):
            continue
        fecha = desde_struct_time(entrada.get("published_parsed") or entrada.get("updated_parsed"))
        etiquetas = []
        for etiqueta in entrada.get("tags") or []:
            termino = limpiar_html(etiqueta.get("term") or etiqueta.get("label"))
            if termino and termino not in etiquetas:
                etiquetas.append(termino)
        resumen = limpiar_html(entrada.get("summary") or entrada.get("description") or "")[:600]
        elementos.append({
            "titulo": titulo,
            "enlace": enlace,
            "fecha": fecha,
            "etiquetas": etiquetas,
            "resumen": resumen,
            "tipo": "noticia",
        })
    return elementos


# ------------------------------------------------------- Sitemap de noticias

ESPACIOS = {
    "s": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "n": "http://www.google.com/schemas/sitemap-news/0.9",
}


def leer_sitemap_noticias(contenido: bytes, fuente: dict) -> list[dict]:
    try:
        raiz = ET.fromstring(contenido)
    except ET.ParseError as error:
        raise ErrorFuente(f"sitemap ilegible: {error}") from error
    if raiz.tag.endswith("sitemapindex"):
        raise ErrorFuente("la URL es un índice de sitemaps, no un sitemap de noticias")
    elementos = []
    for nodo in raiz.findall("s:url", ESPACIOS):
        enlace = (nodo.findtext("s:loc", default="", namespaces=ESPACIOS) or "").strip()
        noticia = nodo.find("n:news", ESPACIOS)
        if not enlace.startswith("http") or noticia is None:
            continue
        titulo = limpiar_html(noticia.findtext("n:title", default="", namespaces=ESPACIOS))
        if not titulo:
            continue
        fecha = desde_iso(noticia.findtext("n:publication_date", default="", namespaces=ESPACIOS))
        palabras = noticia.findtext("n:keywords", default="", namespaces=ESPACIOS) or ""
        etiquetas = [p.strip() for p in palabras.split(",") if p.strip()]
        elementos.append({
            "titulo": titulo,
            "enlace": enlace,
            "fecha": fecha,
            "etiquetas": etiquetas,
            "resumen": "",
            "tipo": "noticia",
        })
    return elementos


# ------------------------------------------------- Página HTML con documentos

class _ExtractorEnlaces(HTMLParser):
    """Recoge (href, texto visible) de cada <a> en orden de aparición."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.enlaces: list[tuple[str, str]] = []
        self._href: str | None = None
        self._texto: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            atributos = dict(attrs)
            self._href = atributos.get("href")
            self._texto = []

    def handle_data(self, data):
        if self._href is not None:
            self._texto.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            texto = re.sub(r"\s+", " ", "".join(self._texto)).strip()
            self.enlaces.append((self._href, texto))
            self._href = None
            self._texto = []


def _titulo_desde_archivo(url: str) -> str:
    nombre = PurePosixPath(unquote(urlsplit(url).path)).stem
    nombre = re.sub(r"^[\d\-_\s]+(?=[A-Za-z])", "", nombre)  # quita prefijos numéricos (ids)
    nombre = re.sub(r"[-_]+", " ", nombre)
    nombre = re.sub(r"\s+", " ", nombre).strip()
    return nombre[:1].upper() + nombre[1:] if nombre else ""


def leer_html_documentos(contenido: bytes, fuente: dict) -> list[dict]:
    texto = contenido.decode("utf-8", errors="replace")
    extractor = _ExtractorEnlaces()
    try:
        extractor.feed(texto)
    except Exception as error:  # noqa: BLE001
        raise ErrorFuente(f"HTML ilegible: {error}") from error

    patron_enlace = re.compile(fuente["patron_enlace"]) if fuente.get("patron_enlace") else None
    patron_titulo = re.compile(fuente["patron_titulo"]) if fuente.get("patron_titulo") else None

    por_enlace: dict[str, str] = {}
    orden: list[str] = []
    for href, texto_enlace in extractor.enlaces:
        if not href:
            continue
        absoluto = urljoin(fuente["url"], html.unescape(href).strip())
        if not absoluto.startswith("http"):
            continue
        if patron_enlace and not patron_enlace.search(absoluto):
            continue
        texto_limpio = texto_enlace.strip()
        generico = _texto_generico(texto_limpio)
        if absoluto not in por_enlace:
            por_enlace[absoluto] = "" if generico else texto_limpio
            orden.append(absoluto)
        elif not por_enlace[absoluto] and not generico:
            por_enlace[absoluto] = texto_limpio

    elementos = []
    for enlace in orden:
        titulo = por_enlace[enlace] or _titulo_desde_archivo(enlace)
        if not titulo:
            continue
        if patron_titulo and not patron_titulo.search(titulo):
            continue
        elementos.append({
            "titulo": titulo[:200],
            "enlace": enlace,
            "fecha": None,
            "etiquetas": [],
            "resumen": "",
            "tipo": "documento",
        })
    return elementos


# ----------------------------------------------------------------- Despacho

LECTORES = {
    "rss": leer_rss,
    "sitemap_noticias": leer_sitemap_noticias,
    "html_documentos": leer_html_documentos,
}


def leer_fuente(fuente: dict) -> list[dict]:
    """Descarga e interpreta una fuente. Lanza ErrorFuente si algo falla."""
    lector = LECTORES[fuente["tipo"]]
    contenido = descargar(fuente["url"])
    return lector(contenido, fuente)
