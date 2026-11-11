"use strict";
/* Vista Reportes (administrador): ocupación histórica, horas pico, patrón semanal y exportación a CSV. */

const PERIODOS = [[1, "Hoy"], [7, "7 días"], [30, "30 días"]];
const EXPORTABLES = [
  ["ocupacion", "Ocupación", "Una muestra por minuto y por fila: libres, ocupados y obstruidos."],
  ["eventos", "Eventos", "Entradas, salidas, obstrucciones y caídas de cámara."],
  ["estancias", "Estancias", "Cada estancia con su hora de entrada, de salida y su duración."],
  ["alertas", "Alertas", "Alertas generadas, quién las atendió y cuándo se resolvieron."],
];
const RP = {};

/** Periodo elegido, como fechas locales AAAA-MM-DD (hasta = hoy). */
function periodoReporte() {
  const hasta = new Date(), desde = new Date(); desde.setDate(desde.getDate() - (S.reporte.dias - 1));
  return { desde: fechaLocal(desde), hasta: fechaLocal(hasta) };
}
/** "2026-11-02T08:00" o "2026-11-02" → Date en hora local (una fecha sola, JS la tomaría como UTC). */
function fechaDeReporte(txt) {
  const [f, t] = txt.split("T"), [a, m, d] = f.split("-").map(Number), [hh, mm] = (t || "00:00").split(":").map(Number);
  return new Date(a, m - 1, d, hh, mm);
}

function vistaReportes() {
  RP.zona = h("select", { class: "entrada", "aria-label": "Fila", onChange: (e) => { S.reporte.zona = e.target.value; cargarReportes(); } }, h("option", { value: "", text: "Todo el estacionamiento" }));
  RP.rango = h("span", { class: "nota" });
  RP.kpis = h("div", { class: "kpis rep-kpis" });
  RP.serie = h("div"); RP.barras = h("div"); RP.calor = h("div");
  RP.subSerie = h("p");
  return h("section", { class: "vista", id: "v-reportes" },
    h("div", { class: "rep-barra" },
      segmentado(PERIODOS, S.reporte.dias, (v) => { S.reporte.dias = v; cargarReportes(); }), RP.zona, RP.rango),
    RP.kpis,
    h("section", { class: "tarjeta" }, h("div", { class: "tarjeta-cab" }, h("div", null, h("h2", { text: "Ocupación histórica" }), RP.subSerie)), RP.serie),
    h("div", { class: "rep-dos" },
      tarjeta("Horas pico", "Ocupación media de cada hora del día en el periodo", null, RP.barras),
      tarjeta("Patrón semanal", "Ocupación media por día de la semana y hora", null, RP.calor)),
    tarjeta("Exportar datos", "Archivos CSV del periodo elegido, listos para abrir en Excel", null,
      h("div", { class: "exportar" }, EXPORTABLES.map(([clave, nombre, texto]) =>
        h("div", { class: "exporta" }, h("div", null, h("b", { text: nombre }), h("span", { text: texto })),
          h("button", { class: "btn chico", type: "button", onClick: (ev) => exportarReporte(clave, ev.currentTarget) }, icono("descarga", 15), "CSV"))))));
}

async function exportarReporte(clave, boton) {
  const p = periodoReporte(); boton.disabled = true;
  try { await descargarCsv(`/reportes/exportar/${clave}?desde=${p.desde}&hasta=${p.hasta}`, `${clave}_${p.desde}_${p.hasta}.csv`); toast("Archivo generado", "ok"); }
  catch (e) { toast(e.message, "mal"); }
  boton.disabled = false;
}

async function cargarReportes() {
  if (!esAdmin() || S.reporte.cargando) return;
  S.reporte.cargando = true;
  const p = periodoReporte(), q = `desde=${p.desde}&hasta=${p.hasta}`, zona = S.reporte.zona ? "&zona=" + encodeURIComponent(S.reporte.zona) : "";
  const intervalo = S.reporte.dias > 7 ? "dia" : "hora", pedido = S.reporte.dias + "|" + S.reporte.zona;
  try {
    const [resumen, serie, pico] = await Promise.all([api(`/reportes/resumen?${q}`), api(`/reportes/ocupacion?intervalo=${intervalo}&${q}${zona}`), api(`/reportes/horas-pico?${q}${zona}`)]);
    S.reporte.datos = { resumen, serie: serie || [], pico: pico || { por_hora: [], semana: [] }, intervalo, periodo: p, pedido };
  } catch (e) { toast(e.message, "mal"); }
  S.reporte.cargando = false;
  if (pedido !== S.reporte.dias + "|" + S.reporte.zona) return cargarReportes();  // cambió la selección mientras cargaba
  pintarReportes();
}

