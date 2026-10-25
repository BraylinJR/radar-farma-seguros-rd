"""Pruebas del radar. Ejecutar con:  python -m unittest discover -s tests -v

No leen fuentes en internet ni escriben en datos/.
"""

import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar import avisos, config  # noqa: E402
from radar.clasificar import Clasificador, aplicar_correcciones  # noqa: E402
from radar.deduplicar import IndiceDuplicados  # noqa: E402
from radar.generar_sitio import incrustar_json  # noqa: E402
from radar.pipeline import _fecha_documento  # noqa: E402
from radar.recolectar import leer_html_documentos, leer_sitemap_noticias  # noqa: E402
from radar.utilidades import ZONA_RD, compilar_palabra, id_desde_url, normalizar_texto, normalizar_url  # noqa: E402


class PruebasUtilidades(unittest.TestCase):
    def test_palabra_sin_acentos_ni_mayusculas(self):
        patron = compilar_palabra("farmacéutica")
        self.assertTrue(patron.search(normalizar_texto("La FARMACEUTICA local")))

    def test_palabra_completa(self):
        patron = compilar_palabra("ARS")
        self.assertTrue(patron.search(normalizar_texto("Las ARS y el SFS")))
        self.assertFalse(patron.search(normalizar_texto("El Arsenal ganó")))

    def test_asterisco(self):
        patron = compilar_palabra("farmac*")
        for texto in ("farmacia", "farmacias", "farmacéutico"):
            self.assertTrue(patron.search(normalizar_texto(texto)), texto)

    def test_url_canonica(self):
        a = "https://www.ejemplo.com.do/nota/?utm_source=x&id=5"
        b = "http://ejemplo.com.do/nota?id=5"
        self.assertEqual(normalizar_url(a), normalizar_url(b))
        self.assertEqual(id_desde_url(a), id_desde_url(b))


class PruebasClasificacion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Clasificador(config.cargar_clasificacion())

    def test_alerta_sanitaria(self):
        r = self.c.clasificar("Digemaps retira del mercado lote de dexametasona por contaminación")
        self.assertEqual(r["tema"], "Alertas sanitarias")
        self.assertIn("DIGEMAPS", r["empresas"])
        self.assertIn("Regulación y gobierno", r["sectores"])

    def test_ars(self):
        r = self.c.clasificar("ARS Humano presenta nuevo plan de salud para pymes")
        self.assertIn("Seguros de salud (ARS)", r["sectores"])
        self.assertIn("ARS Humano", r["empresas"])

    def test_ruido_fuera_del_sector(self):
        self.assertEqual(self.c.clasificar("Banreservas anuncia resultados del trimestre")["sectores"], [])
        self.assertEqual(self.c.clasificar("Ministerio de Defensa garantiza seguridad en frontera")["sectores"], [])
        r = self.c.clasificar("Un terremoto de magnitud 7 sacude la región del Tíbet", ["terremoto", "sismo", "siniestro"])
        self.assertEqual(r["sectores"], [])

    def test_resumen_exige_dos_palabras(self):
        self.assertEqual(self.c.sectores_por_resumen("Habló de seguros en general."), [])
        self.assertIn("Seguros generales", self.c.sectores_por_resumen("Las aseguradoras subieron las primas de las pólizas."))

    def test_organismo(self):
        r = self.c.clasificar("Taller sobre salud mental", categoria="organismo", organismo_emisor="SISALRIL")
        self.assertEqual(r["sectores"][0] if r["sectores"] else None, "Regulación y gobierno")
        self.assertIn("SISALRIL", r["empresas"])

    def test_temas_existen(self):
        for nombre in ("Precios", "Regulación", "Lanzamientos", "Fusiones y adquisiciones",
                       "Resultados financieros", "Alertas sanitarias", "Otros"):
            self.assertIn(nombre, self.c.nombres_temas)


