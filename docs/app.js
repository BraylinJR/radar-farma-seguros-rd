/* Radar Farma & Seguros RD: lógica de la página. Sin dependencias externas. */
(function () {
  "use strict";

  const DATOS = JSON.parse(document.getElementById("radar-datos").textContent);
  const ITEMS = DATOS.items;
  const SECTORES = DATOS.sectores;
  const TEMAS = DATOS.temas;
  const MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const PAGINA = 50;
  const SEMANAS = 12;
  const DIAS_MES = 30;
  const SECTOR_REGULACION = "Regulación y gobierno";

  // ----------------------------------------------------------- utilidades

  const $ = (id) => document.getElementById(id);

  function escapar(texto) {
    return String(texto ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function normalizar(texto) {
    return String(texto ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }

  // Fecha de calendario en hora de RD, tomada del texto ISO (evita cambios por la zona del lector).
  function diaDe(iso) {
    return iso.slice(0, 10);
  }
  function fechaUTC(dia) {
    const [a, m, d] = dia.split("-").map(Number);
    return new Date(Date.UTC(a, m - 1, d));
  }
  function diaDesdeUTC(fecha) {
    return fecha.toISOString().slice(0, 10);
  }
  function sumarDias(dia, n) {
    const f = fechaUTC(dia);
    f.setUTCDate(f.getUTCDate() + n);
    return diaDesdeUTC(f);
  }
  function inicioSemana(dia) {
    const f = fechaUTC(dia);
    const desplazamiento = (f.getUTCDay() + 6) % 7; // lunes = 0
    f.setUTCDate(f.getUTCDate() - desplazamiento);
    return diaDesdeUTC(f);
  }
  function textoDia(dia, conAnio) {
    const [a, m, d] = dia.split("-").map(Number);
    return `${d} ${MESES_CORTOS[m - 1]}${conAnio ? " " + a : ""}`;
  }
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
  function colorTema(tema) {
    const indice = TEMAS.indexOf(tema);
    return `var(--serie-${(indice < 0 ? TEMAS.length - 1 : indice) + 1})`;
  }
  function plural(n, singular, pluralTexto) {
    return `${n.toLocaleString("es-DO")} ${n === 1 ? singular : pluralTexto}`;
  }

  const HOY = diaDe(DATOS.meta.generado);

  // --------------------------------------------------------------- chips

  function chips(item, opciones) {
    const partes = [];
    if (opciones && opciones.tipo && item.tipo === "documento") {
      partes.push(`<span class="chip chip-tipo">Documento</span>`);
    }
    for (const s of item.sectores) partes.push(`<span class="chip chip-sector">${escapar(s)}</span>`);
    partes.push(`<span class="chip chip-tema"><span class="punto" style="background:${colorTema(item.tema)}"></span>${escapar(item.tema)}</span>`);
    for (const e of item.empresas) partes.push(`<span class="chip chip-empresa">${escapar(e)}</span>`);
    return `<div class="chips">${partes.join("")}</div>`;
  }

  function enlace(item, clase) {
    return `<a class="${clase || ""}" href="${escapar(item.enlace)}" target="_blank" rel="noopener noreferrer">${escapar(item.titulo)}</a>`;
  }

  // ------------------------------------------------------------- cabecera

  function renderKpis() {
    const r = DATOS.resumen_semanal;
    const activas = DATOS.fuentes.filter((f) => f.activa);
    const ok = activas.filter((f) => f.estado === "ok").length;
    $("kpis").innerHTML = [
      { etiqueta: "Titulares en 7 días", valor: r.total, nota: `${r.de_medios} de medios, ${r.de_organismos} de organismos` },
      { etiqueta: "Regulatorios en 7 días", valor: r.de_organismos, nota: "publicados por organismos" },
      { etiqueta: "Fuentes funcionando", valor: `${ok}/${activas.length}`, nota: "en la última lectura" },
      { etiqueta: "Historial", valor: DATOS.meta.total_historial, nota: "titulares acumulados" },
    ].map((k) => `<div class="kpi"><div class="etiqueta">${k.etiqueta}</div><div class="valor">${escapar(k.valor)}</div><div class="nota">${k.nota}</div></div>`).join("");
  }

  // ----------------------------------------------------------- regulación

  function renderRegulacion() {
    const ultimos = ITEMS.filter((i) => i.categoria === "organismo").slice(0, 8);
    const lista = $("lista-regulacion");
    if (!ultimos.length) {
      lista.innerHTML = `<li class="vacio">Todavía no hay publicaciones de organismos.</li>`;
      return;
    }
    lista.innerHTML = ultimos.map((i) => `
      <li class="tarjeta">
        <div class="meta"><span class="organismo">${escapar(i.medio)}</span><span>${escapar(textoFechaItem(i))}</span>${i.tipo === "documento" ? '<span class="chip chip-tipo">PDF</span>' : ""}</div>
        <h3>${enlace(i)}</h3>
        ${chips(i)}
      </li>`).join("");
  }

  // -------------------------------------------------------------- filtros

  const estado = { texto: "", sector: "", tema: "", empresa: "", desde: "", hasta: "", mostrados: PAGINA };

  function llenarSelect(id, valores, textoDe) {
    const select = $(id);
    for (const v of valores) {
      const opcion = document.createElement("option");
      opcion.value = typeof v === "string" ? v : v[0];
      opcion.textContent = textoDe ? textoDe(v) : v;
      select.appendChild(opcion);
    }
  }

  function prepararFiltros() {
    llenarSelect("f-sector", SECTORES);
    llenarSelect("f-tema", TEMAS);
    const conteo = new Map();
    for (const i of ITEMS) for (const e of i.empresas) conteo.set(e, (conteo.get(e) || 0) + 1);
    const empresas = [...conteo.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "es"));
    llenarSelect("f-empresa", empresas, (v) => `${v[0]} (${v[1]})`);

    const leer = () => {
      estado.texto = normalizar($("f-texto").value.trim());
      estado.sector = $("f-sector").value;
      estado.tema = $("f-tema").value;
      estado.empresa = $("f-empresa").value;
      estado.desde = $("f-desde").value;
      estado.hasta = $("f-hasta").value;
      estado.mostrados = PAGINA;
      renderTodo();
    };
    $("filtros").addEventListener("input", leer);
    $("filtros").addEventListener("change", leer);
    $("filtros").addEventListener("submit", (ev) => ev.preventDefault());
    $("filtros").addEventListener("reset", () => setTimeout(leer, 0));
    $("mostrar-mas").addEventListener("click", () => { estado.mostrados += PAGINA; renderLista(); });
    $("ver-regulacion").addEventListener("click", () => {
      $("filtros").reset();
      $("f-sector").value = SECTOR_REGULACION;
      leer();
      $("noticias").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function pasaFiltrosSinFecha(i) {
    if (estado.sector && !i.sectores.includes(estado.sector)) return false;
    if (estado.tema && i.tema !== estado.tema) return false;
    if (estado.empresa && !i.empresas.includes(estado.empresa)) return false;
    if (estado.texto) {
      const pajar = normalizar(`${i.titulo} ${i.medio} ${i.empresas.join(" ")}`);
      if (!pajar.includes(estado.texto)) return false;
    }
    return true;
  }
  function pasaFiltros(i) {
    if (!pasaFiltrosSinFecha(i)) return false;
    const dia = diaDe(i.fecha);
    if (estado.desde && dia < estado.desde) return false;
    if (estado.hasta && dia > estado.hasta) return false;
    return true;
  }

  // ---------------------------------------------------------------- lista

  function renderLista() {
    const filtrados = ITEMS.filter(pasaFiltros);
    const visibles = filtrados.slice(0, estado.mostrados);
    const activos = estado.texto || estado.sector || estado.tema || estado.empresa || estado.desde || estado.hasta;
    $("conteo").textContent = activos
      ? `${plural(filtrados.length, "resultado", "resultados")} de ${ITEMS.length.toLocaleString("es-DO")} titulares`
      : `${plural(ITEMS.length, "titular", "titulares")} de los últimos ${DATOS.meta.dias_en_pagina} días, del más reciente al más antiguo`;
    const lista = $("lista-noticias");
    if (!filtrados.length) {
      lista.innerHTML = `<li class="vacio">Ningún titular coincide con los filtros.</li>`;
    } else {
      lista.innerHTML = visibles.map((i) => `
        <li class="noticia">
          <div class="meta"><span class="medio">${escapar(i.medio)}</span><span>${escapar(textoFechaItem(i))}</span>${i.categoria === "organismo" ? "<span>organismo</span>" : ""}</div>
          <h3>${enlace(i)}</h3>
          ${chips(i, { tipo: true })}
          ${i.tambien_en.length ? `<div class="tambien">También en: ${i.tambien_en.map((t) => `<a href="${escapar(t.enlace)}" target="_blank" rel="noopener noreferrer">${escapar(t.medio)}</a>`).join(", ")}</div>` : ""}
        </li>`).join("");
    }
    $("mostrar-mas").hidden = visibles.length >= filtrados.length;
    $("mostrar-mas").textContent = `Mostrar más (${filtrados.length - visibles.length} restantes)`;
  }

  // -------------------------------------------------------------- gráfico

  function datosSemanas() {
    const base = ITEMS.filter(pasaFiltrosSinFecha);
    const inicioActual = inicioSemana(HOY);
    const semanas = [];
    for (let k = SEMANAS - 1; k >= 0; k--) {
      const inicio = sumarDias(inicioActual, -7 * k);
      semanas.push({ inicio, fin: sumarDias(inicio, 6), porTema: Object.fromEntries(TEMAS.map((t) => [t, 0])), total: 0 });
    }
    const indice = new Map(semanas.map((s, n) => [s.inicio, n]));
    for (const i of base) {
      const n = indice.get(inicioSemana(diaDe(i.fecha)));
      if (n === undefined) continue;
      const s = semanas[n];
      const tema = TEMAS.includes(i.tema) ? i.tema : TEMAS[TEMAS.length - 1];
      s.porTema[tema] += 1;
      s.total += 1;
    }
    return semanas;
  }

  function ticksBonitos(maximo) {
    if (maximo <= 0) return [0, 1];
    const pasoBruto = maximo / 4;
    const potencia = Math.pow(10, Math.floor(Math.log10(pasoBruto)));
    const paso = [1, 2, 5, 10].map((m) => m * potencia).find((p) => maximo / p <= 4) || potencia * 10;
    const ticks = [];
    for (let v = 0; v <= Math.ceil(maximo / paso) * paso; v += paso) ticks.push(v);
    return ticks;
  }

  function renderGrafico() {
    const semanas = datosSemanas();
    const temasPresentes = TEMAS.filter((t) => semanas.some((s) => s.porTema[t] > 0));
    $("leyenda-grafico").innerHTML = (temasPresentes.length ? temasPresentes : TEMAS).map((t) =>
      `<span class="clave"><span class="muestra" style="background:${colorTema(t)}"></span>${escapar(t)}</span>`).join("");

    // El ancho del dibujo sigue al contenedor para que el texto conserve su tamaño en el celular.
    const contenedor = $("grafico-semanas");
    const ANCHO = Math.max(300, Math.round(contenedor.clientWidth || 720));
    const ALTO = ANCHO < 480 ? 220 : 260, IZQ = 34, DER = 8, ARRIBA = 18, ABAJO = 28, GAP = 2;
    const anchoPlano = ANCHO - IZQ - DER, altoPlano = ALTO - ARRIBA - ABAJO;
    const ranura = anchoPlano / SEMANAS;
    const anchoBarra = Math.min(24, Math.floor(ranura * 0.6));
    const saltoEtiquetas = ranura < 44 ? 2 : 1; // en pantallas estrechas, una etiqueta sí y otra no
    const maximo = Math.max(...semanas.map((s) => s.total));
    const ticks = ticksBonitos(maximo);
    const tope = ticks[ticks.length - 1];
    const y = (v) => ARRIBA + altoPlano - (v / tope) * altoPlano;

    let svg = `<svg viewBox="0 0 ${ANCHO} ${ALTO}" role="img" aria-label="Columnas apiladas de titulares por semana y tema">`;
    for (const t of ticks) {
      svg += `<line class="rejilla" x1="${IZQ}" x2="${ANCHO - DER}" y1="${y(t)}" y2="${y(t)}"/>`;
      svg += `<text class="eje-texto" x="${IZQ - 6}" y="${y(t) + 4}" text-anchor="end">${t}</text>`;
    }
    svg += `<line class="base" x1="${IZQ}" x2="${ANCHO - DER}" y1="${y(0)}" y2="${y(0)}"/>`;

    semanas.forEach((s, n) => {
      const cx = IZQ + ranura * n + ranura / 2;
      const x0 = cx - anchoBarra / 2;
      let acumulado = 0;
      const presentes = TEMAS.filter((t) => s.porTema[t] > 0);
      presentes.forEach((t, k) => {
        const v = s.porTema[t];
        const yAlto = y(acumulado + v), yBajo = y(acumulado);
        const esCima = k === presentes.length - 1;
        const gapSup = esCima ? 0 : GAP / 2, gapInf = k === 0 ? 0 : GAP / 2;
        const top = yAlto + gapSup, bottom = yBajo - gapInf;
        const h = Math.max(0, bottom - top);
        if (h > 0) {
          if (esCima && h >= 4) {
            const r = 4;
            svg += `<path fill="${colorTema(t)}" d="M${x0},${bottom} V${top + r} a${r},${r} 0 0 1 ${r},-${r} H${x0 + anchoBarra - r} a${r},${r} 0 0 1 ${r},${r} V${bottom} Z"><title>${escapar(t)}: ${v}</title></path>`;
          } else {
            svg += `<rect fill="${colorTema(t)}" x="${x0}" y="${top}" width="${anchoBarra}" height="${h}"><title>${escapar(t)}: ${v}</title></rect>`;
          }
        }
        acumulado += v;
      });
      if (s.total > 0 && (n === SEMANAS - 1 || s.total === maximo)) {
        svg += `<text class="valor-cima" x="${cx}" y="${y(s.total) - 5}" text-anchor="middle">${s.total}</text>`;
      }
      if ((SEMANAS - 1 - n) % saltoEtiquetas === 0) {
        svg += `<text class="eje-texto" x="${cx}" y="${ALTO - 8}" text-anchor="middle">${textoDia(s.inicio)}</text>`;
      }
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
      const caja = contenedor.getBoundingClientRect();
      const zonaCaja = zona.getBoundingClientRect();
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

    const columnas = temasPresentes.length ? temasPresentes : TEMAS;
    $("tabla-grafico").innerHTML = `<thead><tr><th>Semana</th>${columnas.map((t) => `<th>${escapar(t)}</th>`).join("")}<th>Total</th></tr></thead>` +
      `<tbody>${semanas.map((s) => `<tr><td>${textoDia(s.inicio, true)}</td>${columnas.map((t) => `<td>${s.porTema[t]}</td>`).join("")}<td>${s.total}</td></tr>`).join("")}</tbody>`;
  }

  // -------------------------------------------------------------- ranking

  function renderRanking() {
    const desde = sumarDias(HOY, -DIAS_MES);
    const conteo = new Map();
    for (const i of ITEMS) {
      if (diaDe(i.fecha) < desde) continue;
      for (const e of i.empresas) conteo.set(e, (conteo.get(e) || 0) + 1);
    }
    const filas = [...conteo.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "es")).slice(0, 10);
    const contenedor = $("ranking-empresas");
    if (!filas.length) {
      contenedor.innerHTML = `<p class="vacio">Sin menciones en los últimos ${DIAS_MES} días.</p>`;
      return;
    }
    const maximo = filas[0][1];
    contenedor.innerHTML = filas.map(([nombre, n]) => `
      <button type="button" class="ranking-fila" data-empresa="${escapar(nombre)}" aria-label="Filtrar por ${escapar(nombre)}">
        <span class="nombre">${escapar(nombre)}</span>
        <span class="barra" style="width:${Math.max(2, (n / maximo) * 100)}%"></span>
        <span class="cifra">${n}</span>
      </button>`).join("");
    contenedor.querySelectorAll(".ranking-fila").forEach((fila) => fila.addEventListener("click", () => {
      $("filtros").reset();
      $("f-empresa").value = fila.dataset.empresa;
      $("filtros").dispatchEvent(new Event("change"));
      $("noticias").scrollIntoView({ behavior: "smooth", block: "start" });
    }));
  }

  // -------------------------------------------------------------- resumen

  function renderResumen() {
    const r = DATOS.resumen_semanal;
    $("resumen-periodo").textContent = `Datos ${r.periodo.texto}. Generado automáticamente, sin opiniones.`;
    const lista = (pares, vacio) => pares.length
      ? `<dl>${pares.map(([k, v]) => `<dt>${escapar(k)}</dt><dd>${v}</dd>`).join("")}</dl>`
      : `<p class="detalle">${vacio}</p>`;
    const regulatorias = r.regulatorias.slice(0, 15);
    $("resumen-semanal").innerHTML = `
      <div class="bloque">
        <h3>Cifras de la semana</h3>
        ${lista([["Titulares guardados", r.total], ["De medios", r.de_medios], ["De organismos", r.de_organismos]])}
      </div>
      <div class="bloque">
        <h3>Temas más frecuentes</h3>
        ${lista(Object.entries(r.por_tema), "Sin titulares esta semana.")}
      </div>
      <div class="bloque">
        <h3>Sectores</h3>
        ${lista(Object.entries(r.por_sector), "Sin titulares esta semana.")}
      </div>
      <div class="bloque">
        <h3>Empresas y organismos más mencionados</h3>
        ${lista(r.empresas_mas_mencionadas, "Sin menciones esta semana.")}
      </div>
      <div class="bloque bloque-ancho">
        <h3>Publicaciones de organismos en la semana (${r.de_organismos})</h3>
        ${regulatorias.length ? `<ul>${regulatorias.map((i) => `<li>${enlace(i)}<div class="meta">${escapar(i.medio)} · ${escapar(textoFechaItem(i))} · ${escapar(i.tema)}</div></li>`).join("")}</ul>${r.regulatorias.length > 15 ? `<p class="detalle">Y ${r.regulatorias.length - 15} más en la lista de noticias.</p>` : ""}` : `<p class="detalle">Sin publicaciones de organismos esta semana.</p>`}
      </div>`;
  }

  // -------------------------------------------------------------- fuentes

  function renderFuentes() {
    const tipos = { rss: "RSS", sitemap_noticias: "Sitemap", html_documentos: "Documentos" };
    $("estado-fuentes").innerHTML = DATOS.fuentes.map((f) => {
      const clase = !f.activa ? "inactiva" : f.estado === "ok" ? "ok" : "error";
      const texto = !f.activa ? "Inactiva" : f.estado === "ok" ? "OK" : "Error";
      const etiquetaTipo = `${tipos[f.tipo] || f.tipo} · ${escapar(f.id)}`;
      const detalle = !f.activa
        ? `${etiquetaTipo} · desactivada en la configuración`
        : f.estado === "ok"
          ? `${etiquetaTipo} · ${f.conteo ? `${f.conteo.leidos} leídos, ${f.conteo.nuevos} nuevos` : "sin conteo"}`
          : `${etiquetaTipo} · ${escapar(f.mensaje_error || "error sin detalle")}`;
      const derecha = !f.activa ? "" : f.estado === "ok"
        ? `último éxito ${tiempoRelativo(f.ultimo_exito)}`
        : `${plural(f.fallos_consecutivos, "fallo seguido", "fallos seguidos")}${f.ultimo_exito ? `<br>último éxito ${tiempoRelativo(f.ultimo_exito)}` : ""}`;
      return `<li class="fuente">
        <span class="estado ${clase}"><span class="punto"></span>${texto}</span>
        <span><span class="nombre">${escapar(f.nombre)}</span><br><span class="detalle">${detalle}</span></span>
        <span class="derecha">${derecha}</span>
      </li>`;
    }).join("");
  }

  // ----------------------------------------------------------------- todo

  function renderTodo() {
    renderLista();
    renderGrafico();
  }

  renderKpis();
  renderRegulacion();
  prepararFiltros();
  renderRanking();
  renderResumen();
  renderFuentes();
  renderTodo();

  let temporizador = null;
  window.addEventListener("resize", () => {
    clearTimeout(temporizador);
    temporizador = setTimeout(renderGrafico, 150);
  });
})();
