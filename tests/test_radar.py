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
