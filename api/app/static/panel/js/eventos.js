"use strict";
/* Vista Eventos: bitácora de entradas, salidas y avisos de cámara (solo administradores). */

const ES_ALERTA = new Set(["error_deteccion", "camara_desconectada", "camara_restablecida", "obstruccion", "obstruccion_retirada"]);
const FILTROS_EVENTO = [["todos", "Todos"], ["entrada", "Entradas"], ["salida", "Salidas"], ["alertas", "Avisos y cámaras"]];
const cajonDeEvento = (e) => (e.descripcion.match(/\b[A-H]-\d{2}\b/) || [""])[0];
const EV = {};

/** Renglón compacto de un evento, para listas (Resumen y ficha de cajón). */
function filaEvento(e) {
  return h("div", { class: "fila" },
    h("div", { class: "insignia " + (TONO_EVENTO[e.tipo] || "") }, icono(ICONO_EVENTO[e.tipo] || "eventos", 16)),
    h("div", { class: "fila-txt" }, h("b", { text: e.descripcion, title: e.descripcion }), h("span", { text: NOMBRE_EVENTO[e.tipo] || e.tipo })),
    h("div", { class: "fila-der", text: hora(e.fecha) }));
}

function vistaEventos() {
  EV.chips = h("div", { class: "chips" }, FILTROS_EVENTO.map(([valor, texto]) =>
    h("button", { type: "button", class: "chip", "data-f": valor, onClick: () => { S.filtroEvento = valor; pintarEventos(); } }, texto + " ", h("b"))));
  EV.cuerpo = h("div");
  EV.pie = h("p", { class: "nota", style: "margin-top:12px" });
  return h("section", { class: "vista", id: "v-eventos" },
    h("section", { class: "tarjeta" },
      h("div", { class: "barra-filtros" }, EV.chips,
        h("label", { class: "buscar" }, icono("buscar", 15),
          h("input", { class: "entrada", type: "search", placeholder: "Buscar cajón, colgante o texto…", "aria-label": "Buscar en los eventos", onInput: (e) => { S.busqueda = e.target.value.toLowerCase(); pintarEventos(); } }))),
      EV.cuerpo, EV.pie));
}

function pintarEventos() {
  if (!EV.cuerpo) return;
  if (S.eventos === null) { EV.cuerpo.replaceChildren(vacio("eventos", "Solo para administradores", "El historial de eventos es visible únicamente para el personal administrador.")); EV.pie.textContent = ""; return; }
  const pasa = (e, f) => f === "todos" || (f === "alertas" ? ES_ALERTA.has(e.tipo) : e.tipo === f);
  for (const c of EV.chips.children) { c.classList.toggle("activo", c.dataset.f === S.filtroEvento); c.lastChild.textContent = num(S.eventos.filter((e) => pasa(e, c.dataset.f)).length); }
  const lista = S.eventos.filter((e) => pasa(e, S.filtroEvento) && (!S.busqueda || e.descripcion.toLowerCase().includes(S.busqueda)));
  EV.pie.textContent = `Mostrando ${lista.length} de los ${S.eventos.length} eventos más recientes. Para periodos largos usa Reportes → Exportar.`;
  if (!lista.length) {
    EV.cuerpo.replaceChildren(vacio("eventos", S.eventos.length ? "Ningún evento coincide" : "Aún no hay eventos", S.eventos.length ? "Prueba con otro filtro o búsqueda." : "Se registran cuando un vehículo entra o sale de un cajón con cámara."));
    return;
  }
  EV.cuerpo.replaceChildren(h("div", { class: "tabla-caja" }, h("table", { class: "tabla" },
    h("thead", null, h("tr", null, ["Hora", "Tipo", "Cajón", "Detalle"].map((c) => h("th", { text: c })))),
    h("tbody", null, lista.map((e) => {
      const cajon = cajonDeEvento(e);
      return h("tr", { class: S.vistos.has(e.id) ? "" : "nuevo" },
        h("td", { class: "num", text: fechaHora(e.fecha) }),
        h("td", null, h("span", { class: "tipo-evento" }, h("span", { class: "insignia chica " + (TONO_EVENTO[e.tipo] || "") }, icono(ICONO_EVENTO[e.tipo] || "eventos", 13)), NOMBRE_EVENTO[e.tipo] || e.tipo)),
        h("td", null, cajon ? refCajon(cajon) : "—"), h("td", { text: e.descripcion }));
    })))));
}
