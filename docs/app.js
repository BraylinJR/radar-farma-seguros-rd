/* Radar Farma & Seguros RD: lógica de la página. Sin dependencias externas. */
(function () {
  "use strict";

  const DATOS = JSON.parse(document.getElementById("radar-datos").textContent);
  const ITEMS = DATOS.items;
  const SECTORES = DATOS.sectores;
  const TEMAS = DATOS.temas;
  const MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const PAGINA = 40;
  const SEMANAS = 12;
  const DIAS_MES = 30;
  const ICONO_TEMA = {
    "Alertas sanitarias": "t-alertas", "Fusiones y adquisiciones": "t-fusiones", "Resultados financieros": "t-resultados",
    "Precios": "t-precios", "Regulación": "t-regulacion", "Lanzamientos": "t-lanzamientos", "Otros": "t-otros",
  };
  const ICONO_INDICADOR = {
    inflacion_interanual: "ind-inflacion", inflacion_acumulada: "ind-acumulada", tpm: "ind-tpm",
    imae: "ind-imae", salud_actividad: "ind-salud", inflacion_salud: "ind-pastilla",
  };
  const TEXTO_PRIORIDAD = { alta: "Alta", media: "Media", baja: "Baja" };

  // ---------------------------------------------------------- utilidades
  const $ = (id) => document.getElementById(id);
  function escapar(texto) {
    return String(texto ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function normalizar(texto) {
    return String(texto ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }
  const diaDe = (iso) => iso.slice(0, 10);
  function fechaUTC(dia) { const [a, m, d] = dia.split("-").map(Number); return new Date(Date.UTC(a, m - 1, d)); }
  const diaDesdeUTC = (f) => f.toISOString().slice(0, 10);
  function sumarDias(dia, n) { const f = fechaUTC(dia); f.setUTCDate(f.getUTCDate() + n); return diaDesdeUTC(f); }
  function inicioSemana(dia) { const f = fechaUTC(dia); f.setUTCDate(f.getUTCDate() - ((f.getUTCDay() + 6) % 7)); return diaDesdeUTC(f); }
  function textoDia(dia, conAnio) { const [a, m, d] = dia.split("-").map(Number); return `${d} ${MESES_CORTOS[m - 1]}${conAnio ? " " + a : ""}`; }
  function textoFechaItem(item) {
    const dia = diaDe(item.fecha);
    const [a, m] = dia.split("-").map(Number);
    switch (item.precision) {
      case "mes": return `${MESES_CORTOS[m - 1]} ${a}`;
      case "anio": return `${a}`;
      case "deteccion": return `detectado el ${textoDia(dia, true)}`;
      default: return textoDia(dia, true);
    }
  }
  function tiempoRelativo(iso) {
    if (!iso) return "sin datos";
    const minutos = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
    if (minutos < 2) return "hace un momento";
    if (minutos < 60) return `hace ${minutos} min`;
    const horas = Math.round(minutos / 60);
    if (horas < 48) return `hace ${horas} h`;
    return `hace ${Math.round(horas / 24)} días`;
  }
  const indiceTema = (tema) => { const i = TEMAS.indexOf(tema); return (i < 0 ? TEMAS.length - 1 : i) + 1; };
  const colorTema = (tema) => `var(--serie-${Math.min(indiceTema(tema), 7)})`;
  const plural = (n, s, p) => `${Number(n).toLocaleString("es-DO")} ${n === 1 ? s : p}`;
  const HOY = diaDe(DATOS.meta.generado);

  // ------------------------------------------------------------ tema visual
  const raiz = document.documentElement;
  const consultaOscuro = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  function temaEfectivo() {
    const t = raiz.getAttribute("data-theme");
    if (t === "light" || t === "dark") return t;
    return consultaOscuro && consultaOscuro.matches ? "dark" : "light";
  }
  function actualizarBotonTema() {
    $("tema-boton").setAttribute("aria-label", temaEfectivo() === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro");
  }
  $("tema-boton").addEventListener("click", () => {
    const nuevo = temaEfectivo() === "dark" ? "light" : "dark";
    raiz.setAttribute("data-theme", nuevo);
    try { localStorage.setItem("radar-tema", nuevo); } catch (e) { /* sin almacenamiento: solo esta visita */ }
    actualizarBotonTema();
  });
  if (consultaOscuro && consultaOscuro.addEventListener) consultaOscuro.addEventListener("change", actualizarBotonTema);
  actualizarBotonTema();

  // ------------------------------------------------------------ piezas comunes
  function mosaico(tema, clase) {
    return `<span class="mosaico ${clase || ""} tema-${indiceTema(tema)}" aria-hidden="true"><svg><use href="#${ICONO_TEMA[tema] || "t-otros"}"/></svg></span>`;
  }
  function insigniaPrioridad(p) {
    const icono = p === "alta" ? '<svg aria-hidden="true"><use href="#i-rayo"/></svg>' : "";
    return `<span class="prioridad ${p}">${icono}Prioridad ${TEXTO_PRIORIDAD[p] || p}</span>`;
  }
  function enlace(item) {
    return `<a href="${escapar(item.enlace)}" target="_blank" rel="noopener noreferrer">${escapar(item.titulo)}</a>`;
  }
  function chips(item, opciones) {
    const o = opciones || {};
    const partes = [];
    if (o.tipo && item.tipo === "documento") partes.push(`<span class="chip"><svg aria-hidden="true"><use href="#i-documento"/></svg>Documento</span>`);
    partes.push(`<span class="chip"><span class="punto" style="background:${colorTema(item.tema)}"></span>${escapar(item.tema)}</span>`);
    if (o.sectores !== false) for (const s of item.sectores) partes.push(`<span class="chip">${escapar(s)}</span>`);
    for (const e of item.empresas) {
      if (o.sinEmisor && item.categoria === "organismo" && e === item.medio) continue;
      partes.push(`<span class="chip chip-empresa">${escapar(e)}</span>`);
    }
    return `<div class="chips">${partes.join("")}</div>`;
  }

  // ------------------------------------------------------------ cabecera
  function renderCifras() {
    const r = DATOS.resumen_semanal;
    const desde = sumarDias(HOY, -DIAS_MES);
    const alta30 = ITEMS.filter((i) => i.prioridad === "alta" && diaDe(i.fecha) >= desde).length;
    const fuentes = DATOS.fuentes.filter((f) => f.activa);
    const ok = fuentes.filter((f) => f.estado === "ok").length;
    $("cifras").innerHTML = [
      { v: r.total, e: "titulares en 7 días" },
      { v: alta30, e: "de prioridad alta en 30 días", c: "alta" },
      { v: DATOS.metodologia.medios.length, e: "medios monitoreados" },
      { v: `${ok}/${fuentes.length}`, e: "fuentes funcionando" },
    ].map((x) => `<div class="cifra ${x.c || ""}"><div class="valor">${escapar(x.v)}</div><div class="etiqueta">${x.e}</div></div>`).join("");
  }

  // ------------------------------------------------------------ indicadores
  function sparkline(serie) {
    if (!serie || serie.length < 2) return "";
    const valores = serie.map((p) => p.valor);
    const min = Math.min(...valores), max = Math.max(...valores);
    const ancho = 100, alto = 28, pad = 3;
    const x = (i) => pad + (i * (ancho - 2 * pad)) / (serie.length - 1);
    const y = (v) => (max === min ? alto / 2 : alto - pad - ((v - min) / (max - min)) * (alto - 2 * pad));
    const puntos = serie.map((p, i) => `${x(i).toFixed(1)},${y(p.valor).toFixed(1)}`).join(" ");
    const ultimo = serie[serie.length - 1];
    const area = `M${x(0).toFixed(1)},${alto} L${puntos.split(" ").join(" L")} L${x(serie.length - 1).toFixed(1)},${alto} Z`;
    const descripcion = serie.map((p) => `${p.etiqueta}: ${p.valor}`).join(", ");
    return `<svg class="spark" viewBox="0 0 ${ancho} ${alto}" preserveAspectRatio="none" role="img" aria-label="Evolución reciente: ${escapar(descripcion)}">
      <path d="${area}" fill="currentColor" opacity="0.10"/>
      <polyline points="${puntos}" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>
      <circle cx="${x(serie.length - 1).toFixed(1)}" cy="${y(ultimo.valor).toFixed(1)}" r="2.6" fill="currentColor" vector-effect="non-scaling-stroke"/>
    </svg>`;
  }

  function renderIndicadores() {
    const ind = DATOS.indicadores || {};
    const tarjetas = ind.tarjetas || [];
    const lista = $("lista-indicadores");
    if (!tarjetas.length) {
      lista.innerHTML = `<p class="vacio" style="grid-column:1/-1">Los indicadores se cargarán en la próxima actualización.</p>`;
      return;
    }
    const flechas = { sube: "▲", baja: "▼", igual: "●" };
    const textos = { sube: "subió", baja: "bajó", igual: "sin cambio" };
    lista.innerHTML = tarjetas.map((t) => `
      <article class="ind" data-id="${escapar(t.id)}">
        <div class="ind-top">
          <span class="ind-ico" aria-hidden="true"><svg><use href="#${ICONO_INDICADOR[t.id] || "ind-imae"}"/></svg></span>
          <h3 class="ind-nombre">${escapar(t.nombre)}</h3>
        </div>
        <div class="ind-valor"><span class="flecha" aria-hidden="true">${flechas[t.direccion] || "●"}</span><span>${escapar(t.texto_valor)}</span><span class="sr">, ${textos[t.direccion] || ""} respecto de la comparación</span></div>
        <div class="ind-periodo">${escapar(t.periodo)}</div>
        ${sparkline(t.serie)}
        <div class="ind-comp">${escapar(t.comparacion)}</div>
        ${t.desactualizado ? '<div class="ind-desactualizado">Dato anterior: la última lectura falló</div>' : ""}
        ${t.aclaracion ? `<button type="button" class="ind-info" aria-expanded="false" aria-label="Aclaración sobre ${escapar(t.nombre)}"><svg aria-hidden="true"><use href="#i-info"/></svg></button><p class="ind-aclaracion" hidden>${escapar(t.aclaracion)}</p>` : ""}
        <a class="ind-fuente" href="${escapar((t.fuente && (t.fuente.nota || t.fuente.pagina)) || "#")}" target="_blank" rel="noopener noreferrer">Ver fuente</a>
      </article>`).join("");
    lista.querySelectorAll(".ind-info").forEach((boton) => boton.addEventListener("click", () => {
      const texto = boton.nextElementSibling;
      const abierto = boton.getAttribute("aria-expanded") === "true";
      boton.setAttribute("aria-expanded", String(!abierto));
      texto.hidden = abierto;
    }));
    if (ind.actualizado) {
      $("indicadores-fuente").textContent = `Fuente: Banco Central de la República Dominicana · leído ${tiempoRelativo(ind.actualizado)}`;
    }
  }

  // ------------------------------------------------------------ prioridad alta
  function renderAlta() {
    const desde = sumarDias(HOY, -DIAS_MES);
    let lista = ITEMS.filter((i) => i.prioridad === "alta" && diaDe(i.fecha) >= desde);
    let nota = "";
    if (!lista.length) {
      lista = ITEMS.filter((i) => i.prioridad === "alta").slice(0, 6);
      nota = lista.length ? "No hubo publicaciones de prioridad alta en los últimos 30 días; se muestran las más recientes." : "";
    }
    const contenedor = $("lista-alta");
    if (!lista.length) {
      contenedor.innerHTML = `<li class="vacio">Todavía no hay publicaciones de prioridad alta.</li>`;
      return;
    }
    contenedor.innerHTML = (nota ? `<li class="detalle" style="grid-column:1/-1">${nota}</li>` : "") + lista.slice(0, 9).map((i) => `
      <li class="tarjeta-alta">
        ${mosaico(i.tema, "grande")}
        <div class="cuerpo">
          <div class="cabeza">${insigniaPrioridad("alta")}<span class="motivo">${escapar(i.motivo)}</span></div>
          <h3>${enlace(i)}</h3>
          <div class="meta"><span class="medio">${escapar(i.medio)}</span><span>${escapar(textoFechaItem(i))}</span><span>${i.categoria === "organismo" ? "organismo" : "medio"}</span></div>
        </div>
      </li>`).join("");
  }

  // ------------------------------------------------------------ regulación
  let organismoElegido = "";
  function renderRegulacion() {
    const base = ITEMS.filter((i) => i.categoria === "organismo" && i.prioridad !== "baja");
    const organismos = [...new Set(base.map((i) => i.medio))].sort((a, b) => a.localeCompare(b, "es"));
    $("filtro-organismos").innerHTML = ["", ...organismos].map((o) =>
      `<button type="button" class="chip-filtro" data-organismo="${escapar(o)}" aria-pressed="${o === organismoElegido}">${o ? escapar(o) : "Todos"}</button>`).join("");
    $("filtro-organismos").querySelectorAll(".chip-filtro").forEach((b) => b.addEventListener("click", () => {
      organismoElegido = b.dataset.organismo;
      renderRegulacion();
    }));
    const lista = base.filter((i) => !organismoElegido || i.medio === organismoElegido).slice(0, 8);
    $("lista-regulacion").innerHTML = lista.length ? lista.map((i) => `
      <li class="tarjeta">
        <div class="cabeza">${mosaico(i.tema)}<div><div class="organismo">${escapar(i.medio)}</div><div class="fecha">${escapar(textoFechaItem(i))}${i.tipo === "documento" ? " · documento" : ""}</div></div></div>
        <h3>${enlace(i)}</h3>
        <div>${insigniaPrioridad(i.prioridad)}</div>
        ${chips(i, { sectores: false, sinEmisor: true })}
      </li>`).join("") : `<li class="vacio">Sin publicaciones para este organismo.</li>`;
  }

  // ------------------------------------------------------------ filtros
  const estado = { categoria: "medio", texto: [], sector: "", tema: "", empresa: "", desde: "", hasta: "", prioridades: new Set(["alta", "media"]), mostrados: PAGINA };

  function llenarSelect(id, valores, textoDe) {
    const select = $(id);
    for (const v of valores) {
      const opcion = document.createElement("option");
      opcion.value = Array.isArray(v) ? v[0] : v;
      opcion.textContent = textoDe ? textoDe(v) : v;
      select.appendChild(opcion);
    }
  }
  function prepararFiltros() {
    llenarSelect("f-sector", SECTORES);
    llenarSelect("f-tema", TEMAS);
    const conteo = new Map();
    for (const i of ITEMS) for (const e of i.empresas) conteo.set(e, (conteo.get(e) || 0) + 1);
    llenarSelect("f-empresa", [...conteo.entries()].sort((a, b) => a[0].localeCompare(b[0], "es")), (v) => `${v[0]} (${v[1]})`);

    const leer = () => {
      const marcado = document.querySelector('input[name="f-categoria"]:checked');
      estado.categoria = marcado ? marcado.value : "";
      estado.texto = normalizar($("f-texto").value).split(/\s+/).filter(Boolean);
      estado.sector = $("f-sector").value;
      estado.tema = $("f-tema").value;
      estado.empresa = $("f-empresa").value;
      estado.desde = $("f-desde").value;
      estado.hasta = $("f-hasta").value;
      estado.prioridades = new Set([...document.querySelectorAll('input[name="f-prioridad"]:checked')].map((c) => c.value));
      estado.mostrados = PAGINA;
      renderLista();
      renderGrafico();
    };
    const formulario = $("filtros");
    formulario.addEventListener("input", leer);
    formulario.addEventListener("change", leer);
    formulario.addEventListener("submit", (ev) => ev.preventDefault());
    formulario.addEventListener("reset", () => setTimeout(leer, 0));
    $("mostrar-mas").addEventListener("click", () => { estado.mostrados += PAGINA; renderLista(); });
    return leer;
  }
  function pasaSinFecha(i) {
    if (estado.categoria && i.categoria !== estado.categoria) return false;
    if (!estado.prioridades.has(i.prioridad)) return false;
    if (estado.sector && !i.sectores.includes(estado.sector)) return false;
    if (estado.tema && i.tema !== estado.tema) return false;
    if (estado.empresa && !i.empresas.includes(estado.empresa)) return false;
    if (estado.texto.length) {
      // búsqueda objetiva: todas las palabras deben aparecer, sin importar acentos ni mayúsculas
      const pajar = normalizar([i.titulo, i.medio, i.tema, i.motivo, ...i.sectores, ...i.empresas].join(" "));
      if (!estado.texto.every((palabra) => pajar.includes(palabra))) return false;
    }
    return true;
  }
  function pasa(i) {
    if (!pasaSinFecha(i)) return false;
    const dia = diaDe(i.fecha);
    return !(estado.desde && dia < estado.desde) && !(estado.hasta && dia > estado.hasta);
  }

  // ------------------------------------------------------------ lista
  function renderLista() {
    const filtrados = ITEMS.filter(pasa);
    const visibles = filtrados.slice(0, estado.mostrados);
    const tipo = estado.categoria === "medio" ? "de medios" : estado.categoria === "organismo" ? "de organismos" : "";
    $("conteo").textContent = `${plural(filtrados.length, "titular", "titulares")} ${tipo}, del más reciente al más antiguo`;
    $("lista-noticias").innerHTML = filtrados.length ? visibles.map((i) => `
      <li class="noticia ${i.prioridad === "alta" ? "es-alta" : ""}">
        ${mosaico(i.tema)}
        <div class="cuerpo">
          <div class="cabeza"><span class="medio">${escapar(i.medio)}</span><span>${escapar(textoFechaItem(i))}</span>${insigniaPrioridad(i.prioridad)}${i.prioridad === "alta" ? `<span class="motivo">${escapar(i.motivo)}</span>` : ""}</div>
          <h3>${enlace(i)}</h3>
          ${chips(i, { tipo: true, sinEmisor: true })}
          ${i.tambien_en.length ? `<div class="tambien">También en: ${i.tambien_en.map((t) => `<a href="${escapar(t.enlace)}" target="_blank" rel="noopener noreferrer">${escapar(t.medio)}</a>`).join(", ")}</div>` : ""}
        </div>
      </li>`).join("") : `<li class="vacio">Ningún titular coincide con los filtros. Prueba con “Todo” o marca también la prioridad baja.</li>`;
    $("mostrar-mas").hidden = visibles.length >= filtrados.length;
    $("mostrar-mas").textContent = `Mostrar más (${filtrados.length - visibles.length} restantes)`;
  }

  // ------------------------------------------------------------ gráfico
  function datosSemanas() {
    const base = ITEMS.filter(pasaSinFecha);
    const actual = inicioSemana(HOY);
    const semanas = [];
    for (let k = SEMANAS - 1; k >= 0; k--) {
      const inicio = sumarDias(actual, -7 * k);
      semanas.push({ inicio, fin: sumarDias(inicio, 6), porTema: Object.fromEntries(TEMAS.map((t) => [t, 0])), total: 0 });
    }
    const indice = new Map(semanas.map((s, n) => [s.inicio, n]));
    for (const i of base) {
      const n = indice.get(inicioSemana(diaDe(i.fecha)));
      if (n === undefined) continue;
      const tema = TEMAS.includes(i.tema) ? i.tema : TEMAS[TEMAS.length - 1];
      semanas[n].porTema[tema] += 1;
      semanas[n].total += 1;
    }
    return semanas;
  }
  function ticks(maximo) {
    if (maximo <= 0) return [0, 1];
    const bruto = maximo / 4;
    const potencia = Math.pow(10, Math.floor(Math.log10(bruto)));
    const paso = [1, 2, 5, 10].map((m) => m * potencia).find((p) => maximo / p <= 4) || potencia * 10;
    const salida = [];
    for (let v = 0; v <= Math.ceil(maximo / paso) * paso; v += paso) salida.push(v);
    return salida;
  }
  function renderGrafico() {
    const semanas = datosSemanas();
    const presentes = TEMAS.filter((t) => semanas.some((s) => s.porTema[t] > 0));
    $("leyenda-grafico").innerHTML = (presentes.length ? presentes : TEMAS).map((t) =>
      `<span class="clave"><span class="muestra" style="background:${colorTema(t)}"></span>${escapar(t)}</span>`).join("");
    const contenedor = $("grafico-semanas");
    const ANCHO = Math.max(300, Math.round(contenedor.clientWidth || 720));
    const ALTO = ANCHO < 480 ? 220 : 270, IZQ = 34, DER = 8, ARRIBA = 20, ABAJO = 28, GAP = 2;
    const anchoPlano = ANCHO - IZQ - DER, altoPlano = ALTO - ARRIBA - ABAJO;
    const ranura = anchoPlano / SEMANAS;
    const anchoBarra = Math.min(24, Math.floor(ranura * 0.6));
    const salto = ranura < 44 ? 2 : 1;
    const maximo = Math.max(...semanas.map((s) => s.total));
    const marcas = ticks(maximo);
    const tope = marcas[marcas.length - 1];
    const y = (v) => ARRIBA + altoPlano - (v / tope) * altoPlano;
    let svg = `<svg viewBox="0 0 ${ANCHO} ${ALTO}" role="img" aria-label="Columnas apiladas de titulares por semana y tema">`;
    for (const t of marcas) {
      svg += `<line class="rejilla" x1="${IZQ}" x2="${ANCHO - DER}" y1="${y(t)}" y2="${y(t)}"/><text class="eje-texto" x="${IZQ - 6}" y="${y(t) + 4}" text-anchor="end">${t}</text>`;
    }
    svg += `<line class="base" x1="${IZQ}" x2="${ANCHO - DER}" y1="${y(0)}" y2="${y(0)}"/>`;
    semanas.forEach((s, n) => {
      const cx = IZQ + ranura * n + ranura / 2, x0 = cx - anchoBarra / 2;
      let acumulado = 0;
      const temas = TEMAS.filter((t) => s.porTema[t] > 0);
      temas.forEach((t, k) => {
        const v = s.porTema[t];
        const cima = k === temas.length - 1;
        const top = y(acumulado + v) + (cima ? 0 : GAP / 2), bottom = y(acumulado) - (k === 0 ? 0 : GAP / 2);
        const h = Math.max(0, bottom - top);
        if (h > 0) {
          if (cima && h >= 4) {
            const r = 4;
            svg += `<path fill="${colorTema(t)}" d="M${x0},${bottom} V${top + r} a${r},${r} 0 0 1 ${r},-${r} H${x0 + anchoBarra - r} a${r},${r} 0 0 1 ${r},${r} V${bottom} Z"/>`;
          } else {
            svg += `<rect fill="${colorTema(t)}" x="${x0}" y="${top}" width="${anchoBarra}" height="${h}"/>`;
          }
        }
        acumulado += v;
      });
      if (s.total > 0 && (n === SEMANAS - 1 || s.total === maximo)) svg += `<text class="valor-cima" x="${cx}" y="${y(s.total) - 6}" text-anchor="middle">${s.total}</text>`;
      if ((SEMANAS - 1 - n) % salto === 0) svg += `<text class="eje-texto" x="${cx}" y="${ALTO - 8}" text-anchor="middle">${textoDia(s.inicio)}</text>`;
      svg += `<rect class="columna-zona" data-semana="${n}" tabindex="0" x="${IZQ + ranura * n}" y="${ARRIBA}" width="${ranura}" height="${altoPlano}"><title>Semana del ${textoDia(s.inicio)}: ${s.total}</title></rect>`;
    });
    svg += `</svg><div class="tooltip" id="tooltip" hidden></div>`;
    contenedor.innerHTML = svg;
    const tooltip = $("tooltip");
    const mostrar = (zona) => {
      const s = semanas[Number(zona.dataset.semana)];
      const filas = TEMAS.filter((t) => s.porTema[t] > 0).map((t) =>
        `<div class="fila"><span class="nombre"><span class="muestra" style="background:${colorTema(t)}"></span>${escapar(t)}</span><span>${s.porTema[t]}</span></div>`).join("");
      tooltip.innerHTML = `<div class="titulo">Semana del ${textoDia(s.inicio, true)} al ${textoDia(s.fin, true)}</div>${filas || '<div class="fila"><span>Sin titulares</span></div>'}<div class="fila"><span><strong>Total</strong></span><span><strong>${s.total}</strong></span></div>`;
      tooltip.hidden = false;
      const caja = contenedor.getBoundingClientRect(), zonaCaja = zona.getBoundingClientRect();
      let izquierda = zonaCaja.left - caja.left + zonaCaja.width / 2 - tooltip.offsetWidth / 2;
      izquierda = Math.max(0, Math.min(izquierda, caja.width - tooltip.offsetWidth));
      tooltip.style.left = `${izquierda}px`;
      tooltip.style.top = `${Math.max(0, zonaCaja.top - caja.top - tooltip.offsetHeight - 6)}px`;
    };
    const ocultar = () => { tooltip.hidden = true; };
    contenedor.querySelectorAll(".columna-zona").forEach((zona) => {
      zona.addEventListener("mouseenter", () => mostrar(zona));
      zona.addEventListener("focus", () => mostrar(zona));
      zona.addEventListener("mouseleave", ocultar);
      zona.addEventListener("blur", ocultar);
    });
    const columnas = presentes.length ? presentes : TEMAS;
    $("tabla-grafico").innerHTML = `<thead><tr><th>Semana</th>${columnas.map((t) => `<th>${escapar(t)}</th>`).join("")}<th>Total</th></tr></thead>` +
      `<tbody>${semanas.map((s) => `<tr><td>${textoDia(s.inicio, true)}</td>${columnas.map((t) => `<td>${s.porTema[t]}</td>`).join("")}<td>${s.total}</td></tr>`).join("")}</tbody>`;
  }

  // ------------------------------------------------------------ ranking
  function renderRanking(aplicarFiltro) {
    const desde = sumarDias(HOY, -DIAS_MES);
    const conteo = new Map();
    for (const i of ITEMS) {
      if (diaDe(i.fecha) < desde) continue;
      for (const e of i.empresas) {
        if (i.categoria === "organismo" && e === i.medio) continue; // no contar la autopublicación
        conteo.set(e, (conteo.get(e) || 0) + 1);
      }
    }
    const filas = [...conteo.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "es")).slice(0, 10);
    const contenedor = $("ranking-empresas");
    if (!filas.length) { contenedor.innerHTML = `<p class="vacio">Sin menciones en los últimos ${DIAS_MES} días.</p>`; return; }
    const maximo = filas[0][1];
    contenedor.innerHTML = filas.map(([nombre, n]) => `
      <button type="button" class="ranking-fila" data-empresa="${escapar(nombre)}" aria-label="Filtrar la lista por ${escapar(nombre)}, ${n} menciones">
        <span class="nombre">${escapar(nombre)}</span><span class="barra-r" style="width:${Math.max(3, (n / maximo) * 100)}%"></span><span class="cifra-r">${n}</span>
      </button>`).join("");
    contenedor.querySelectorAll(".ranking-fila").forEach((fila) => fila.addEventListener("click", () => {
      $("filtros").reset();
      setTimeout(() => {
        document.querySelector('input[name="f-categoria"][value=""]').checked = true;
        document.querySelectorAll('input[name="f-prioridad"]').forEach((c) => { c.checked = true; });
        $("f-empresa").value = fila.dataset.empresa;
        aplicarFiltro();
        $("noticias").scrollIntoView({ block: "start" });
      }, 0);
    }));
  }

  // ------------------------------------------------------------ resumen
  function renderResumen() {
    const r = DATOS.resumen_semanal;
    $("resumen-periodo").textContent = `Datos ${r.periodo.texto}. Generado automáticamente, sin opiniones.`;
    const tabla = (pares, vacio) => pares.length ? `<dl>${pares.map(([k, v]) => `<dt>${escapar(k)}</dt><dd>${v}</dd>`).join("")}</dl>` : `<p class="detalle">${vacio}</p>`;
    const item = (i) => `<li>${enlace(i)}<div class="meta"><span class="medio">${escapar(i.medio)}</span><span>${escapar(textoFechaItem(i))}</span><span>${escapar(i.motivo || i.tema)}</span></div></li>`;
    const pp = r.por_prioridad || {};
    $("resumen-semanal").innerHTML = `
      <div class="bloque"><h3>Cifras de la semana</h3>${tabla([["Titulares", r.total], ["De medios", r.de_medios], ["De organismos", r.de_organismos], ["Prioridad alta", pp.alta || 0], ["Prioridad media", pp.media || 0], ["Prioridad baja", pp.baja || 0]])}</div>
      <div class="bloque"><h3>Temas</h3>${tabla(Object.entries(r.por_tema), "Sin titulares esta semana.")}</div>
      <div class="bloque"><h3>Sectores</h3>${tabla(Object.entries(r.por_sector), "Sin titulares esta semana.")}</div>
      <div class="bloque"><h3>Empresas y organismos</h3>${tabla(r.empresas_mas_mencionadas, "Sin menciones esta semana.")}</div>
      <div class="bloque bloque-ancho"><h3>Prioridad alta de la semana (${(r.alta || []).length})</h3>${(r.alta || []).length ? `<ul>${r.alta.slice(0, 10).map(item).join("")}</ul>` : '<p class="detalle">Sin publicaciones de prioridad alta esta semana.</p>'}</div>
      <div class="bloque bloque-ancho"><h3>Publicaciones de organismos (${r.regulatorias.length})</h3>${r.regulatorias.length ? `<ul>${r.regulatorias.slice(0, 10).map(item).join("")}</ul>` : '<p class="detalle">Sin publicaciones regulatorias esta semana.</p>'}</div>`;
  }

  // ------------------------------------------------------------ fuentes
  function renderFuentes() {
    const tipos = { rss: "RSS", sitemap_noticias: "Sitemap de noticias", html_documentos: "Página de documentos", datos_bcrd: "Archivo de datos" };
    const grupos = [["medio", "Medios"], ["organismo", "Organismos"], ["indicador", "Datos del Banco Central"]];
    const activas = DATOS.fuentes.filter((f) => f.activa);
    const ok = activas.filter((f) => f.estado === "ok").length;
    $("fuentes-resumen").textContent = `${ok} de ${activas.length} fuentes funcionando en la última lectura. Una fuente con error no detiene a las demás; a los 3 fallos seguidos se abre un aviso automático.`;
    $("estado-fuentes").innerHTML = grupos.map(([clave, titulo]) => {
      const filas = DATOS.fuentes.filter((f) => (f.categoria || "medio") === clave);
      if (!filas.length) return "";
      const activasGrupo = filas.filter((f) => f.activa);
      const okGrupo = activasGrupo.filter((f) => f.estado === "ok").length;
      const conError = okGrupo < activasGrupo.length;
      return `<details class="grupo-fuentes"${conError ? " open" : ""}><summary><span class="grupo-titulo">${titulo}</span><span class="grupo-estado ${conError ? "error" : "ok"}"><span class="punto"></span>${okGrupo} de ${activasGrupo.length} funcionando</span></summary><ul class="estado-fuentes">${filas.map((f) => {
        const clase = !f.activa ? "inactiva" : f.estado === "ok" ? "ok" : "error";
        const texto = !f.activa ? "Inactiva" : f.estado === "ok" ? "OK" : "Error";
        const detalle = !f.activa ? "desactivada en la configuración"
          : f.estado === "ok" ? `${tipos[f.tipo] || f.tipo} · último éxito ${tiempoRelativo(f.ultimo_exito)}`
            : `${escapar(f.mensaje_error || "error sin detalle").slice(0, 120)} · ${plural(f.fallos_consecutivos, "fallo seguido", "fallos seguidos")}`;
        return `<li class="fuente"><span class="estado ${clase}"><span class="punto"></span>${texto}</span><span><span class="nombre">${escapar(f.nombre)}</span><br><span class="detalle">${detalle}</span></span></li>`;
      }).join("")}</ul></details>`;
    }).join("");
  }

  // ------------------------------------------------------------ metodología
  function renderMetodologia() {
    const m = DATOS.metodologia;
    $("metodologia-contenido").innerHTML = `
      <div class="bloque"><h3>Fuentes</h3>
        <p><strong>${m.medios.length} medios:</strong> ${m.medios.map(escapar).join(", ")}.</p>
        <p style="margin-top:8px"><strong>${m.organismos.length} organismos:</strong> ${m.organismos.map(escapar).join(", ")}.</p>
        <p style="margin-top:8px">Solo se leen feeds y sitemaps públicos que el robots.txt de cada sitio permite. Los indicadores salen de archivos oficiales del Banco Central.</p>
      </div>
      <div class="bloque"><h3>Prioridad</h3><ul>
        <li><strong>Alta:</strong> menciona una ley, decreto, resolución, circular o norma con número, o una reforma, tarifa, cobertura, cierre o impuesto sobre los seguros.</li>
        <li><strong>Baja:</strong> comunicado institucional (campañas, aniversarios, premios, talleres) o nota de un medio sin ninguna empresa u organismo del mercado.</li>
        <li><strong>Media:</strong> el resto de las noticias del sector.</li>
        <li>Cada titular muestra el motivo de su prioridad. Las reglas están en el código abierto.</li>
      </ul></div>
      <div class="bloque"><h3>Búsqueda y orden</h3><ul>
        <li>La búsqueda encuentra los titulares que contienen todas las palabras escritas, sin importar acentos ni mayúsculas.</li>
        <li>Los resultados se ordenan siempre por fecha, del más reciente al más antiguo. Ningún medio ni empresa tiene más peso.</li>
        <li>La misma noticia en varios medios aparece una vez, con enlaces a los demás.</li>
        <li>Solo se guarda título, medio, fecha, enlace y etiquetas; nunca el texto.</li>
      </ul></div>`;
  }

  // ------------------------------------------------------------ inicio
  if (DATOS.meta.repositorio) {
    $("enlace-repo").innerHTML = ` · <a href="${escapar(DATOS.meta.repositorio)}" target="_blank" rel="noopener noreferrer">código y datos en GitHub</a>`;
  }
  renderCifras();
  renderIndicadores();
  renderAlta();
  renderRegulacion();
  const aplicarFiltro = prepararFiltros();
  renderRanking(aplicarFiltro);
  renderResumen();
  renderFuentes();
  renderMetodologia();
  renderLista();
  renderGrafico();

  let temporizador = null;
  window.addEventListener("resize", () => { clearTimeout(temporizador); temporizador = setTimeout(renderGrafico, 150); });
})();