class PruebasCorrecciones(unittest.TestCase):
    def test_por_id_y_por_enlace(self):
        noticias = {
            "a1": {"id": "a1", "enlace": "https://x.do/1", "tema": "Otros", "sectores": ["Farmacia"], "empresas": []},
            "b2": {"id": "b2", "enlace": "https://x.do/2", "tema": "Otros", "sectores": ["Farmacia"], "empresas": []},
        }
        n = aplicar_correcciones(noticias, [{"id": "a1", "tema": "Precios"}, {"enlace": "https://www.x.do/2/", "excluir": True}])
        self.assertEqual(n, 2)
        self.assertEqual(noticias["a1"]["tema"], "Precios")
        self.assertTrue(noticias["b2"]["excluida"])
        self.assertTrue(noticias["a1"]["corregida"])


class PruebasFechasYDuplicados(unittest.TestCase):
    ahora = datetime(2026, 10, 23, 9, 0, tzinfo=ZONA_RD)

    def test_fecha_por_ruta_y_titulo(self):
        f, p = _fecha_documento("Circular 12-2026 Renovación", "https://sis.gob.do/wp-content/uploads/2026/01/c.pdf", self.ahora)
        self.assertEqual((f.year, f.month, p), (2026, 1, "mes"))

    def test_numero_que_no_es_anio(self):
        _, p = _fecha_documento("Comunicado 2066 Cobertura", "https://sis.gob.do/doc.pdf", self.ahora)
        self.assertEqual(p, "deteccion")

    def test_duplicado_por_titulo(self):
        base = {"x": {"id": "x", "titulo": "Sisalril incluye burnout y depresión en nuevo cuadro de enfermedades profesionales",
                      "fecha": "2026-10-20T10:00:00-04:00"}}
        indice = IndiceDuplicados(base)
        dia = datetime(2026, 10, 21).date()
        self.assertEqual(indice.buscar("Sisalril incluye el burnout y la depresión en nuevo cuadro de enfermedades profesionales", dia), "x")
        self.assertIsNone(indice.buscar("Pro Consumidor interviene comercios por irregularidades", dia))


class PruebasLectores(unittest.TestCase):
    def test_sitemap_noticias(self):
        xml = b"""<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
          <url><loc>https://medio.do/nota-1</loc><news:news><news:title><![CDATA[Farmacias bajan precios]]></news:title>
          <news:publication_date>2026-10-22T15:53:38-04:00</news:publication_date><news:keywords>farmacia, precios</news:keywords></news:news></url>
        </urlset>"""
        items = leer_sitemap_noticias(xml, {})
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["titulo"], "Farmacias bajan precios")
        self.assertEqual(items[0]["etiquetas"], ["farmacia", "precios"])
        self.assertEqual(items[0]["fecha"].day, 22)

    def test_documentos_con_texto_generico(self):
        html = b"""<a href="/wp-content/uploads/2026/01/Circular-12-2026-Inicio-de-Licencias.pdf">Click para descargar documento</a>
                   <a href="/wp-content/uploads/2026/01/Circular-12-2026-Inicio-de-Licencias.pdf">Descargar</a>
                   <a href="/otra-pagina/">Inicio</a>"""
        fuente = {"url": "https://sis.gob.do/", "patron_enlace": r"\.pdf$"}
        items = leer_html_documentos(html, fuente)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["titulo"], "Circular 12 2026 Inicio de Licencias")
        self.assertEqual(items[0]["tipo"], "documento")


class PruebasAvisos(unittest.TestCase):
    def test_abrir_al_tercer_fallo(self):
        estado = {"f1": {"activa": True, "fallos_consecutivos": 3, "estado": "error"},
                  "f2": {"activa": True, "fallos_consecutivos": 2, "estado": "error"}}
        acciones = avisos.decidir(estado, {})
        self.assertEqual([(a["accion"], a["fuente"]) for a in acciones], [("abrir", "f1")])

    def test_no_duplicar_issue(self):
        estado = {"f1": {"activa": True, "fallos_consecutivos": 5, "estado": "error"}}
        self.assertEqual(avisos.decidir(estado, {"f1": 7}), [])

    def test_cerrar_al_recuperarse_o_desactivarse(self):
        estado = {"f1": {"activa": True, "fallos_consecutivos": 0, "estado": "ok"},
                  "f2": {"activa": False, "fallos_consecutivos": 4, "estado": "error"}}
        acciones = avisos.decidir(estado, {"f1": 7, "f2": 8})
        self.assertEqual(sorted((a["accion"], a["issue"]) for a in acciones), [("cerrar", 7), ("cerrar", 8)])

    def test_marca_en_el_cuerpo(self):
        cuerpo = avisos.cuerpo_issue("eldia", {"nombre": "El Día", "fallos_consecutivos": 3})
        self.assertEqual(avisos.MARCA.search(cuerpo).group(1), "eldia")


