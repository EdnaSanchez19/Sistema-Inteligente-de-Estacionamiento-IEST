"use strict";
/* Núcleo del panel: acceso a la API, estado compartido, utilidades de DOM, formatos, iconos, modal y avisos.
   Todo el texto que llega del servidor se escribe con textContent (nunca innerHTML). */

const API = location.origin;
const VISION = new URLSearchParams(location.search).get("vision") || `${location.protocol}//${location.hostname}:8100`;
const SVG_NS = "http://www.w3.org/2000/svg";
const $ = (id) => document.getElementById(id);

/** Crea un elemento. props: class, text, style, on<Evento>, o atributos; los hijos nulos o false se omiten. */
function h(tag, props, ...hijos) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k === "style") el.style.cssText = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2).toLowerCase(), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const hijo of hijos.flat()) if (hijo != null && hijo !== false) el.append(hijo);
  return el;
}
/** Igual que h(), para elementos SVG. */
function s(tag, attrs, ...hijos) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "text") el.textContent = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2).toLowerCase(), v);
    else el.setAttribute(k, v);
  }
  for (const hijo of hijos.flat()) if (hijo != null && hijo !== false) el.append(hijo);
  return el;
}

/* Iconos de trazo (24×24). Son constantes del propio panel, por eso se pueden insertar como marcado. */
const ICONOS = {
  resumen: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  mapa: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M9.5 17V7h3.2a3 3 0 0 1 0 6H9.5"/>',
  camara: '<path d="M15.5 10.5 21 7v10l-5.500-3.500"/><rect x="2.500" y="6" width="13" height="12" rx="2.500"/>',
  camara_off: '<path d="M3 3l18 18"/><path d="M15.500 10.500 21 7v10"/><path d="M9 6h4a2.500 2.500 0 0 1 2.500 2.500v4M15.500 16a2.500 2.500 0 0 1-2.500 2H5a2.500 2.500 0 0 1-2.500-2.500v-7A2.500 2.500 0 0 1 4.500 6.050"/>',
  alerta: '<path d="M6 9a6 6 0 0 1 12 0c0 6 2.500 7.500 2.500 7.500h-17S6 15 6 9z"/><path d="M10 20a2.200 2.200 0 0 0 4 0"/>',
  eventos: '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="3.500" cy="6" r="1"/><circle cx="3.500" cy="12" r="1"/><circle cx="3.500" cy="18" r="1"/>',
  reportes: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  admin: '<circle cx="9" cy="8" r="3.500"/><path d="M2.500 20a6.500 6.500 0 0 1 13 0"/><path d="M16 4.700a3.500 3.500 0 0 1 0 6.600M18.500 14.300A6.500 6.500 0 0 1 21.500 20"/>',
  sistema: '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="10" y="10" width="4" height="4" rx=".5"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
  sol: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2.500M12 19.500V22M4.200 4.200 6 6M18 18l1.800 1.800M2 12h2.500M19.500 12H22M4.200 19.800 6 18M18 6l1.800-1.800"/>',
  luna: '<path d="M20.500 14.500A8.500 8.500 0 0 1 9.500 3.500a8.500 8.500 0 1 0 11 11z"/>',
  salir: '<path d="M9 21H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3"/><path d="M16 17l5-5-5-5M21 12H9"/>',
  coche: '<path d="M5 11l1.600-4.300A2.500 2.500 0 0 1 9 5h6a2.500 2.500 0 0 1 2.400 1.700L19 11"/><rect x="3" y="11" width="18" height="6" rx="2"/><path d="M6 17v2M18 17v2"/><circle cx="7.500" cy="14" r=".6"/><circle cx="16.500" cy="14" r=".6"/>',
  buscar: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.500-4.500"/>',
  descarga: '<path d="M12 3v12M7 10l5 5 5-5M4 21h16"/>',
  check: '<path d="M4.500 12.500l5 5 10-11"/>',
  reloj: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.500 2"/>',
  obstaculo: '<path d="M12 3.500 2.500 20h19z"/><path d="M12 10v4.500M12 17.500v.1"/>',
  entrada: '<path d="M4 12h13M12 6l6 6-6 6"/>',
  salida: '<path d="M20 12H7M12 6l-6 6 6 6"/>',
  pulso: '<path d="M2 12h4l3-8 4 16 3-8h6"/>',
  base: '<ellipse cx="12" cy="5.500" rx="8" ry="3"/><path d="M4 5.500v13c0 1.700 3.600 3 8 3s8-1.300 8-3v-13M4 12c0 1.700 3.600 3 8 3s8-1.300 8-3"/>',
  nube: '<path d="M7 18a4.500 4.500 0 0 1-.5-9 6 6 0 0 1 11.600 1.500A3.800 3.800 0 0 1 17.500 18z"/>',
  pantalla: '<rect x="2.500" y="4" width="14" height="10" rx="1.500"/><path d="M6 18h7M9.500 14v4"/><rect x="17.500" y="9" width="4.500" height="9" rx="1"/>',
  usuario: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  flecha: '<path d="M9 6l6 6-6 6"/>',
  ampliar: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
  lleno: '<circle cx="12" cy="12" r="9"/><path d="M12 7.500v5M12 16v.1"/>',
};
function icono(nombre, tam) {
  const el = s("svg", { class: "ico", viewBox: "0 0 24 24", width: tam || 18, height: tam || 18, fill: "none", stroke: "currentColor", "stroke-width": 1.8, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" });
  el.innerHTML = ICONOS[nombre] || "";
  return el;
}

/* ── Textos y formatos ── */
const ESTADO = { libre: "Libre", ocupado: "Ocupado", obstruido: "Obstruido", reservado: "Reservado", fuera_de_servicio: "Fuera de servicio" };
const TIPO_ESPACIO = { general: "General", discapacidad: "Accesibilidad", directivo: "Directivo", visitante: "Visitante", motocicleta: "Motocicleta" };
const MARCA_TIPO = { discapacidad: "♿", directivo: "★", visitante: "V", motocicleta: "M" };
const NOMBRE_EVENTO = { entrada: "Entrada", salida: "Salida", cambio_ocupacion: "Cambio manual", error_deteccion: "Confianza baja", camara_desconectada: "Cámara caída", camara_restablecida: "Cámara restablecida", obstruccion: "Obstrucción", obstruccion_retirada: "Obstrucción retirada" };
const TONO_EVENTO = { entrada: "ok", salida: "", cambio_ocupacion: "info", error_deteccion: "critico", camara_desconectada: "critico", camara_restablecida: "ok", obstruccion: "aviso", obstruccion_retirada: "ok" };
const ICONO_EVENTO = { entrada: "entrada", salida: "salida", cambio_ocupacion: "usuario", error_deteccion: "lleno", camara_desconectada: "camara_off", camara_restablecida: "camara", obstruccion: "obstaculo", obstruccion_retirada: "check" };
const ESTANCIA_LARGA_S = 4 * 3600;
const DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

function dur(seg) {
  if (seg == null) return "—";
  if (seg < 60) return Math.round(seg) + " s";
  const m = Math.floor(seg / 60); if (m < 60) return m + " min";
  const hh = Math.floor(m / 60), mm = m % 60; if (hh < 24) return mm ? `${hh} h ${mm} min` : `${hh} h`;
  const d = Math.floor(hh / 24), h2 = hh % 24; return h2 ? `${d} d ${h2} h` : `${d} d`;
}
/** Duración en muy poco espacio, para escribirla dentro de un cajón: 45m, 3h, 2d. */
function durCorta(seg) {
  if (seg == null) return "";
  const m = Math.floor(seg / 60); if (m < 1) return "<1m"; if (m < 60) return m + "m";
  const hh = Math.floor(m / 60); return hh < 24 ? hh + "h" : Math.floor(hh / 24) + "d";
}
const textoDuracion = (e) => (e.monitoreado && e.duracion_s != null ? (e.desde_observado ? "" : "al menos ") + dur(e.duracion_s) : "—");
const hora = (iso) => (iso ? new Date(iso).toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" }) : "—");
const fechaHora = (iso) => (iso ? new Date(iso).toLocaleString("es-MX", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—");
const hace = (iso) => (iso ? "hace " + dur(Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)) : "—");
const pct = (parte, total) => (total ? Math.round((parte / total) * 100) : 0);
const num = (n, dec) => (n == null ? "—" : Number(n).toLocaleString("es-MX", { maximumFractionDigits: dec || 0 }));
const gravedad = (porcentaje) => (porcentaje >= 90 ? "critico" : porcentaje >= 70 ? "aviso" : "ok");
const TEXTO_GRAVEDAD = { ok: "Con espacio", aviso: "Llenándose", critico: "Casi lleno" };
/** Fecha local AAAA-MM-DD (lo que esperan los reportes). */
const fechaLocal = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/* ── Estado compartido ── */
let token = sessionStorage.getItem("token");
let timers = [];
const S = {
  yo: null, estado: null, estancias: [], coches: null, espacios: [], eventos: null, camaras: null, avisos: [], alertas: null, serie: [],
  vista: "resumen", camSel: null, isla: "todas", filtroEvento: "todos", busqueda: "",
  mapa: { modo: "croquis", rotulo: "numero", filtro: "todos", buscar: "" },
  alertasTab: "activas", historialAlertas: null,
  reporte: { dias: 7, zona: "", datos: null, cargando: false },
  previo: new Map(), vistos: new Set(), primera: true, latCam: {}, admin: {},
};
const esAdmin = () => !!S.yo && S.yo.rol === "admin";

/* ── API ── */
function toast(msg, tipo) {
  const t = h("div", { class: "toast " + (tipo || ""), text: msg });
  $("toasts").append(t); setTimeout(() => t.remove(), 6000);
}
async function api(path, opciones) {
  const r = await fetch(API + path, { ...(opciones || {}), headers: { Authorization: "Bearer " + token, ...((opciones && opciones.headers) || {}) } });
  if (r.status === 401) { cerrarSesion(); throw new Error("Sesión expirada"); }
  if (r.status === 403) return null;
  if (!r.ok) { let d = ""; try { d = (await r.json()).detail; } catch (_) {} throw new Error(typeof d === "string" && d ? d : "Error " + r.status); }
  return r.json();
}
const post = (path, cuerpo, metodo) => api(path, { method: metodo || "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo || {}) });

/** Descarga un CSV protegido: se pide con el token y se guarda desde memoria. */
async function descargarCsv(path, nombre) {
  const r = await fetch(API + path, { headers: { Authorization: "Bearer " + token } });
  if (!r.ok) throw new Error(r.status === 403 ? "Solo un administrador puede exportar" : "No se pudo generar el archivo");
  const url = URL.createObjectURL(await r.blob());
  const a = h("a", { href: url, download: nombre }); document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

/* ── Tema claro / oscuro ── */
const temaOscuro = () => (document.documentElement.dataset.tema ? document.documentElement.dataset.tema === "oscuro" : matchMedia("(prefers-color-scheme: dark)").matches);
function alternarTema() {
  const nuevo = temaOscuro() ? "claro" : "oscuro";
  document.documentElement.dataset.tema = nuevo;
  try { localStorage.setItem("tema", nuevo); } catch (_) {}
  const b = $("tema"); if (b) b.replaceChildren(icono(nuevo === "oscuro" ? "sol" : "luna"));
}

/* ── Modal ── */
function abrirModal(contenido, ancha) {
  $("modal").querySelector(".modal-caja").classList.toggle("ancha", !!ancha);
  $("modal-contenido").replaceChildren(contenido);
  $("modal").hidden = false;
}
function cerrarModal() {
  if ($("modal").hidden) return;
  const img = $("modal-contenido").querySelector("img.video");
  if (img) desconectarVideo(img);  // quitar el nodo no corta un MJPEG: hay que cambiarle la fuente
  $("modal").hidden = true; $("modal-contenido").replaceChildren();
  gestionarVideos();
}
$("modal").addEventListener("click", (e) => { if (e.target === $("modal") || e.target.closest(".modal-cerrar")) cerrarModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") cerrarModal(); });

/* ── Globo de datos compartido (cajones y gráficas) ── */
/** filas: [[etiqueta, valor], ...] o cadenas sueltas. */
function mostrarTip(titulo, filas, x, y) {
  const tip = $("tip");
  tip.replaceChildren(titulo ? h("b", { text: titulo }) : null, ...(filas || []).map((f) => (Array.isArray(f) ? h("div", null, h("span", { text: f[0] }), h("span", { text: f[1] })) : h("div", null, h("span", { text: f })))));
  tip.hidden = false;
  const r = tip.getBoundingClientRect(), m = 12;
  let izq = x + 14, arr = y + 14;
  if (izq + r.width > innerWidth - m) izq = x - r.width - 14;
  if (arr + r.height > innerHeight - m) arr = y - r.height - 14;
  tip.style.left = Math.max(m, izq) + "px"; tip.style.top = Math.max(m, arr) + "px";
}
const ocultarTip = () => { $("tip").hidden = true; };

/* ── Piezas pequeñas reutilizables ── */
const tarjeta = (titulo, sub, accion, ...cuerpo) => h("section", { class: "tarjeta" },
  h("div", { class: "tarjeta-cab" }, h("div", null, h("h2", { text: titulo }), sub ? h("p", { text: sub }) : null), accion || null), ...cuerpo);
const vacio = (ico, titulo, texto) => h("div", { class: "vacio" }, icono(ico, 26), h("b", { text: titulo }), texto ? h("span", { text: texto }) : null);
const etq = (texto, tono) => h("span", { class: "etq " + (tono || ""), text: texto });
/** Control segmentado: opciones [[valor, texto], ...]. */
function segmentado(opciones, actual, alElegir) {
  const caja = h("div", { class: "seg", role: "tablist" });
  for (const [valor, texto] of opciones) {
    caja.append(h("button", { type: "button", class: valor === actual ? "activo" : "", text: texto, "data-v": valor, onClick: () => {
      for (const b of caja.children) b.classList.toggle("activo", b.dataset.v === String(valor));
      alElegir(valor);
    } }));
  }
  return caja;
}
