"""Indicadores económicos del Banco Central de la República Dominicana (BCRD).

Lee los archivos oficiales de config/indicadores.yaml y calcula seis tarjetas:
inflación interanual, inflación acumulada, tasa de política monetaria (TPM), IMAE,
actividad del sector salud (PIB real trimestral) e inflación del grupo Salud del IPC.

Los lectores reciben filas (listas de celdas) y buscan los encabezados por su texto,
no por posición fija. Cada valor pasa un control de rango antes de publicarse. Si un
archivo falla, se conservan los últimos valores buenos marcados como desactualizados.
"""

from __future__ import annotations

import io
import json
import re
from datetime import datetime

import requests
import yaml

from . import almacen, config
from .utilidades import a_iso, ahora_rd, normalizar_texto

ARCHIVO_CONFIG = config.CARPETA_CONFIG / "indicadores.yaml"
ARCHIVO_SALIDA = config.CARPETA_DATOS / "indicadores.json"
AGENTE = "RadarFarmaSegurosRD/0.1 (proyecto personal sin fines comerciales; lee estadisticas publicas del BCRD)"

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
TRIMESTRES = {"e-m": 1, "a-j": 2, "j-s": 3, "o-d": 4}
TEXTO_TRIMESTRE = {1: "ene–mar", 2: "abr–jun", 3: "jul–sep", 4: "oct–dic"}

RANGOS = {  # control de cordura: fuera de rango = error de lectura, no se publica
    "inflacion": (-15.0, 60.0),
    "tpm": (0.0, 40.0),
    "actividad": (-40.0, 40.0),
}


class ErrorIndicador(Exception):
    pass


# ------------------------------------------------------------------ celdas

def _texto(celda) -> str:
    return normalizar_texto("" if celda is None else str(celda))


def _numero(celda) -> float | None:
    if celda is None or isinstance(celda, bool):
        return None
    if isinstance(celda, (int, float)):
        return float(celda)
    texto = str(celda).strip().replace(",", "")
    try:
        return float(texto)
    except ValueError:
        return None


def _anio(celda) -> int | None:
    texto = "" if celda is None else str(celda).strip()
    if len(texto) > 12:
        return None
    m = re.match(r"^((?:19|20)\d{2})(?:\.0)?\b", texto)
    return int(m.group(1)) if m else None


def _mes(celda) -> int | None:
    texto = _texto(celda).strip(" .*")
    if not texto or len(texto) > 12 or not texto.isalpha():
        return None
    prefijo = "sep" if texto.startswith("set") else texto[:3]
    return MESES_CORTOS.index(prefijo) + 1 if prefijo in MESES_CORTOS else None


def recorrer_meses(filas: list[list], desde: int = 0):
    """Recorre filas con año y mes en las primeras dos columnas, en cualquiera de los
    formatos del BCRD (año y mes en la misma fila, o el año en una fila aparte).
    Produce (año, mes, fila)."""
    anio = None
    for fila in filas[desde:]:
        if not fila:
            continue
        c0 = fila[0] if len(fila) > 0 else None
        c1 = fila[1] if len(fila) > 1 else None
        if _anio(c0):
            anio = _anio(c0)
        mes = _mes(c0) or _mes(c1)
        if anio and mes:
            yield anio, mes, fila


def _buscar_columna(filas: list[list], patron: str, hasta: int = 15, desde_columna: int = 0) -> tuple[int, int]:
    """Devuelve (fila, columna) de la primera celda cuyo texto coincide con el patrón."""
    regex = re.compile(patron)
    for i, fila in enumerate(filas[:hasta]):
        for j, celda in enumerate(fila):
            if j >= desde_columna and regex.search(_texto(celda)):
                return i, j
    raise ErrorIndicador(f"no se encontró el encabezado '{patron}'")


def _valor(fila: list, columna: int) -> float | None:
    return _numero(fila[columna]) if columna < len(fila) else None


# ------------------------------------------------------------------ lectores