class PruebasSitio(unittest.TestCase):
    def test_json_incrustado_seguro(self):
        texto = json.dumps({"titulo": "Ataque </script><script>alert(1)</script> <!-- x"})
        seguro = incrustar_json(texto)
        self.assertNotIn("<", seguro)
        self.assertNotIn(">", seguro)
        self.assertEqual(json.loads(seguro)["titulo"], "Ataque </script><script>alert(1)</script> <!-- x")


class PruebasPrioridad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Clasificador(config.cargar_clasificacion())

    def test_ley_con_numero_es_alta(self):
        r = self.c.clasificar("Senado aprueba modificación a la Ley 87-01 sobre seguridad social")
        self.assertEqual((r["prioridad"], r["motivo_prioridad"]), ("alta", "Menciona Ley 87-01"))
        r = self.c.clasificar("Gobierno someterá reforma a la Ley núm. 146-02 de Seguros y Fianzas")
        self.assertEqual(r["motivo_prioridad"], "Menciona Ley 146-02")

    def test_documento_con_anio_separado(self):
        r = self.c.clasificar("Resolucion 05 2026 Sobre cierre definitivo de la compania Seguros Cibao", categoria="organismo")
        self.assertEqual(r["prioridad"], "alta")
        self.assertIn("Resolución 05-2026", r["motivo_prioridad"])

    def test_comunicado_institucional_es_baja(self):
        r = self.c.clasificar("CNSS se une a campaña prevención Cáncer de Mama", categoria="organismo", organismo_emisor="CNSS")
        self.assertEqual(r["prioridad"], "baja")

    def test_medio_sin_actor_es_baja_pero_organismo_no(self):
        self.assertEqual(self.c.clasificar("Vacuna contra la tuberculosis muestra potencial frente a la demencia")["prioridad"], "baja")
        r = self.c.clasificar("Encuentro técnico sobre medicamentos", categoria="organismo", organismo_emisor="DIGEMAPS")
        self.assertNotEqual(r["motivo_prioridad"], "Sin empresa u organismo del mercado dominicano")

    def test_noticia_comun_es_media(self):
        self.assertEqual(self.c.clasificar("Farmacia Carol abre nueva sucursal en Santiago")["prioridad"], "media")


def _meses(desde_anio, n, valor):
    """Filas año/mes al estilo del BCRD: el año solo en enero."""
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    filas = []
    for k in range(n):
        anio, mes = desde_anio + k // 12, k % 12
        filas.append([str(anio) if mes == 0 else "", meses[mes], *valor(k)])
    return filas