function pintarReportes() {
  if (!RP.kpis) return;
  if (!esAdmin()) { RP.kpis.replaceChildren(vacio("reportes", "Solo para administradores", "Los reportes históricos son visibles únicamente para el personal administrador.")); return; }
  // Opciones de fila (una vez que se conocen los cajones)
  if (RP.zona.children.length === 1 && S.espacios.length) {
    for (const z of agruparIslas().filter((x) => x.monit)) RP.zona.append(h("option", { value: z.nombre, text: rotulo(z.nombre) }));
    RP.zona.value = S.reporte.zona;
  }
  const d = S.reporte.datos;
  if (!d) { RP.kpis.replaceChildren(h("div", { class: "vacio", text: "Cargando los reportes…" })); return; }
  const r = d.resumen || {};
  RP.rango.textContent = d.periodo.desde === d.periodo.hasta ? "Hoy" : `${fechaDeReporte(d.periodo.desde).toLocaleDateString("es-MX", { day: "numeric", month: "short" })} – ${fechaDeReporte(d.periodo.hasta).toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric" })}`;

  const kpi = (etiqueta, valor, unidad, nota) => h("div", { class: "tarjeta kpi" }, h("div", { class: "kpi-etq", text: etiqueta }),
    h("div", { class: "kpi-valor" }, valor, unidad ? h("small", { text: unidad }) : null), h("div", { class: "kpi-nota", text: nota }));
  RP.kpis.replaceChildren(
    kpi("Ocupación media", r.ocupacion_media_pct == null ? "—" : num(r.ocupacion_media_pct, 1), r.ocupacion_media_pct == null ? "" : "%", r.muestras ? `${num(r.muestras)} muestras en el periodo` : "Sin muestras en el periodo"),
    kpi("Pico de ocupación", r.pico ? num(r.pico.ocupacion_pct, 1) : "—", r.pico ? "%" : "", r.pico ? `${r.pico.ocupados} de ${r.pico.monitoreados} cajones · ${fechaHora(r.pico.cuando)}` : "Sin datos"),
    kpi("Hora más concurrida", r.hora_pico ? String(r.hora_pico.hora).padStart(2, "0") + ":00" : "—", "", r.hora_pico ? `${num(r.hora_pico.ocupacion_media_pct, 1)} % de ocupación media` : "Sin datos"),
    kpi("Movimiento", num((r.entradas || 0) + (r.salidas || 0)), "", `${num(r.entradas || 0)} entradas · ${num(r.salidas || 0)} salidas`),
    kpi("Incidencias", num((r.alertas || 0)), "", `${num(r.obstrucciones || 0)} obstrucciones · ${num(r.caidas_de_camara || 0)} caídas de cámara`));

  const porDia = d.intervalo === "dia";
  RP.subSerie.textContent = (porDia ? "Promedio diario" : "Promedio por hora") + " del porcentaje de cajones ocupados" + (S.reporte.zona ? " · " + rotulo(S.reporte.zona) : "");
  const variosDias = d.periodo.desde !== d.periodo.hasta;
  graficaSerie(RP.serie, d.serie.map((x) => {
    const f = fechaDeReporte(x.inicio);
    const dia = f.toLocaleDateString("es-MX", { weekday: "short", day: "numeric", month: "short" }), hh = String(f.getHours()).padStart(2, "0") + ":00";
    return { y: x.ocupacion_media_pct, eje: porDia ? f.toLocaleDateString("es-MX", { day: "numeric", month: "short" }) : variosDias ? (f.getHours() === 0 ? f.toLocaleDateString("es-MX", { day: "numeric", month: "short" }) : null) : (f.getHours() % 2 === 0 ? hh : null),
      titulo: porDia ? dia : `${dia} · ${hh}`,
      filas: [["Ocupación media", num(x.ocupacion_media_pct, 1) + " %"], ["Máxima", num(x.ocupacion_max_pct, 1) + " %"], ["Ocupados (máx.)", `${x.ocupados_max} de ${x.monitoreados}`], ["Libres (mín.)", num(x.libres_min)]] };
  }), { alto: 240, max: 100, titulo: "Ocupación histórica" });

  graficaBarras(RP.barras, (d.pico.por_hora || []).map((x) => ({ y: x.ocupacion_media_pct, eje: String(x.hora).padStart(2, "0"), titulo: `${String(x.hora).padStart(2, "0")}:00 a ${String(x.hora + 1).padStart(2, "0")}:00`,
    filas: x.ocupacion_media_pct == null ? ["Sin muestras"] : [["Ocupación media", num(x.ocupacion_media_pct, 1) + " %"], ["Máxima", num(x.ocupacion_max_pct, 1) + " %"], ["Libres (mín.)", num(x.libres_min)], ["Muestras", num(x.muestras)]] })), { alto: 230, max: 100, titulo: "Ocupación media por hora del día" });
  calorSemana(RP.calor, d.pico.semana);
}
