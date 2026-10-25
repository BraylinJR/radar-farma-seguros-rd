"""Avisos automáticos en GitHub cuando una fuente falla varias veces seguidas.

- Si una fuente activa acumula UMBRAL_FALLOS fallos consecutivos y no tiene un issue
  abierto, se crea uno (con la etiqueta ETIQUETA) y se asigna al dueño del repositorio,
  para que GitHub le envíe un correo.
- Si la fuente vuelve a funcionar y tiene un issue abierto, se comenta y se cierra.

Se ejecuta en GitHub Actions con las variables GITHUB_TOKEN, GITHUB_REPOSITORY y
GITHUB_REPOSITORY_OWNER. En local, `python -m radar avisos --simular` muestra qué haría
sin llamar a GitHub.
"""

from __future__ import annotations

import os
import re

import requests

from . import almacen

UMBRAL_FALLOS = 3
ETIQUETA = "fuente-caida"
API = "https://api.github.com"
MARCA = re.compile(r"<!--\s*radar-fuente:([\w\-]+)\s*-->")


def decidir(estado: dict[str, dict], issues_abiertos: dict[str, int]) -> list[dict]:
    """Calcula las acciones a tomar. Función pura (fácil de probar).

    estado:           contenido de datos/estado_fuentes.json
    issues_abiertos:  {id_fuente: número_de_issue} de los issues abiertos con la etiqueta
    Devuelve una lista de {"accion": "abrir"|"cerrar", "fuente": id, ...}.
    """
    acciones = []
    for id_fuente, registro in sorted(estado.items()):
        activa = registro.get("activa", True)
        fallos = int(registro.get("fallos_consecutivos", 0))
        abierto = issues_abiertos.get(id_fuente)
        if activa and fallos >= UMBRAL_FALLOS and abierto is None:
            acciones.append({"accion": "abrir", "fuente": id_fuente, "registro": registro})
        elif abierto is not None and (registro.get("estado") == "ok" or not activa):
            motivo = "volvió a funcionar" if activa else "fue desactivada en la configuración"
            acciones.append({"accion": "cerrar", "fuente": id_fuente, "issue": abierto, "motivo": motivo, "registro": registro})
    return acciones


def titulo_issue(id_fuente: str, registro: dict) -> str:
    return f"Fuente con fallos: {registro.get('nombre', id_fuente)} ({id_fuente})"


def cuerpo_issue(id_fuente: str, registro: dict) -> str:
    return "\n".join([
        f"<!-- radar-fuente:{id_fuente} -->",
        f"La fuente **{registro.get('nombre', id_fuente)}** (`{id_fuente}`) falló "
        f"{registro.get('fallos_consecutivos')} veces seguidas.",
        "",
        f"- URL: {registro.get('url')}",
        f"- Tipo: {registro.get('tipo')}",
        f"- Último error: {registro.get('ultimo_error')}",
        f"- Mensaje: `{registro.get('mensaje_error')}`",
        f"- Último éxito: {registro.get('ultimo_exito') or 'nunca'}",
        "",
        "Las demás fuentes siguen funcionando con normalidad.",
        "",
        "Qué hacer (ver la sección *Qué hacer si una fuente deja de funcionar* del README):",
        "1. Abrir la URL en el navegador y comprobar si cambió de dirección o dejó de existir.",
        "2. Si cambió, actualizar `url` en `config/fuentes.yaml`.",
        "3. Si ya no se puede leer de forma legítima, poner `activa: false` y anotar el motivo en `nota`.",
        "",
        "Este issue se cierra solo cuando la fuente vuelva a funcionar.",
    ])


class ClienteGitHub:
    def __init__(self, token: str, repositorio: str) -> None:
        self.repositorio = repositorio
        self.sesion = requests.Session()
        self.sesion.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "radar-farma-seguros-rd",
        })

    def _url(self, ruta: str) -> str:
        return f"{API}/repos/{self.repositorio}{ruta}"

    def asegurar_etiqueta(self) -> None:
        respuesta = self.sesion.post(self._url("/labels"), json={
            "name": ETIQUETA, "color": "d03b3b", "description": "Una fuente del radar falla de forma repetida",
        }, timeout=30)
        if respuesta.status_code not in (201, 422):  # 422 = ya existe
            respuesta.raise_for_status()

    def issues_abiertos(self) -> dict[str, int]:
        encontrados: dict[str, int] = {}
        pagina = 1
        while True:
            respuesta = self.sesion.get(self._url("/issues"), params={
                "state": "open", "labels": ETIQUETA, "per_page": 100, "page": pagina,
            }, timeout=30)
            respuesta.raise_for_status()
            lote = respuesta.json()
            for issue in lote:
                marca = MARCA.search(issue.get("body") or "")
                if marca:
                    encontrados[marca.group(1)] = issue["number"]
            if len(lote) < 100:
                return encontrados
            pagina += 1

    def abrir(self, id_fuente: str, registro: dict, asignado: str | None) -> int:
        datos = {"title": titulo_issue(id_fuente, registro), "body": cuerpo_issue(id_fuente, registro), "labels": [ETIQUETA]}
        if asignado:
            datos["assignees"] = [asignado]
        respuesta = self.sesion.post(self._url("/issues"), json=datos, timeout=30)
        if respuesta.status_code == 422 and asignado:  # asignación no válida: crear sin asignar
            datos.pop("assignees")
            respuesta = self.sesion.post(self._url("/issues"), json=datos, timeout=30)
        respuesta.raise_for_status()
        return respuesta.json()["number"]

    def cerrar(self, numero: int, mensaje: str) -> None:
        self.sesion.post(self._url(f"/issues/{numero}/comments"), json={"body": mensaje}, timeout=30).raise_for_status()
        self.sesion.patch(self._url(f"/issues/{numero}"), json={"state": "closed", "state_reason": "completed"}, timeout=30).raise_for_status()


def ejecutar(simular: bool = False) -> list[dict]:
    estado = almacen.cargar_estado()
    token = os.environ.get("GITHUB_TOKEN")
    repositorio = os.environ.get("GITHUB_REPOSITORY")
    asignado = os.environ.get("GITHUB_REPOSITORY_OWNER")

    if simular or not (token and repositorio):
        if not simular:
            print("Avisos: faltan GITHUB_TOKEN o GITHUB_REPOSITORY; se muestra la simulación.")
        acciones = decidir(estado, {})
        for accion in acciones:
            if accion["accion"] == "abrir":
                print(f"[simulación] abriría issue: {titulo_issue(accion['fuente'], accion['registro'])}")
        if not acciones:
            print(f"[simulación] ninguna fuente activa con {UMBRAL_FALLOS} o más fallos seguidos")
        return acciones

    cliente = ClienteGitHub(token, repositorio)
    cliente.asegurar_etiqueta()
    acciones = decidir(estado, cliente.issues_abiertos())
    for accion in acciones:
        if accion["accion"] == "abrir":
            numero = cliente.abrir(accion["fuente"], accion["registro"], asignado)
            print(f"Avisos: abierto el issue #{numero} para {accion['fuente']}")
        else:
            cliente.cerrar(accion["issue"], f"La fuente `{accion['fuente']}` {accion['motivo']}. Se cierra automáticamente.")
            print(f"Avisos: cerrado el issue #{accion['issue']} de {accion['fuente']} ({accion['motivo']})")
    if not acciones:
        print("Avisos: sin cambios")
    return acciones
