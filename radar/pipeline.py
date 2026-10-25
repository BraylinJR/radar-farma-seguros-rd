"""Proceso completo: leer fuentes, clasificar, deduplicar, guardar y registrar el estado."""

from __future__ import annotations

import re
import sys
from datetime import datetime

from . import almacen, config
from .clasificar import Clasificador, aplicar_correcciones
from .deduplicar import IndiceDuplicados
from .recolectar import ErrorFuente, leer_fuente
from .utilidades import ZONA_RD, a_iso, ahora_rd, id_desde_url, normalizar_url


def _registrar(mensaje: str) -> None:
    print(mensaje, flush=True)


# ---------------------------------------------------------------- fechas

def _fecha_documento(titulo: str, enlace: str, ahora: datetime) -> tuple[datetime, str]:
    """Estima la fecha de un documento sin fecha explícita.

    Devuelve (fecha, precision) con precision en {"mes", "anio", "deteccion"}.
    - Año en el título (p. ej. "Circular 12-2026") -> 31 de diciembre de ese año (precisión "anio"),
      o el mes de la ruta /uploads/AAAA/MM/ si coincide el año (precisión "mes").
    - Solo ruta /uploads/AAAA/MM/ -> primer día de ese mes (precisión "mes").
    - Si nada de esto existe o la fecha resultante es futura -> fecha de detección.
    """
    anio_titulo = None
    anios_validos = [
        int(a) for a in re.findall(r"(?<!\d)(20\d{2})(?!\d)", titulo)
        if 2000 <= int(a) <= ahora.year  # ignora números que no son años ("Comunicado 2066", "PEI 2025-2028")
    ]
    if anios_validos:
        anio_titulo = max(anios_validos)
    ruta = re.search(r"/(20\d{2})/(\d{2})/", enlace)
    anio_ruta = int(ruta.group(1)) if ruta else None
    mes_ruta = int(ruta.group(2)) if ruta else None

    candidata: datetime | None = None
    precision = "deteccion"
    if anio_titulo and anio_ruta == anio_titulo and mes_ruta and 1 <= mes_ruta <= 12:
        candidata, precision = datetime(anio_titulo, mes_ruta, 1, tzinfo=ZONA_RD), "mes"
    elif anio_titulo:
        candidata, precision = datetime(anio_titulo, 12, 31, 23, 59, tzinfo=ZONA_RD), "anio"
    elif anio_ruta and mes_ruta and 1 <= mes_ruta <= 12:
        candidata, precision = datetime(anio_ruta, mes_ruta, 1, tzinfo=ZONA_RD), "mes"

    if candidata is None or candidata > ahora:
        return ahora, "deteccion"
    return candidata, precision


# ---------------------------------------------------------------- noticias

def _construir_noticia(crudo: dict, fuente: dict, clasificacion: dict, ahora: datetime) -> dict:
    fecha = crudo.get("fecha")
    precision = "dia"
    if fecha is None:
        if crudo["tipo"] == "documento":
            fecha, precision = _fecha_documento(crudo["titulo"], crudo["enlace"], ahora)
        else:
            fecha, precision = ahora, "deteccion"
    return {
        "id": id_desde_url(crudo["enlace"]),
        "titulo": crudo["titulo"],
        "medio": fuente["nombre"],
        "fuente_id": fuente["id"],
        "categoria": fuente["categoria"],
        "tipo": crudo["tipo"],
        "fecha": a_iso(fecha),
        "precision_fecha": precision,
        "enlace": crudo["enlace"],
        "sectores": clasificacion["sectores"],
        "sectores_resumen": clasificacion.get("sectores_resumen", []),
        "tema": clasificacion["tema"],
        "empresas": clasificacion["empresas"],
        "prioridad": clasificacion["prioridad"],
        "motivo_prioridad": clasificacion["motivo_prioridad"],
        "etiquetas_fuente": crudo.get("etiquetas") or [],
        "capturado": a_iso(ahora),
        "tambien_en": [],
        "excluida": False,
        "corregida": False,
    }