def leer_ipc(filas: list[list]) -> list[dict]:
    """IPC general: índice y variaciones mensual, acumulada (con diciembre) e interanual (12 meses)."""
    fila_enc, col_12 = _buscar_columna(filas, r"^12 meses$")
    _, col_acum = _buscar_columna(filas, r"^con dic")
    _, col_mens = _buscar_columna(filas, r"^mensual$")
    _, col_ind = _buscar_columna(filas, r"^indice$")
    serie = []
    for anio, mes, fila in recorrer_meses(filas, fila_enc + 1):
        indice = _valor(fila, col_ind)
        interanual = _valor(fila, col_12)
        if indice is None or interanual is None:
            continue
        serie.append({"anio": anio, "mes": mes, "indice": indice, "mensual": _valor(fila, col_mens),
                      "acumulada": _valor(fila, col_acum), "interanual": interanual})
    if len(serie) < 13:
        raise ErrorIndicador("IPC: muy pocas filas leídas")
    return serie


def leer_ipc_grupo(filas: list[list], grupo: str = "salud") -> list[dict]:
    """IPC por grupos: índice del grupo pedido; la variación interanual se calcula."""
    fila_enc, col = _buscar_columna(filas, rf"^{grupo}$")
    serie = []
    for anio, mes, fila in recorrer_meses(filas, fila_enc + 1):
        indice = _valor(fila, col)
        if indice is not None:
            serie.append({"anio": anio, "mes": mes, "indice": indice})
    por_mes = {(p["anio"], p["mes"]): p["indice"] for p in serie}
    for p in serie:
        base = por_mes.get((p["anio"] - 1, p["mes"]))
        p["interanual"] = (p["indice"] / base - 1) * 100 if base else None
        anterior = por_mes.get((p["anio"], p["mes"] - 1) if p["mes"] > 1 else (p["anio"] - 1, 12))
        p["mensual"] = (p["indice"] / anterior - 1) * 100 if anterior else None
    serie = [p for p in serie if p["interanual"] is not None]
    if len(serie) < 13:
        raise ErrorIndicador(f"IPC grupo {grupo}: muy pocas filas leídas")
    return serie


def leer_tpm(filas: list[list]) -> list[dict]:
    """Tasa de política monetaria mensual. El archivo la expresa en fracción (0.055 = 5.50 %)."""
    fila_enc, col = _buscar_columna(filas, r"^tasa de politica monetaria$")
    serie = []
    for anio, mes, fila in recorrer_meses(filas, fila_enc + 1):
        valor = _valor(fila, col)
        if valor is None:
            continue
        serie.append({"anio": anio, "mes": mes, "tasa": valor * 100 if valor <= 1 else valor})
    if len(serie) < 13:
        raise ErrorIndicador("TPM: muy pocas filas leídas")
    return serie


def leer_imae(filas: list[list]) -> list[dict]:
    """IMAE, serie original: índice y variaciones interanual y acumulada (las primeras columnas con esos nombres)."""
    fila_enc, col_inter = _buscar_columna(filas, r"^interanual$")
    _, col_acum = _buscar_columna(filas, r"^acumulada$")
    _, col_ind = _buscar_columna(filas, r"^indice$")
    preliminar = any(re.search(r"preliminar", _texto(c)) for fila in filas[-6:] for c in fila)
    serie = []
    for anio, mes, fila in recorrer_meses(filas, fila_enc + 1):
        inter = _valor(fila, col_inter)
        if inter is None:
            continue
        serie.append({"anio": anio, "mes": mes, "indice": _valor(fila, col_ind), "interanual": inter,
                      "acumulada": _valor(fila, col_acum), "preliminar": preliminar})
    if len(serie) < 13:
        raise ErrorIndicador("IMAE: muy pocas filas leídas")
    return serie


