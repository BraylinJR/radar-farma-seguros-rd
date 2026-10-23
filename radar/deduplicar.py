"""Detección de noticias repetidas: misma URL o título muy parecido en fechas cercanas."""

from __future__ import annotations

from datetime import date, timedelta

from .utilidades import desde_iso, similitud, tokens_titulo

UMBRAL_SIMILITUD = 0.75
DIAS_VENTANA = 3


class IndiceDuplicados:
    """Índice en memoria de títulos ya guardados, agrupados por fecha."""

    def __init__(self, noticias: dict[str, dict]) -> None:
        self._por_dia: dict[date, list[tuple[str, frozenset[str]]]] = {}
        for noticia in noticias.values():
            self.agregar(noticia)

    @staticmethod
    def _dia(noticia: dict) -> date | None:
        fecha = desde_iso(noticia.get("fecha"))
        return fecha.date() if fecha else None

    def agregar(self, noticia: dict) -> None:
        dia = self._dia(noticia)
        if dia is None:
            return
        self._por_dia.setdefault(dia, []).append((noticia["id"], tokens_titulo(noticia["titulo"])))

    def buscar(self, titulo: str, dia: date | None) -> str | None:
        """Devuelve el id de una noticia parecida publicada a pocos días, o None."""
        if dia is None:
            return None
        tokens = tokens_titulo(titulo)
        if len(tokens) < 3:
            return None
        mejor_id, mejor_valor = None, 0.0
        for desplazamiento in range(-DIAS_VENTANA, DIAS_VENTANA + 1):
            for id_existente, tokens_existente in self._por_dia.get(dia + timedelta(days=desplazamiento), []):
                valor = similitud(tokens, tokens_existente)
                if valor > mejor_valor:
                    mejor_id, mejor_valor = id_existente, valor
        return mejor_id if mejor_valor >= UMBRAL_SIMILITUD else None