def _procesar_fuente(
    fuente: dict,
    crudos: list[dict],
    noticias: dict[str, dict],
    indice: IndiceDuplicados,
    clasificador: Clasificador,
    ahora: datetime,
) -> dict:
    conteo = {"leidos": len(crudos), "nuevos": 0, "repetidos": 0, "descartados": 0}
    for crudo in crudos:
        clave = id_desde_url(crudo["enlace"])
        if clave in noticias:
            conteo["repetidos"] += 1
            continue
        clasificacion = clasificador.clasificar(
            crudo["titulo"],
            crudo.get("etiquetas"),
            crudo.get("resumen", ""),
            categoria=fuente["categoria"],
            tema_fijo=fuente.get("tema_fijo"),
            organismo_emisor=fuente["nombre"] if fuente["categoria"] == "organismo" else None,
        )
        if fuente["categoria"] == "medio" and not clasificacion["sectores"]:
            conteo["descartados"] += 1
            continue
        noticia = _construir_noticia(crudo, fuente, clasificacion, ahora)
        dia = datetime.fromisoformat(noticia["fecha"]).date()
        parecida = indice.buscar(noticia["titulo"], dia)
        if parecida and parecida in noticias:
            existente = noticias[parecida]
            referencia = {"medio": noticia["medio"], "enlace": noticia["enlace"]}
            enlaces_conocidos = {normalizar_url(existente["enlace"])} | {
                normalizar_url(r["enlace"]) for r in existente.get("tambien_en", [])
            }
            if normalizar_url(noticia["enlace"]) not in enlaces_conocidos and existente["medio"] != noticia["medio"]:
                existente.setdefault("tambien_en", []).append(referencia)
            conteo["repetidos"] += 1
            continue
        noticias[clave] = noticia
        indice.agregar(noticia)
        conteo["nuevos"] += 1
    return conteo


# ------------------------------------------------------------------ estado

def _actualizar_estado(estado: dict, fuente: dict, ahora: datetime, error: str | None, conteo: dict | None) -> None:
    registro = estado.setdefault(fuente["id"], {"fallos_consecutivos": 0})
    registro.update({
        "nombre": fuente["nombre"],
        "tipo": fuente["tipo"],
        "url": fuente["url"],
        "categoria": fuente["categoria"],
        "activa": True,
        "ultima_lectura": a_iso(ahora),
    })
    if error is None:
        registro["fallos_consecutivos"] = 0
        registro["ultimo_exito"] = a_iso(ahora)
        registro["mensaje_error"] = None
        registro["conteo_ultima_lectura"] = conteo
        registro["estado"] = "ok"
    else:
        registro["fallos_consecutivos"] = int(registro.get("fallos_consecutivos", 0)) + 1
        registro["ultimo_error"] = a_iso(ahora)
        registro["mensaje_error"] = error[:300]
        registro["estado"] = "error"


# ---------------------------------------------------------------- comandos

def recolectar(solo_fuente: str | None = None, guardar: bool = True) -> dict:
    inicio = ahora_rd()
    fuentes = config.cargar_fuentes()
    if solo_fuente:
        fuentes = [f for f in fuentes if f["id"] == solo_fuente]
        if not fuentes:
            raise SystemExit(f"No existe una fuente activa con id '{solo_fuente}'")
    # Los organismos se leen primero: si un medio repite el mismo titular, la versión
    # que se conserva es la de la fuente oficial y el medio queda en "tambien_en".
    fuentes = sorted(fuentes, key=lambda f: 0 if f["categoria"] == "organismo" else 1)
    clasificador = Clasificador(config.cargar_clasificacion())
    correcciones = config.cargar_correcciones()
    noticias = almacen.cargar_noticias()
    estado = almacen.cargar_estado()
    indice = IndiceDuplicados(noticias)

    resumen = {"inicio": a_iso(inicio), "fuentes": {}, "nuevas": 0, "repetidas": 0, "descartadas": 0, "errores": 0}
    _registrar(f"Radar: {len(fuentes)} fuentes activas, {len(noticias)} noticias en el historial")

    for fuente in fuentes:
        ahora = ahora_rd()
        try:
            crudos = leer_fuente(fuente)
        except ErrorFuente as error:
            _actualizar_estado(estado, fuente, ahora, str(error), None)
            resumen["errores"] += 1
            resumen["fuentes"][fuente["id"]] = {"error": str(error)}
            _registrar(f"  [ERROR] {fuente['id']}: {error}")
            continue
        except Exception as error:  # noqa: BLE001 - una fuente nunca detiene a las demás
            mensaje = f"{type(error).__name__}: {error}"
            _actualizar_estado(estado, fuente, ahora, mensaje, None)
            resumen["errores"] += 1
            resumen["fuentes"][fuente["id"]] = {"error": mensaje}
            _registrar(f"  [ERROR] {fuente['id']}: {mensaje}")
            continue
        conteo = _procesar_fuente(fuente, crudos, noticias, indice, clasificador, ahora)
        _actualizar_estado(estado, fuente, ahora, None, conteo)
        resumen["fuentes"][fuente["id"]] = conteo
        resumen["nuevas"] += conteo["nuevos"]
        resumen["repetidas"] += conteo["repetidos"]
        resumen["descartadas"] += conteo["descartados"]
        _registrar(
            f"  [ok] {fuente['id']}: {conteo['leidos']} leídos, {conteo['nuevos']} nuevos, "
            f"{conteo['repetidos']} repetidos, {conteo['descartados']} fuera del sector"
        )

    # Fuentes desactivadas: se conservan en el estado como inactivas.
    activas = {f["id"] for f in config.cargar_fuentes()}
    for id_fuente, registro in estado.items():
        if registro.get("categoria") == "indicador":
            continue  # los archivos del BCRD los gestiona radar.indicadores
        registro["activa"] = id_fuente in activas

    corregidas = aplicar_correcciones(noticias, correcciones)
    resumen["corregidas"] = corregidas
    resumen["fin"] = a_iso(ahora_rd())
    resumen["total_historial"] = len(noticias)

    if guardar:
        almacen.guardar_noticias(noticias)
        almacen.guardar_estado(estado)
        almacen.guardar_ultima_corrida(resumen)
    _registrar(
        f"Resultado: {resumen['nuevas']} nuevas, {resumen['repetidas']} repetidas, "
        f"{resumen['descartadas']} fuera del sector, {resumen['errores']} fuentes con error, "
        f"{len(noticias)} en el historial"
    )
    return resumen