def leer_pib_sector(filas: list[list], sector: str = "salud") -> list[dict]:
    """PIB real trimestral por sector (hoja de índices de volumen): variación interanual calculada.

    Toma la primera fila cuyo nombre es exactamente el sector (el bloque de índices) y
    lee años y trimestres de las filas de encabezado (años con "(p)" = preliminar).
    """
    fila_trim = next((i for i, f in enumerate(filas[:20]) if any(_texto(c) in TRIMESTRES for c in f)), None)
    if fila_trim is None:
        raise ErrorIndicador("PIB por sectores: no se encontraron los trimestres")
    fila_anios = filas[fila_trim - 1]
    columnas = []
    anio, preliminar = None, False
    for j, celda in enumerate(filas[fila_trim]):
        if j < len(fila_anios) and _anio(fila_anios[j]):
            anio = _anio(fila_anios[j])
            preliminar = "(p)" in str(fila_anios[j]).lower()
        trimestre = TRIMESTRES.get(_texto(celda))
        if trimestre and anio:
            columnas.append((j, anio, trimestre, preliminar))
    fila_sector = next((f for f in filas[fila_trim + 1:] if f and _texto(f[0]) == sector), None)
    if fila_sector is None:
        raise ErrorIndicador(f"PIB por sectores: no se encontró la fila '{sector}'")
    puntos = [{"anio": a, "trimestre": t, "indice": _valor(fila_sector, j), "preliminar": p}
              for j, a, t, p in columnas if _valor(fila_sector, j) is not None]
    por_trim = {(p["anio"], p["trimestre"]): p["indice"] for p in puntos}
    for p in puntos:
        base = por_trim.get((p["anio"] - 1, p["trimestre"]))
        p["interanual"] = (p["indice"] / base - 1) * 100 if base else None
    puntos = [p for p in puntos if p["interanual"] is not None]
    if len(puntos) < 5:
        raise ErrorIndicador("PIB por sectores: muy pocos trimestres")
    return puntos


def titulo_nota_imae(titulo: str) -> tuple[float, int, int] | None:
    """Extrae (variación, mes, año) del título de una nota de prensa del IMAE de un mes concreto.
    Ignora los títulos de promedios acumulados ("promedio de 4.5 % en enero-agosto")."""
    t = normalizar_texto(titulo)
    if "promedio" in t or not re.search(r"econom|imae|actividad", t):
        return None
    m = re.search(r"(-?\d+[.,]\d+)\s*%\s*(?:interanual\s+)?en\s+(" + "|".join(MESES) + r")\s+(?:de\s+)?(20\d{2})", t)
    if not m:
        return None
    return float(m.group(1).replace(",", ".")), MESES.index(m.group(2)) + 1, int(m.group(3))


# ------------------------------------------------------------------ descarga

def descargar_filas(url: str, hoja: str | None = None) -> list[list]:
    respuesta = requests.get(url, headers={"User-Agent": AGENTE}, timeout=60)
    respuesta.raise_for_status()
    contenido = respuesta.content
    if url.lower().endswith(".xls"):
        import xlrd

        libro = xlrd.open_workbook(file_contents=contenido)
        h = libro.sheet_by_name(hoja) if hoja else libro.sheet_by_index(0)
        return [[h.cell_value(f, c) for c in range(h.ncols)] for f in range(h.nrows)]
    import openpyxl

    libro = openpyxl.load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    h = libro[hoja] if hoja else libro.worksheets[0]
    return [list(f) for f in h.iter_rows(values_only=True)]


def notas_prensa(cfg: dict) -> list[dict]:
    respuesta = requests.post(cfg["url_contenido"], data={"id": cfg["seccion_id"], "languageName": "es"},
                              headers={"User-Agent": AGENTE, "Content-Type": "application/x-www-form-urlencoded"}, timeout=40)
    respuesta.raise_for_status()
    datos = json.loads(respuesta.text)
    while isinstance(datos, str):
        datos = json.loads(datos)
    encontrados: list[dict] = []

    def recorrer(nodo):
        if isinstance(nodo, dict):
            if isinstance(nodo.get("id"), int) and isinstance(nodo.get("title"), str) and nodo.get("creationTime"):
                encontrados.append({"id": nodo["id"], "titulo": nodo["title"], "fecha": str(nodo["creationTime"])[:10]})
            for v in nodo.values():
                recorrer(v)
        elif isinstance(nodo, list):
            for v in nodo:
                recorrer(v)

    recorrer(datos)
    return sorted(encontrados, key=lambda n: n["fecha"], reverse=True)


# ------------------------------------------------------------------ tarjetas

def _mes_texto(anio: int, mes: int, corto: bool = False) -> str:
    return f"{(MESES_CORTOS if corto else MESES)[mes - 1]} {anio}"


def _direccion(actual: float, anterior: float | None, decimales: int) -> str:
    if anterior is None:
        return "igual"
    a, b = round(actual, decimales), round(anterior, decimales)
    return "sube" if a > b else "baja" if a < b else "igual"


def _fmt(valor: float, decimales: int) -> str:
    return f"{valor:.{decimales}f} %"


