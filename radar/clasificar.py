"""Clasificación por palabras clave: sectores, tema y empresas u organismos."""

from __future__ import annotations

import re

from .config import SECTOR_ORGANISMO, TEMA_POR_DEFECTO
from .utilidades import compilar_palabra, normalizar_texto


class Clasificador:
    def __init__(self, configuracion: dict) -> None:
        self.sectores: list[tuple[str, list[re.Pattern]]] = [
            (nombre, [compilar_palabra(p) for p in (definicion or {}).get("palabras") or []])
            for nombre, definicion in configuracion["sectores"].items()
        ]
        self.temas: list[tuple[str, list[re.Pattern]]] = [
            (tema["nombre"], [compilar_palabra(p) for p in tema.get("palabras") or []])
            for tema in configuracion["temas"]
        ]
        self.empresas: list[tuple[str, str, list[re.Pattern]]] = [
            (
                empresa["nombre"],
                (empresa.get("sector") or "") if empresa.get("implica_sector", True) else "",
                [compilar_palabra(p) for p in empresa.get("palabras") or []],
            )
            for empresa in configuracion["empresas"]
        ]
        self.nombres_sectores = [nombre for nombre, _ in self.sectores]
        self.nombres_temas = [nombre for nombre, _ in self.temas] + [TEMA_POR_DEFECTO]

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
    ) -> dict:
        """Devuelve {"sectores": [...], "tema": str, "empresas": [...]}.

        - El tema y las empresas se detectan solo en el título y las etiquetas de la fuente
          (así la clasificación se puede reproducir después sin el resumen).
        - Los sectores salen del título y etiquetas, del sector de las empresas detectadas y,
          como apoyo, del resumen del feed cuando este contiene dos o más palabras clave
          distintas de un mismo sector.
        - Las publicaciones de organismos llevan siempre el sector "Regulación y gobierno".
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
        for _, sector in empresas:
            if sector and sector not in sectores and sector in self.nombres_sectores:
                sectores.append(sector)
        if categoria == "organismo" and SECTOR_ORGANISMO not in sectores:
            sectores.insert(0, SECTOR_ORGANISMO)
        sectores = [s for s in self.nombres_sectores if s in sectores]  # orden del YAML
        tema = self.detectar_tema(texto)
        if tema == TEMA_POR_DEFECTO and tema_fijo:
            tema = tema_fijo
        return {
            "sectores": sectores,
            "sectores_resumen": sectores_resumen,
            "tema": tema,
            "empresas": [nombre for nombre, _ in empresas],
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
