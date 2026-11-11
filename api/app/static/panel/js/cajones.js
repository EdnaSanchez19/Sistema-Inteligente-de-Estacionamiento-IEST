"use strict";
/* Cajones: agrupación por zona, mosaicos que se actualizan en su sitio (sin volver a crearlos cada 2 s),
   globo de datos al pasar el cursor y la ficha de detalle de un cajón. */

/** Las islas se guardan con una letra (A, B…); para la gente son "Fila 1", "Fila 2"… */
function rotulo(nombre) { return nombre.length === 1 ? "Fila " + (nombre.charCodeAt(0) - 64) : nombre; }

function agruparIslas() {
  const m = new Map();
  for (const e of S.espacios) {
    if (!m.has(e.zona)) m.set(e.zona, { nombre: e.zona, total: 0, monit: 0, libres: 0, ocupados: 0, obstruidos: 0, lista: [] });
    const i = m.get(e.zona); i.total++; i.lista.push(e);
    if (e.monitoreado) { i.monit++; if (e.estado === "libre") i.libres++; if (e.estado === "ocupado") i.ocupados++; if (e.estado === "obstruido") i.obstruidos++; }
  }
  return [...m.values()].sort((a, b) => (a.nombre.length > 1) - (b.nombre.length > 1) || a.nombre.localeCompare(b.nombre));  // primero las islas, luego el perímetro
}

const estanciaLarga = (e) => e.monitoreado && e.estado === "ocupado" && e.duracion_s != null && e.duracion_s >= ESTANCIA_LARGA_S;

/** ¿El cajón pasa el filtro y la búsqueda de la vista de mapa? */
function pasaFiltro(e) {
  const f = S.mapa.filtro, q = S.mapa.buscar.trim().toUpperCase();
  if (q && !e.numero.toUpperCase().includes(q)) return false;
  if (f === "todos") return true;
  if (f === "sin") return !e.monitoreado;
  if (f === "largo") return estanciaLarga(e);
  if (f === "reservado") return e.estado === "reservado";
  return e.monitoreado && e.estado === f;
}

/** Pinta la lista de cajones dentro de `cont` reutilizando los botones que ya existen (clave: número de cajón).
 *  opciones: { filtrar: aplica el filtro del mapa, tiempo: escribe el tiempo transcurrido en vez del número } */
function pintarCajones(cont, lista, opciones) {
  const o = opciones || {};
  const mosaicos = cont._mosaicos || (cont._mosaicos = new Map()), presentes = new Set();
  for (const e of lista) {
    presentes.add(e.numero);
    let b = mosaicos.get(e.numero);
    if (!b) {
      b = h("button", { type: "button", class: "cajon", "data-n": e.numero }, h("span"), h("small"));
      mosaicos.set(e.numero, b); cont.append(b);
    }
    const visible = e.monitoreado || e.estado !== "libre";
    const clase = "cajon" + (visible ? " " + e.estado : "") + (e.monitoreado ? "" : " sin") + (estanciaLarga(e) ? " largo" : "") + (o.filtrar && !pasaFiltro(e) ? " apagado" : "");
    const destello = b.classList.contains("cambio");
    if (b.dataset.clase !== clase) { b.dataset.clase = clase; b.className = clase + (destello ? " cambio" : ""); }
    if (!S.primera && S.previo.has(e.numero) && S.previo.get(e.numero) !== e.estado + e.monitoreado && !destello) {
      b.classList.add("cambio"); setTimeout(() => b.classList.remove("cambio"), 1700);
    }
    const corto = e.numero.split("-")[1] || e.numero, conTiempo = o.tiempo && e.monitoreado && e.estado !== "libre" && e.duracion_s != null;
    const principal = conTiempo ? durCorta(e.duracion_s) : corto, secundario = conTiempo ? corto : MARCA_TIPO[e.tipo] || "";
    if (b.firstChild.textContent !== principal) b.firstChild.textContent = principal;
    if (b.lastChild.textContent !== secundario) b.lastChild.textContent = secundario;
    b.setAttribute("aria-label", `Cajón ${e.numero}, ${e.monitoreado ? ESTADO[e.estado] : "sin monitoreo"}`);
  }
  for (const [n, b] of mosaicos) if (!presentes.has(n)) { b.remove(); mosaicos.delete(n); }
}