def _comprobar(valor: float, rango: str, nombre: str) -> float:
    minimo, maximo = RANGOS[rango]
    if not (minimo <= valor <= maximo):
        raise ErrorIndicador(f"{nombre}: valor fuera de rango ({valor})")
    return valor


def _tarjeta(id_, nombre, valor, decimales, periodo, comparacion, anterior, serie, fuente, **extra):
    return {
        "id": id_, "nombre": nombre, "valor": round(valor, decimales), "decimales": decimales,
        "texto_valor": _fmt(valor, decimales), "periodo": periodo, "comparacion": comparacion,
        "direccion": _direccion(valor, anterior, decimales), "serie": serie, "fuente": fuente,
        "desactualizado": False, **extra,
    }


def tarjetas_ipc(ipc: list[dict], meta: str, fuente: dict) -> list[dict]:
    u, p = ipc[-1], ipc[-2]
    hace_un_anio = next((x for x in ipc if x["anio"] == u["anio"] - 1 and x["mes"] == u["mes"]), None)
    _comprobar(u["interanual"], "inflacion", "inflación interanual")
    serie = [{"etiqueta": _mes_texto(x["anio"], x["mes"], True), "valor": round(x["interanual"], 2)} for x in ipc[-13:]]
    interanual = _tarjeta(
        "inflacion_interanual", "Inflación interanual", u["interanual"], 2, _mes_texto(u["anio"], u["mes"]),
        f"{MESES[p['mes'] - 1].capitalize()}: {_fmt(p['interanual'], 2)} · {meta}", p["interanual"], serie, fuente)
    acumulada_anterior = hace_un_anio["acumulada"] if hace_un_anio else None
    serie_acum = [{"etiqueta": _mes_texto(x["anio"], x["mes"], True), "valor": round(x["acumulada"], 2)} for x in ipc[-13:] if x["acumulada"] is not None]
    acumulada = _tarjeta(
        "inflacion_acumulada", "Inflación acumulada", _comprobar(u["acumulada"], "inflacion", "inflación acumulada"), 2,
        f"enero–{MESES[u['mes'] - 1]} {u['anio']}",
        f"Mismo período de {u['anio'] - 1}: {_fmt(acumulada_anterior, 2)}" if acumulada_anterior is not None else "",
        acumulada_anterior, serie_acum, fuente)
    return [interanual, acumulada]


def tarjeta_tpm(tpm: list[dict], fuente: dict) -> dict:
    u, p = tpm[-1], tpm[-2]
    _comprobar(u["tasa"], "tpm", "TPM")
    # desde cuándo rige la tasa actual y cuál fue la anterior distinta
    inicio = len(tpm) - 1
    while inicio > 0 and round(tpm[inicio - 1]["tasa"], 2) == round(u["tasa"], 2):
        inicio -= 1
    desde = tpm[inicio]
    distinta = tpm[inicio - 1] if inicio > 0 else None
    hace_un_anio = next((x for x in tpm if x["anio"] == u["anio"] - 1 and x["mes"] == u["mes"]), None)
    partes = []
    if distinta:
        partes.append(f"Antes: {_fmt(distinta['tasa'], 2)}")
    if hace_un_anio:
        partes.append(f"{_mes_texto(hace_un_anio['anio'], hace_un_anio['mes'], True)}: {_fmt(hace_un_anio['tasa'], 2)}")
    serie = [{"etiqueta": _mes_texto(x["anio"], x["mes"], True), "valor": round(x["tasa"], 2)} for x in tpm[-13:]]
    return _tarjeta("tpm", "Tasa de política monetaria (TPM)", u["tasa"], 2,
                    f"vigente desde {_mes_texto(desde['anio'], desde['mes'])}", " · ".join(partes), p["tasa"], serie, fuente)


