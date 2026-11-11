"use strict";
/* Vista Alertas (administrador): la cola de trabajo del operador. Las alertas las crea y las cierra el servidor;
   aquí se revisan, se marcan como atendidas y se consulta el historial. */

const TIPO_ALERTA = {
  estancia_excedida: { nombre: "Estancia excedida", icono: "reloj", tono: "aviso" },
  obstruccion_prolongada: { nombre: "Obstrucción prolongada", icono: "obstaculo", tono: "aviso" },
  camara_sin_senal: { nombre: "Cámara sin señal", icono: "camara_off", tono: "critico" },
  ocupacion_alta: { nombre: "Ocupación alta", icono: "lleno", tono: "critico" },
};
const tipoAlerta = (a) => TIPO_ALERTA[a.tipo] || { nombre: a.tipo, icono: "alerta", tono: "" };
const AL = {};

/** Renglón compacto, para la tarjeta del Resumen. */
function filaAlerta(a) {
  const t = tipoAlerta(a);
  return h("div", { class: "fila" }, h("div", { class: "insignia " + t.tono }, icono(t.icono, 16)),
    h("div", { class: "fila-txt" }, h("b", { text: a.mensaje, title: a.mensaje }), h("span", { text: t.nombre + (a.atendida ? " · atendida" : "") })),
    h("div", { class: "fila-der", text: a.duracion_s != null ? dur(a.duracion_s) : hace(a.creada) }));
}

function vistaAlertas() {
  AL.cuentas = h("div", { class: "alerta-cuentas" });
  AL.lista = h("div");
  return h("section", { class: "vista", id: "v-alertas" },
    AL.cuentas,
    h("section", { class: "tarjeta" },
      h("div", { class: "tarjeta-cab" },
        AL.seg = segmentado([["activas", "Activas"], ["historial", "Historial"]], S.alertasTab, (v) => { S.alertasTab = v; if (v === "historial") cargarHistorialAlertas(); pintarAlertas(); }),
        h("button", { class: "btn chico", type: "button", onClick: revisarAlertas }, icono("pulso", 15), "Revisar ahora")),
      AL.lista),
    h("p", { class: "nota", style: "margin-top:12px", text: "Una alerta se cierra sola cuando la condición deja de cumplirse (el vehículo se va, se retira el objeto, vuelve la cámara). «Atender» solo registra que alguien ya la está viendo." }));
}

async function cargarHistorialAlertas() {
  try { S.historialAlertas = await api("/alertas?estado=todas&limite=200"); } catch (e) { toast(e.message, "mal"); }
  if (S.vista === "alertas") pintarAlertas();
}
async function revisarAlertas(ev) {
  const b = ev.currentTarget; b.disabled = true;
  try {
    const r = await post("/alertas/evaluar");
    S.alertas = await api("/alertas?estado=activas&limite=100");
    toast(r && (r.creadas || r.cerradas) ? `${r.creadas} alerta(s) nueva(s), ${r.cerradas} cerrada(s)` : "Sin cambios: todo sigue igual", "ok");
    if (S.alertasTab === "historial") await cargarHistorialAlertas();
    pintarAlertas(); pintarComun();
  } catch (e) { toast(e.message, "mal"); }
  b.disabled = false;
}
async function atenderAlerta(a, boton) {
  boton.disabled = true;
  try {
    const r = await post(`/alertas/${a.id}/atender`);
    if (r) Object.assign(a, r);
    toast("Alerta marcada como atendida", "ok"); pintarAlertas(); pintarComun();
  } catch (e) { toast(e.message, "mal"); boton.disabled = false; }
}

function tarjetaAlerta(a) {
  const t = tipoAlerta(a);
  const meta = [t.nombre, a.zona, a.camara, a.duracion_s != null ? "desde hace " + dur(a.duracion_s) : fechaHora(a.creada)].filter(Boolean).join(" · ");
  return h("div", { class: "alerta " + t.tono + (a.atendida ? " atendida" : "") },
    h("div", { class: "insignia " + t.tono }, icono(t.icono, 18)),
    h("div", { class: "alerta-txt" }, h("b", { text: a.mensaje }), h("span", null, meta, a.espacio ? [" · ", refCajon(a.espacio)] : null)),
    a.atendida
      ? h("div", { class: "alerta-quien" }, etq("Atendida", "ok"), h("span", { text: `${a.atendidaPor || "—"} · ${hora(a.atendida)}` }))
      : h("button", { class: "btn primario chico", type: "button", onClick: (ev) => atenderAlerta(a, ev.currentTarget) }, icono("check", 15), "Atender"));
}

function pintarAlertas() {
  if (!AL.lista) return;
  const activas = S.alertas || [];
  AL.cuentas.replaceChildren(...Object.entries(TIPO_ALERTA).map(([clave, t]) => {
    const n = activas.filter((a) => a.tipo === clave).length;
    return h("div", { class: "tarjeta kpi" }, h("div", { class: "kpi-etq" }, h("div", { class: "insignia " + (n ? t.tono : "") }, icono(t.icono, 16)), t.nombre), h("div", { class: "kpi-valor", text: num(n) }),
      h("div", { class: "kpi-nota", text: n ? `${activas.filter((a) => a.tipo === clave && !a.atendida).length} sin atender` : "Ninguna activa" }));
  }));

  if (S.alertasTab === "activas") {
    const orden = [...activas].sort((a, b) => !!a.atendida - !!b.atendida || (b.duracion_s || 0) - (a.duracion_s || 0));
    AL.lista.replaceChildren(orden.length ? h("div", { class: "alertas" }, orden.map(tarjetaAlerta)) : vacio("check", "Todo en orden", "No hay alertas activas en este momento."));
    return;
  }
  const hist = S.historialAlertas;
  if (!hist) { AL.lista.replaceChildren(h("div", { class: "vacio", text: "Cargando el historial…" })); return; }
  if (!hist.length) { AL.lista.replaceChildren(vacio("alerta", "Sin historial", "Todavía no se ha generado ninguna alerta.")); return; }
  AL.lista.replaceChildren(h("div", { class: "tabla-caja" }, h("table", { class: "tabla" },
    h("thead", null, h("tr", null, ["Creada", "Tipo", "Detalle", "Cajón", "Estado", "Atendida por", "Resuelta"].map((c) => h("th", { text: c })))),
    h("tbody", null, hist.map((a) => h("tr", null,
      h("td", { class: "num", text: fechaHora(a.creada) }), h("td", { text: tipoAlerta(a).nombre }), h("td", { text: a.mensaje }),
      h("td", null, a.espacio ? refCajon(a.espacio) : "—"), h("td", null, etq(a.activa ? "Activa" : "Resuelta", a.activa ? tipoAlerta(a).tono : "ok")),
      h("td", { text: a.atendidaPor || "—" }), h("td", { class: "num", text: a.resuelta ? fechaHora(a.resuelta) : "—" })))))));
}