/* Un solo escucha para todos los cajones de la página: globo al pasar el cursor y ficha al hacer clic. */
document.addEventListener("mousemove", (ev) => {
  const b = ev.target.closest && ev.target.closest(".cajon");
  if (!b) { if (!$("tip").hidden && $("tip").dataset.de === "cajon") { ocultarTip(); $("tip").dataset.de = ""; } return; }
  const e = S.porNumero && S.porNumero.get(b.dataset.n); if (!e) return;
  const filas = [["Estado", e.monitoreado ? ESTADO[e.estado] : "Sin monitoreo"]];
  if (e.monitoreado && e.estado === "obstruido") filas.push(["Objeto", e.objeto || "no identificado"]);
  if (e.monitoreado) filas.push([e.estado === "ocupado" ? "Estacionado hace" : "Así desde hace", textoDuracion(e)]);
  filas.push(["Tipo", TIPO_ESPACIO[e.tipo] || e.tipo]);
  $("tip").dataset.de = "cajon";
  mostrarTip(`Cajón ${e.numero} · ${rotulo(e.zona)}`, filas, ev.clientX, ev.clientY);
});
document.addEventListener("click", (ev) => {
  const b = ev.target.closest && ev.target.closest(".cajon, .ref-cajon");
  if (b && b.dataset.n) { ocultarTip(); abrirCajon(b.dataset.n); }
});

/** Enlace a la ficha de un cajón, para usar dentro de listas y tablas. */
const refCajon = (numero) => h("button", { type: "button", class: "ref-cajon", "data-n": numero, text: numero });

function leyendaCajones() {
  const marca = (clase, texto) => h("span", null, h("i", { class: clase }), texto);
  return h("div", { class: "leyenda" }, marca("m-libre", "Libre"), marca("m-ocupado", "Ocupado"), marca("m-obstruido", "Obstruido"), marca("m-reservado", "Reservado"), marca("m-fuera", "Fuera de servicio"), marca("m-sin", "Sin cámara"));
}

async function abrirCajon(numero) {
  abrirModal(h("div", { class: "vacio", text: "Cargando…" }));
  try {
    const d = await api("/espacios/" + encodeURIComponent(numero));
    const dl = h("dl", { class: "detalle" });
    const fila = (k, v) => dl.append(h("dt", { text: k }), h("dd", null, v));
    if (d.monitoreado && d.estado === "obstruido") fila("Objeto", d.objeto || "no identificado");
    if (d.monitoreado) {
      fila(d.estado === "ocupado" ? "Estacionado desde hace" : "En este estado desde hace", d.desde_observado ? dur(d.duracion_s) : "al menos " + dur(d.duracion_s));
      if (!d.desde_observado) fila("", h("span", { style: "font-weight:400;color:var(--tenue);font-size:12px", text: "La cámara empezó a verlo así: el tiempo real puede ser mayor." }));
      fila("Desde", fechaHora(d.desde));
    }
    fila("Tipo", TIPO_ESPACIO[d.tipo] || d.tipo);
    fila("Cámara", d.camara || "Ninguna");
    fila("Última actualización", d.monitoreado ? fechaHora(d.actualizado) : "—");
    if (esAdmin()) fila("Ocupado por", d.colgante ? `Colgante ${d.colgante.codigo} (${d.colgante.tipo})` : d.estado === "ocupado" ? "Vehículo sin colgante identificado" : "—");

    const visible = d.monitoreado || d.estado !== "libre";
    const partes = [
      h("div", { class: "detalle-cab" },
        h("div", { class: "detalle-num cajon " + (visible ? d.estado : "sin"), text: d.numero }),
        h("div", null, h("h2", { text: "Cajón " + d.numero }), h("p", { text: rotulo(d.zona) })),
        h("div", { style: "margin-left:auto" }, d.monitoreado ? etq(ESTADO[d.estado], d.estado) : etq("Sin monitoreo"))),
      dl,
    ];
    if (esAdmin()) {
      partes.push(h("div", { class: "detalle-sub", text: "Historial del cajón" }));
      partes.push(d.historial && d.historial.length ? h("div", { class: "lista", style: "max-height:240px;overflow-y:auto" }, d.historial.map((e) => filaEvento(e))) : vacio("eventos", "Sin eventos registrados"));
    }
    $("modal-contenido").replaceChildren(...partes);
  } catch (e) { $("modal-contenido").replaceChildren(vacio("lleno", "No se pudo cargar el cajón", e.message)); }
}