def tarjeta_imae(imae: list[dict], nota: dict | None, fuente: dict) -> dict:
    u, p = imae[-1], imae[-2]
    _comprobar(u["interanual"], "actividad", "IMAE")
    serie = [{"etiqueta": _mes_texto(x["anio"], x["mes"], True), "valor": round(x["interanual"], 1)} for x in imae[-13:]]
    if nota and (nota["anio"], nota["mes"]) > (u["anio"], u["mes"]):
        _comprobar(nota["valor"], "actividad", "IMAE (nota)")
        serie.append({"etiqueta": _mes_texto(nota["anio"], nota["mes"], True), "valor": nota["valor"]})
        return _tarjeta(
            "imae", "Actividad económica (IMAE)", nota["valor"], 1,
            f"{_mes_texto(nota['anio'], nota['mes'])} · preliminar",
            f"{MESES[u['mes'] - 1].capitalize()}: {_fmt(u['interanual'], 1)} · ene–{MESES_CORTOS[u['mes'] - 1]}: {_fmt(u['acumulada'], 1)}",
            u["interanual"], serie[-13:], {**fuente, "nota": nota["enlace"]},
            aclaracion=f"Dato de la nota de prensa del BCRD del {nota['fecha']}; el archivo de datos aún no incluye {MESES[nota['mes'] - 1]}.")
    return _tarjeta(
        "imae", "Actividad económica (IMAE)", u["interanual"], 1,
        f"{_mes_texto(u['anio'], u['mes'])}{' · preliminar' if u['preliminar'] else ''}",
        f"Ene–{MESES_CORTOS[u['mes'] - 1]}: {_fmt(u['acumulada'], 1)} · {MESES[p['mes'] - 1]}: {_fmt(p['interanual'], 1)}",
        p["interanual"], serie, fuente)


def tarjeta_salud_actividad(pib: list[dict], fuente: dict) -> dict:
    u, p = pib[-1], pib[-2]
    _comprobar(u["interanual"], "actividad", "actividad salud")
    serie = [{"etiqueta": f"T{x['trimestre']} {x['anio']}", "valor": round(x["interanual"], 1)} for x in pib[-8:]]
    return _tarjeta(
        "salud_actividad", "Actividad salud (PIB real)", u["interanual"], 1,
        f"{TEXTO_TRIMESTRE[u['trimestre']]} {u['anio']}{' · preliminar' if u['preliminar'] else ''}",
        f"{TEXTO_TRIMESTRE[p['trimestre']].capitalize()} {p['anio']}: {_fmt(p['interanual'], 1)}",
        p["interanual"], serie, fuente,
        aclaracion="El BCRD no publica un IMAE mensual por sector en archivo de datos; se usa el PIB real trimestral del sector salud.")


def tarjeta_inflacion_salud(grupo: list[dict], fuente: dict) -> dict:
    u, p = grupo[-1], grupo[-2]
    _comprobar(u["interanual"], "inflacion", "inflación salud")
    serie = [{"etiqueta": _mes_texto(x["anio"], x["mes"], True), "valor": round(x["interanual"], 2)} for x in grupo[-13:]]
    return _tarjeta(
        "inflacion_salud", "Inflación salud", u["interanual"], 2, f"{_mes_texto(u['anio'], u['mes'])} · interanual",
        f"{MESES[p['mes'] - 1].capitalize()}: {_fmt(p['interanual'], 2)} · mensual: {_fmt(u['mensual'], 2)}",
        p["interanual"], serie, fuente,
        aclaracion="Grupo Salud del IPC (base 2019-2020); la variación interanual se calcula con el índice publicado.")


# ------------------------------------------------------------------ proceso

def _registro_estado(estado: dict, id_: str, nombre: str, url: str, ahora: datetime, error: str | None, conteo: dict | None) -> None:
    from .pipeline import _actualizar_estado

    _actualizar_estado(estado, {"id": id_, "nombre": nombre, "tipo": "datos_bcrd", "url": url, "categoria": "indicador"},
                       ahora, error, conteo)


