"""Clasificación por palabras clave: sectores, tema y empresas u organismos."""

from __future__ import annotations

import re

from .config import SECTOR_ORGANISMO, TEMA_POR_DEFECTO
from .utilidades import compilar_palabra, normalizar_texto


def _compilar_lista(palabras: list[str] | None) -> list[re.Pattern]:
    """Compila una lista de palabras clave sin repetir las que solo difieren en
    mayúsculas o acentos ("seguros" y "Seguros" son la misma palabra)."""
    vistos: dict[str, re.Pattern] = {}
    for palabra in palabras or []:
        patron = compilar_palabra(str(palabra))
        vistos.setdefault(patron.pattern, patron)
    return list(vistos.values())


class Clasificador:
    def __init__(self, configuracion: dict) -> None:
        self.sectores: list[tuple[str, list[re.Pattern]]] = [
            (nombre, _compilar_lista((definicion or {}).get("palabras")))
            for nombre, definicion in configuracion["sectores"].items()
        ]
        self.temas: list[tuple[str, list[re.Pattern]]] = [
            (tema["nombre"], _compilar_lista(tema.get("palabras")))
            for tema in configuracion["temas"]
        ]
        self.empresas: list[tuple[str, str, list[re.Pattern]]] = [
            (
                empresa["nombre"],
                (empresa.get("sector") or "") if empresa.get("implica_sector", True) else "",
                _compilar_lista(empresa.get("palabras")),
            )
            for empresa in configuracion["empresas"]
        ]
        self.nombres_sectores = [nombre for nombre, _ in self.sectores]
        self.nombres_temas = [nombre for nombre, _ in self.temas] + [TEMA_POR_DEFECTO]

        prioridad = configuracion.get("prioridad") or {}
        alta = prioridad.get("alta") or {}
        self.alta_expresiones = []
        for entrada in alta.get("expresiones") or []:
            if isinstance(entrada, dict):
                self.alta_expresiones.append((re.compile(entrada["expresion"]), entrada.get("motivo")))
            else:
                self.alta_expresiones.append((re.compile(entrada), None))
        self.alta_palabras = [(p, compilar_palabra(str(p))) for p in alta.get("palabras") or []]
        self.baja_palabras = [(p, compilar_palabra(str(p))) for p in (prioridad.get("baja") or {}).get("palabras") or []]
        sin_actor = prioridad.get("sin_actor") or {}
        self.sin_actor_solo_medios = bool(sin_actor.get("solo_medios", True))
        self.sin_actor_temas = set(sin_actor.get("temas") or [])

    # -------------------------------------------------------------- prioridad

    @staticmethod
    def _texto_prioridad(titulo: str, etiquetas: list[str] | None) -> str:
        texto = Clasificador.texto_para_reglas(titulo, etiquetas)
        return re.sub(r"[–‑]", "-", texto)

    @staticmethod
    def _formatear_norma(fragmento: str) -> str:
        """'ley no. 87 - 01' -> 'Ley 87-01'; 'resol 525 06' -> 'Resol. 525-06' (para mostrar el motivo)."""
        limpio = re.sub(r"\s*-\s*", "-", fragmento.strip())
        limpio = re.sub(r"\s+(?:n(?:o|um|umero|°|º)\.?)\s*", " ", limpio)
        limpio = re.sub(r"(\d{1,4})\s+(\d{2,4})$", r"\1-\2", limpio)
        limpio = re.sub(r"^(res|resol)\.?\s", r"\1. ", limpio)
        limpio = re.sub(r"\bcnss\b", "CNSS", limpio)
        limpio = re.sub(r"\bresolucion(es)?\b", lambda m: "resolución" if not m.group(1) else "resoluciones", limpio)
        limpio = re.sub(r"\bcamara\b", "cámara", limpio)
        return limpio[:1].upper() + limpio[1:]

    def prioridad(self, titulo: str, etiquetas: list[str] | None, categoria: str, tema: str, empresas: list[str]) -> tuple[str, str]:
        """Devuelve (prioridad, motivo) según las reglas de clasificacion.yaml."""
        texto = self._texto_prioridad(titulo, etiquetas)
        for expresion, motivo in self.alta_expresiones:
            m = expresion.search(texto)
            if m:
                return "alta", motivo or f"Menciona {self._formatear_norma(m.group(0))}"
        for palabra, patron in self.alta_palabras:
            if patron.search(texto):
                return "alta", f"Menciona «{palabra}»"
        for palabra, patron in self.baja_palabras:
            if patron.search(texto):
                return "baja", f"Comunicado institucional («{palabra}»)"
        if (not self.sin_actor_solo_medios or categoria == "medio") and not empresas and tema in self.sin_actor_temas:
            return "baja", "Sin empresa u organismo del mercado dominicano"
        return "media", "Noticia del sector"

    # ------------------------------------------------------------ utilidades

    @staticmethod
    def texto_para_reglas(titulo: str, etiquetas: list[str] | None = None, resumen: str = "") -> str:
        partes = [titulo or ""]
        if etiquetas:
            partes.append(" . ".join(etiquetas))
        if resumen:
            partes.append(resumen)
        return normalizar_texto(" . ".join(partes))

    @staticmethod
    def _coincide(patrones: list[re.Pattern], texto: str) -> bool:
        return any(p.search(texto) for p in patrones)

    # --------------------------------------------------------------- reglas

    def detectar_sectores(self, texto: str) -> list[str]:
        return [nombre for nombre, patrones in self.sectores if self._coincide(patrones, texto)]

    def sectores_por_resumen(self, resumen: str, minimo_coincidencias: int = 2) -> list[str]:
        """Sectores cuyo resumen contiene al menos `minimo_coincidencias` palabras clave distintas.

        El resumen es más largo que el título y una sola palabra suelta ("seguros", "vacuna")
        produce falsos positivos; por eso se exige más de una coincidencia distinta.
        """
        texto = normalizar_texto(resumen)
        if not texto:
            return []
        encontrados = []
        for nombre, patrones in self.sectores:
            distintas = sum(1 for p in patrones if p.search(texto))
            if distintas >= minimo_coincidencias:
                encontrados.append(nombre)
        return encontrados

    def detectar_tema(self, texto: str) -> str:
        for nombre, patrones in self.temas:
            if self._coincide(patrones, texto):
                return nombre
        return TEMA_POR_DEFECTO

    def detectar_empresas(self, texto: str) -> list[tuple[str, str]]:
        return [(nombre, sector) for nombre, sector, patrones in self.empresas if self._coincide(patrones, texto)]

    def clasificar(
        self,
        titulo: str,
        etiquetas: list[str] | None = None,
        resumen: str = "",
        categoria: str = "medio",
        tema_fijo: str | None = None,
        organismo_emisor: str | None = None,
    ) -> dict:
        """Devuelve {"sectores": [...], "tema": str, "empresas": [...]}.

        - El tema y las empresas se detectan solo en el título y las etiquetas de la fuente
          (así la clasificación se puede reproducir después sin el resumen).
        - Los sectores salen del título y etiquetas, del sector de las empresas detectadas y,
          como apoyo, del resumen del feed cuando este contiene dos o más palabras clave
          distintas de un mismo sector.
        - Las publicaciones de organismos llevan siempre el sector "Regulación y gobierno" y,
          si el organismo que publica está en la lista de empresas, queda como mencionado.
        - El tema es el primero (en el orden del YAML) cuyas palabras coinciden; si no hay
          ninguno se usa tema_fijo (si existe) o "Otros".
        """
        texto = self.texto_para_reglas(titulo, etiquetas)
        sectores = self.detectar_sectores(texto)
        sectores_resumen = self.sectores_por_resumen(resumen)
        for sector in sectores_resumen:
            if sector not in sectores:
                sectores.append(sector)
        empresas = self.detectar_empresas(texto)
        if organismo_emisor:
            for nombre, sector, _ in self.empresas:
                if nombre == organismo_emisor and nombre not in [n for n, _ in empresas]:
                    empresas.append((nombre, sector))
                    break
        for _, sector in empresas:
            if sector and sector not in sectores and sector in self.nombres_sectores:
                sectores.append(sector)
        if categoria == "organismo" and SECTOR_ORGANISMO not in sectores:
            sectores.insert(0, SECTOR_ORGANISMO)
        sectores = [s for s in self.nombres_sectores if s in sectores]  # orden del YAML
        tema = self.detectar_tema(texto)
        if tema == TEMA_POR_DEFECTO and tema_fijo:
            tema = tema_fijo
        nombres_empresas = [nombre for nombre, _ in empresas]
        # Para "sin actor" solo cuentan las empresas nombradas en el texto, no el organismo emisor.
        mencionadas = [n for n, _ in self.detectar_empresas(texto)]
        prioridad, motivo = self.prioridad(titulo, etiquetas, categoria, tema, mencionadas)
        return {
            "sectores": sectores,
            "sectores_resumen": sectores_resumen,
            "tema": tema,
            "empresas": nombres_empresas,
            "prioridad": prioridad,
            "motivo_prioridad": motivo,
        }


def aplicar_correcciones(noticias: dict[str, dict], correcciones: list[dict]) -> int:
    """Aplica config/correcciones.yaml sobre el diccionario de noticias (por id).

    Devuelve cuántas noticias se modificaron. Las correcciones por enlace se resuelven
    buscando el enlace exacto.
    """
    from .utilidades import normalizar_url

    por_enlace = {normalizar_url(n["enlace"]): clave for clave, n in noticias.items()}
    modificadas = 0
    for correccion in correcciones:
        clave = correccion.get("id")
        if not clave and correccion.get("enlace"):
            clave = por_enlace.get(normalizar_url(correccion["enlace"]))
        if not clave or clave not in noticias:
            continue
        noticia = noticias[clave]
        cambio = False
        for campo in ("sectores", "tema", "empresas"):
            if campo in correccion and correccion[campo] is not None and noticia.get(campo) != correccion[campo]:
                noticia[campo] = correccion[campo]
                cambio = True
        excluir = bool(correccion.get("excluir", False))
        if noticia.get("excluida", False) != excluir:
            noticia["excluida"] = excluir
            cambio = True
        if cambio or not noticia.get("corregida"):
            noticia["corregida"] = True
            modificadas += 1
    return modificadas
