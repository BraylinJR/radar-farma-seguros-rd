"""Funciones auxiliares: normalización de texto, URL, fechas e identificadores."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

ZONA_RD = ZoneInfo("America/Santo_Domingo")

PARAMETROS_RASTREO = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "source", "amp", "output",
}

PALABRAS_VACIAS = {
    "a", "al", "ante", "bajo", "con", "contra", "de", "del", "desde", "durante", "en", "entre",
    "hacia", "hasta", "mediante", "para", "por", "segun", "sin", "sobre", "tras", "el", "la",
    "los", "las", "un", "una", "unos", "unas", "y", "e", "o", "u", "que", "se", "su", "sus",
    "es", "son", "fue", "ser", "lo", "le", "les", "mas", "como", "este", "esta", "estos", "estas",
    "ese", "esa", "esos", "esas", "ya", "no", "si", "pero", "tambien", "hay", "ha", "han", "rd",
}


def ahora_rd() -> datetime:
    """Fecha y hora actual en la zona de República Dominicana."""
    return datetime.now(ZONA_RD)


def quitar_acentos(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def normalizar_texto(texto: str | None) -> str:
    """Minúsculas, sin acentos y con espacios simples."""
    if not texto:
        return ""
    return re.sub(r"\s+", " ", quitar_acentos(texto).lower()).strip()


def compilar_palabra(palabra: str) -> re.Pattern:
    """Convierte una palabra clave del YAML en una expresión regular.

    - Se compara sin acentos ni mayúsculas.
    - Coincide con palabras completas.
    - Un asterisco admite cualquier terminación ("farmac*").
    - Los espacios admiten uno o más espacios.
    """
    limpia = normalizar_texto(palabra)
    partes = [re.escape(parte).replace(r"\*", r"\w*") for parte in limpia.split(" ") if parte]
    patron = r"\s+".join(partes)
    return re.compile(r"(?<!\w)" + patron + r"(?!\w)")


def limpiar_html(texto: str | None) -> str:
    """Quita etiquetas HTML y entidades básicas de un fragmento."""
    if not texto:
        return ""
    import html as _html

    sin_etiquetas = re.sub(r"<[^>]+>", " ", texto)
    return re.sub(r"\s+", " ", _html.unescape(sin_etiquetas)).strip()


def normalizar_url(url: str) -> str:
    """Forma canónica de una URL para detectar repeticiones."""
    url = (url or "").strip()
    partes = urlsplit(url)
    esquema = "https"
    host = partes.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    ruta = re.sub(r"/+$", "", partes.path) or "/"
    parametros = [
        (k, v) for k, v in parse_qsl(partes.query, keep_blank_values=True)
        if k.lower() not in PARAMETROS_RASTREO and not k.lower().startswith("utm_")
    ]
    consulta = urlencode(sorted(parametros))
    return urlunsplit((esquema, host, ruta, consulta, ""))


def id_desde_url(url: str) -> str:
    """Identificador corto y estable de una noticia a partir de su URL canónica."""
    return hashlib.sha1(normalizar_url(url).encode("utf-8")).hexdigest()[:12]


def tokens_titulo(titulo: str) -> frozenset[str]:
    """Conjunto de palabras significativas de un título, para comparar parecidos."""
    limpio = re.sub(r"[^a-z0-9ñ ]+", " ", normalizar_texto(titulo))
    return frozenset(t for t in limpio.split() if len(t) >= 3 and t not in PALABRAS_VACIAS)


def similitud(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def desde_struct_time(valor) -> datetime | None:
    """Convierte el struct_time (UTC) que entrega feedparser a datetime con zona RD."""
    if not valor:
        return None
    try:
        dt = datetime(*valor[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    return dt.astimezone(ZONA_RD)


def desde_iso(valor: str | None) -> datetime | None:
    """Convierte una fecha ISO 8601 (con o sin zona) a datetime con zona RD."""
    if not valor:
        return None
    texto = valor.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(texto)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZONA_RD)
    return dt.astimezone(ZONA_RD)


def a_iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") if dt else None