def reclasificar(guardar: bool = True) -> dict:
    """Vuelve a clasificar todo el historial con las reglas actuales (título y etiquetas).

    El resumen del feed no se guarda, así que los sectores que en su momento aportó el
    resumen (campo "sectores_resumen") se conservan tal cual. Una noticia de un medio
    que ya no coincide con ningún sector queda marcada como excluida (no se borra del
    historial). Las correcciones manuales se aplican al final y siempre prevalecen.
    """
    fuentes = {f["id"]: f for f in config.cargar_fuentes(solo_activas=False)}
    clasificador = Clasificador(config.cargar_clasificacion())
    correcciones = config.cargar_correcciones()
    noticias = almacen.cargar_noticias()
    cambios = 0
    excluidas = 0
    for noticia in noticias.values():
        fuente = fuentes.get(noticia["fuente_id"], {})
        nueva = clasificador.clasificar(
            noticia["titulo"],
            noticia.get("etiquetas_fuente"),
            "",
            categoria=noticia.get("categoria", "medio"),
            tema_fijo=fuente.get("tema_fijo"),
            organismo_emisor=noticia["medio"] if noticia.get("categoria") == "organismo" else None,
        )
        nueva["sectores_resumen"] = noticia.get("sectores_resumen", [])
        for sector in nueva["sectores_resumen"]:
            if sector not in nueva["sectores"]:
                nueva["sectores"].append(sector)
        nueva["sectores"] = [s for s in clasificador.nombres_sectores if s in nueva["sectores"]]
        antes = (noticia.get("sectores"), noticia.get("tema"), noticia.get("empresas"), noticia.get("excluida"),
                 noticia.get("prioridad"))
        noticia.update(nueva)
        noticia["corregida"] = False
        noticia["excluida"] = False
        if noticia.get("categoria") == "medio" and not noticia["sectores"]:
            noticia["excluida"] = True
            noticia["motivo_exclusion"] = "sin sector con las reglas actuales"
            excluidas += 1
        else:
            noticia.pop("motivo_exclusion", None)
        if antes != (noticia["sectores"], noticia["tema"], noticia["empresas"], noticia["excluida"], noticia["prioridad"]):
            cambios += 1
    corregidas = aplicar_correcciones(noticias, correcciones)
    if guardar:
        almacen.guardar_noticias(noticias)
    _registrar(
        f"Reclasificadas {len(noticias)} noticias: {cambios} cambiaron, {excluidas} excluidas por no coincidir, "
        f"{corregidas} con corrección manual"
    )
    return {"total": len(noticias), "cambiadas": cambios, "excluidas": excluidas, "corregidas": corregidas}


def probar(titulo: str) -> dict:
    """Muestra cómo se clasificaría un título (útil para ajustar palabras clave)."""
    clasificador = Clasificador(config.cargar_clasificacion())
    return clasificador.clasificar(titulo)


def estado_fuentes() -> list[dict]:
    estado = almacen.cargar_estado()
    filas = []
    for id_fuente, registro in sorted(estado.items()):
        filas.append({
            "id": id_fuente,
            "nombre": registro.get("nombre"),
            "estado": registro.get("estado"),
            "activa": registro.get("activa", True),
            "fallos_consecutivos": registro.get("fallos_consecutivos", 0),
            "ultimo_exito": registro.get("ultimo_exito"),
            "mensaje_error": registro.get("mensaje_error"),
        })
    return filas


def _configurar_salida() -> None:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