class PruebasIndicadores(unittest.TestCase):
    def test_ipc(self):
        from radar.indicadores import leer_ipc, tarjetas_ipc
        filas = [["Índice de Precios"], ["Período", "", "Indice", "Variación Porcentual"], ["", "", "", "Mensual", "con Dic.", "12 meses", "12 meses"]]
        filas += _meses(2025, 21, lambda k: [100 + k, 0.3, 0.3 * (k % 12 + 1), 5.0 + k / 100, 4.0])
        serie = leer_ipc(filas)
        self.assertEqual((serie[-1]["anio"], serie[-1]["mes"]), (2026, 9))
        interanual, acumulada = tarjetas_ipc(serie, "Meta", {})
        self.assertEqual(interanual["texto_valor"], "5.20 %")
        self.assertEqual(interanual["direccion"], "sube")
        self.assertIn("Mismo período de 2025", acumulada["comparacion"])

    def test_ipc_grupo_calcula_interanual(self):
        from radar.indicadores import ErrorIndicador, leer_ipc_grupo
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        # formato del BCRD: el año en una fila aparte ("2024.0") y los meses debajo
        filas = [["Período", "Alimentos", "", "Salud"], ["", "Indice", "Var. %", "Indice"], ["2024.0"]]
        filas += [[m, "1", "-", 100.0] for m in meses]
        filas += [["2025.0"]] + [[m, "1", "-", 104.0] for m in meses]
        filas += [["2026.0"], ["Enero", "1", "-", 106.08]]
        serie = leer_ipc_grupo(filas, "salud")
        self.assertAlmostEqual(serie[-1]["interanual"], 2.0, places=6)   # 106.08 / 104 - 1
        self.assertAlmostEqual(serie[-2]["interanual"], 4.0, places=6)   # 104 / 100 - 1
        with self.assertRaises(ErrorIndicador):
            leer_ipc_grupo(filas[:20], "salud")  # sin un año completo de base: muy pocas filas

    def test_tpm_en_fraccion_y_desde_cuando(self):
        from radar.indicadores import leer_tpm, tarjeta_tpm
        filas = [["Tasas de Política Monetaria"], ["Año", "Mes", "Tasa de Política Monetaria"]]
        tasas = [0.0525] * 20 + [0.055]
        abreviados = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        for k, t in enumerate(tasas):
            filas.append([str(2025 + k // 12) if k % 12 == 0 else "", abreviados[k % 12], t])
        t = tarjeta_tpm(leer_tpm(filas), {})
        self.assertEqual(t["texto_valor"], "5.50 %")
        self.assertEqual(t["direccion"], "sube")
        self.assertEqual(t["periodo"], "vigente desde septiembre 2026")
        self.assertIn("Antes: 5.25 %", t["comparacion"])

    def test_pib_sector_interanual(self):
        from radar.indicadores import leer_pib_sector
        anios = ["INDICE", "2024", "", "", "", "2025 (p)", "", "", "", "2026 (p)", ""]
        trims = ["", "E-M", "A-J", "J-S", "O-D", "E-M", "A-J", "J-S", "O-D", "E-M", "A-J"]
        salud = ["Salud", 100, 100, 100, 100, 104, 105, 106, 107, 110.24, 109.2]
        serie = leer_pib_sector([["PIB"], anios, trims, ["Agropecuario"] + [1] * 10, salud], "salud")
        self.assertAlmostEqual(serie[-1]["interanual"], 4.0, places=6)
        self.assertTrue(serie[-1]["preliminar"])
        self.assertEqual((serie[-1]["anio"], serie[-1]["trimestre"]), (2026, 2))

    def test_titulo_nota_imae(self):
        from radar.indicadores import titulo_nota_imae
        self.assertEqual(titulo_nota_imae("Valdez Albizu anunció que la economía dominicana creció 5.6 % interanual en septiembre 2026"), (5.6, 9, 2026))
        self.assertEqual(titulo_nota_imae("Economía dominicana registra expansión de 6.4 % en junio 2026"), (6.4, 6, 2026))
        self.assertIsNone(titulo_nota_imae("Economía dominicana registra crecimiento interanual promedio de 4.5 % en enero-agosto de 2026"))
        self.assertIsNone(titulo_nota_imae("BCRD informa que la variación mensual del IPC de septiembre fue de 0.33 %"))

    def test_fuera_de_rango_es_error(self):
        from radar.indicadores import ErrorIndicador, _comprobar
        with self.assertRaises(ErrorIndicador):
            _comprobar(512.0, "inflacion", "prueba")


class PruebasConfiguracion(unittest.TestCase):
    def test_fuentes_validas(self):
        fuentes = config.cargar_fuentes(solo_activas=False)
        self.assertGreater(len(fuentes), 0)
        for f in fuentes:
            self.assertTrue(f["url"].startswith("https://"), f["id"])

    def test_empresas_con_sector_conocido(self):
        datos = config.cargar_clasificacion()
        sectores = set(datos["sectores"])
        for empresa in datos["empresas"]:
            self.assertIn(empresa["sector"], sectores, empresa["nombre"])


if __name__ == "__main__":
    unittest.main()