def actualizar(guardar: bool = True) -> dict:
    cfg = yaml.safe_load(ARCHIVO_CONFIG.read_text(encoding="utf-8"))
    archivos = cfg["archivos"]
    ahora = ahora_rd()
    estado = almacen.cargar_estado()
    anterior = json.loads(ARCHIVO_SALIDA.read_text(encoding="utf-8")) if ARCHIVO_SALIDA.exists() else {}
    previas = {t["id"]: t for t in anterior.get("tarjetas", [])}

    lectores = {
        "ipc": (lambda f: leer_ipc(f), None),
        "ipc_grupos": (lambda f: leer_ipc_grupo(f, "salud"), None),
        "tpm": (lambda f: leer_tpm(f), None),
        "imae": (lambda f: leer_imae(f), None),
        "pib_sectores": (lambda f: leer_pib_sector(f, "salud"), "PIBK_Trim"),
    }
    series: dict[str, list] = {}
    errores: dict[str, str] = {}
    for clave, (lector, hoja) in lectores.items():
        info = archivos[clave]
        try:
            series[clave] = lector(descargar_filas(info["url"], hoja))
            _registro_estado(estado, f"bcrd_{clave}", f"BCRD · {info['nombre']}", info["url"], ahora, None,
                             {"leidos": len(series[clave]), "nuevos": 0, "repetidos": 0, "descartados": 0})
            print(f"  [ok] bcrd_{clave}: {len(series[clave])} períodos")
        except Exception as error:  # noqa: BLE001 - un archivo no detiene a los demás
            errores[clave] = f"{type(error).__name__}: {error}"
            _registro_estado(estado, f"bcrd_{clave}", f"BCRD · {info['nombre']}", info["url"], ahora, errores[clave], None)
            print(f"  [ERROR] bcrd_{clave}: {errores[clave]}")

    nota = None
    if cfg.get("notas_prensa", {}).get("activo"):
        try:
            for n in notas_prensa(cfg["notas_prensa"]):
                datos = titulo_nota_imae(n["titulo"])
                if datos:
                    nota = {"valor": datos[0], "mes": datos[1], "anio": datos[2], "fecha": n["fecha"],
                            "titulo": n["titulo"], "enlace": f"{cfg['notas_prensa']['url_articulo']}{n['id']}"}
                    break
            print(f"  [ok] notas de prensa: {'IMAE ' + _mes_texto(nota['anio'], nota['mes']) if nota else 'sin nota de IMAE reciente'}")
        except Exception as error:  # noqa: BLE001 - es un complemento; su fallo no afecta a los archivos
            print(f"  [aviso] notas de prensa no disponibles: {type(error).__name__}: {error}")

    def fuente(clave):
        return {"nombre": f"BCRD · {archivos[clave]['nombre']}", "archivo": archivos[clave]["url"], "pagina": archivos[clave]["pagina"]}

    constructores = {
        "inflacion_interanual": ("ipc", lambda: tarjetas_ipc(series["ipc"], cfg.get("meta_inflacion", ""), fuente("ipc"))[0]),
        "inflacion_acumulada": ("ipc", lambda: tarjetas_ipc(series["ipc"], cfg.get("meta_inflacion", ""), fuente("ipc"))[1]),
        "tpm": ("tpm", lambda: tarjeta_tpm(series["tpm"], fuente("tpm"))),
        "imae": ("imae", lambda: tarjeta_imae(series["imae"], nota, fuente("imae"))),
        "salud_actividad": ("pib_sectores", lambda: tarjeta_salud_actividad(series["pib_sectores"], fuente("pib_sectores"))),
        "inflacion_salud": ("ipc_grupos", lambda: tarjeta_inflacion_salud(series["ipc_grupos"], fuente("ipc_grupos"))),
    }
    tarjetas = []
    for id_ in cfg.get("orden", list(constructores)):
        clave, construir = constructores[id_]
        try:
            if clave not in series:
                raise ErrorIndicador(errores.get(clave, "archivo no disponible"))
            tarjeta = construir()
        except Exception as error:  # noqa: BLE001
            print(f"  [ERROR] tarjeta {id_}: {error}")
            if id_ in previas:
                tarjeta = {**previas[id_], "desactualizado": True}
            else:
                continue
        tarjetas.append(tarjeta)

    salida = {"actualizado": a_iso(ahora), "fuente": "Banco Central de la República Dominicana",
              "pagina_fuente": cfg.get("pagina_fuente"), "tarjetas": tarjetas, "errores": errores}
    if guardar:
        config.CARPETA_DATOS.mkdir(parents=True, exist_ok=True)
        ARCHIVO_SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        almacen.guardar_estado(estado)
    print(f"Indicadores: {len(tarjetas)} tarjetas, {len(errores)} archivos con error")
    return salida


def cargar() -> dict:
    if not ARCHIVO_SALIDA.exists():
        return {"tarjetas": []}
    return json.loads(ARCHIVO_SALIDA.read_text(encoding="utf-8"))
