"""Línea de comandos del radar.

    python -m radar recolectar [--fuente ID] [--sin-guardar]
    python -m radar reclasificar [--sin-guardar]
    python -m radar probar "Título de prueba"
    python -m radar estado
    python -m radar generar          (construye el sitio en docs/)
"""

from __future__ import annotations

import argparse
import json
import sys

from . import pipeline


def _principal(argumentos: list[str] | None = None) -> int:
    pipeline._configurar_salida()
    analizador = argparse.ArgumentParser(prog="radar", description="Radar Farma & Seguros RD")
    sub = analizador.add_subparsers(dest="comando", required=True)

    p_recolectar = sub.add_parser("recolectar", help="lee las fuentes, clasifica y guarda")
    p_recolectar.add_argument("--fuente", help="id de una sola fuente (ver config/fuentes.yaml)")
    p_recolectar.add_argument("--sin-guardar", action="store_true", help="no escribe datos/ (solo prueba)")

    p_reclasificar = sub.add_parser("reclasificar", help="vuelve a clasificar el historial con las reglas actuales")
    p_reclasificar.add_argument("--sin-guardar", action="store_true")

    p_probar = sub.add_parser("probar", help="muestra cómo se clasificaría un título")
    p_probar.add_argument("titulo")

    sub.add_parser("estado", help="muestra el estado de cada fuente")
    sub.add_parser("generar", help="construye el sitio estático en docs/")

    opciones = analizador.parse_args(argumentos)

    if opciones.comando == "recolectar":
        resumen = pipeline.recolectar(solo_fuente=opciones.fuente, guardar=not opciones.sin_guardar)
        return 0 if resumen["errores"] < max(1, len(resumen["fuentes"])) else 1
    if opciones.comando == "reclasificar":
        pipeline.reclasificar(guardar=not opciones.sin_guardar)
        return 0
    if opciones.comando == "probar":
        print(json.dumps(pipeline.probar(opciones.titulo), ensure_ascii=False, indent=2))
        return 0
    if opciones.comando == "estado":
        for fila in pipeline.estado_fuentes():
            marca = "ok   " if fila["estado"] == "ok" else "ERROR"
            if not fila["activa"]:
                marca = "inact"
            detalle = fila["mensaje_error"] or f"último éxito {fila['ultimo_exito']}"
            print(f"[{marca}] {fila['id']:<24} {fila['nombre']:<28} fallos={fila['fallos_consecutivos']}  {detalle}")
        return 0
    if opciones.comando == "generar":
        from . import generar_sitio

        generar_sitio.generar()
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(_principal())
