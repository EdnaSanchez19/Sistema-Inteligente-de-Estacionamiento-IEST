"use strict";
/* Arranque: inicio de sesión, armazón (menú + barra superior), navegación entre vistas y ciclos de actualización. */

/* Menú por grupos. `admin: true` → solo lo ve un administrador (la vista de operador es este mismo panel con el menú recortado). */
const MENU = [
  ["Operación", [
    { id: "resumen", nombre: "Resumen", corto: "Inicio", icono: "resumen", sub: "Estado del estacionamiento en este momento" },
    { id: "mapa", nombre: "Mapa de cajones", corto: "Mapa", icono: "mapa", sub: "Cada cajón en vivo: libre, ocupado, obstruido y tiempo transcurrido" },
    { id: "camaras", nombre: "Cámaras", corto: "Cámaras", icono: "camara", sub: "Video en vivo con las detecciones del modelo" },
  ]],
  ["Supervisión", [
    { id: "alertas", nombre: "Alertas", corto: "Alertas", icono: "alerta", sub: "Lo que pide atención: estancias excedidas, obstrucciones y cámaras caídas", admin: true },
    { id: "eventos", nombre: "Eventos", corto: "Eventos", icono: "eventos", sub: "Bitácora de entradas, salidas y avisos", admin: true },
    { id: "reportes", nombre: "Reportes", corto: "Reportes", icono: "reportes", sub: "Ocupación histórica, horas pico y exportación de datos", admin: true },
  ]],
  ["Configuración", [
    { id: "admin", nombre: "Administración", corto: "Admin", icono: "admin", sub: "Usuarios, vehículos y colgantes", admin: true },
    { id: "sistema", nombre: "Sistema", corto: "Sistema", icono: "sistema", sub: "Componentes y modelo de visión" },
  ]],
];
const VISTA = {
  resumen: [vistaResumen, pintarResumen], mapa: [vistaMapa, pintarMapa], camaras: [vistaCamaras, pintarCamaras], alertas: [vistaAlertas, pintarAlertas],
  eventos: [vistaEventos, pintarEventos], reportes: [vistaReportes, () => {}], admin: [vistaAdmin, () => {}], sistema: [vistaSistema, pintarSistema],
};  // Reportes y Administración no se repintan en cada ciclo: se pintan al entrar y cuando llegan sus datos
const vistasPermitidas = () => MENU.flatMap(([, items]) => items).filter((v) => !v.admin || esAdmin());
const infoVista = (id) => vistasPermitidas().find((v) => v.id === id);

/* ── Inicio de sesión ── */
function vistaLogin(mensaje) {
  timers.forEach(clearInterval); timers = [];
  const app = $("app"); app.className = "login"; app.replaceChildren();
  const correo = h("input", { class: "entrada", type: "email", placeholder: "nombre@iest.edu.mx", required: true, autocomplete: "username" });
  const clave = h("input", { class: "entrada", type: "password", placeholder: "Contraseña", required: true, autocomplete: "current-password" });
  const error = h("div", { class: "login-error", role: "alert", text: mensaje || "" });
  const boton = h("button", { class: "btn primario", type: "submit", text: "Entrar" });
  const form = h("form", { class: "login-form" },
    h("div", { class: "marca-logo", text: "P" }), h("h2", { text: "Inicia sesión" }), h("p", { text: "Usa tu correo institucional." }),
    h("label", { class: "campo" }, h("span", { text: "Correo" }), correo), h("label", { class: "campo" }, h("span", { text: "Contraseña" }), clave), error, boton);
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault(); boton.disabled = true; error.textContent = "";
    try {
      const r = await fetch(API + "/auth/login", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: new URLSearchParams({ username: correo.value.trim(), password: clave.value }) });
      if (!r.ok) throw new Error(r.status === 401 ? "Correo o contraseña incorrectos" : "Error " + r.status);
      token = (await r.json()).access_token; sessionStorage.setItem("token", token); iniciar();
    } catch (e) { error.textContent = e.message; boton.disabled = false; }
  });
  const dato = (valor, texto) => h("div", null, h("b", { text: valor }), h("span", { text: texto }));
  app.append(
    h("div", { class: "login-portada" },
      h("div", { class: "marca" }, h("div", { class: "marca-logo", text: "P" }), h("div", null, h("b", { text: "IEST Anáhuac" }), h("span", { text: "Sistema inteligente de estacionamiento" }))),
      h("div", { class: "login-lema" }, h("h1", { text: "Encuentra tu lugar antes de llegar" }),
        h("p", { text: "Cámaras y visión por computadora que muestran en tiempo real qué cajones están libres, ocupados u obstruidos." }),
        h("div", { class: "login-datos" }, dato("2 s", "entre cada actualización"), dato("24/7", "monitoreo continuo"), dato("En vivo", "cajón por cajón")))),
    h("div", { class: "login-acceso" },
      h("button", { class: "icono-btn", id: "tema", type: "button", title: "Cambiar tema", "aria-label": "Cambiar entre modo claro y oscuro", onClick: alternarTema }, icono(temaOscuro() ? "sol" : "luna")),
      form, h("p", { class: "login-pie", text: "IEST Anáhuac · Tampico" })));
  correo.focus();
}
function cerrarSesion() {
  token = null; sessionStorage.removeItem("token");
  Object.assign(S, { yo: null, estado: null, espacios: [], eventos: null, camaras: null, alertas: null, historialAlertas: null, primera: true });
  S.reporte.datos = null;
  vistaLogin();
}

/* ── Armazón ── */
function armarEstructura() {
  const app = $("app"); app.className = "shell"; app.replaceChildren();
  const nav = h("nav", { id: "nav", "aria-label": "Secciones" });
  for (const [grupo, items] of MENU) {
    const visibles = items.filter((v) => !v.admin || esAdmin()); if (!visibles.length) continue;
    nav.append(h("div", { class: "nav-titulo", text: grupo }));
    for (const v of visibles) nav.append(h("button", { type: "button", class: "nav-item", "data-vista": v.id, onClick: () => ir(v.id) },
      icono(v.icono, 18), h("span", { class: "nav-largo", text: v.nombre }), h("span", { class: "nav-corto", text: v.corto }),
      v.id === "alertas" || v.id === "eventos" ? h("span", { class: "nav-badge", id: "badge-" + v.id, hidden: true }) : null));
  }
  const inicial = (S.yo.nombre || "?").trim().charAt(0).toUpperCase();
  app.append(
    h("aside", { class: "lado" },
      h("div", { class: "marca" }, h("div", { class: "marca-logo", text: "P" }), h("div", null, h("b", { text: "IEST Anáhuac" }), h("span", { text: "Estacionamiento" }))),
      nav, h("div", { class: "lado-pie", id: "lado-pie" })),
    h("main", { class: "principal" },
      h("header", { class: "barra" },
        h("div", { class: "barra-titulo" }, h("h1", { id: "titulo" }), h("p", { id: "subtitulo" })),
        h("div", { class: "barra-acc" },
          h("span", { class: "vivo", id: "vivo" }, h("i"), h("span", { text: "En vivo" })),
          h("button", { class: "pildora", id: "salud", type: "button", title: "Ver el estado del sistema", onClick: () => ir("sistema") }, h("i"), h("span")),
          esAdmin() ? h("button", { class: "icono-btn", id: "campana", type: "button", title: "Alertas", "aria-label": "Ver alertas", onClick: () => ir("alertas") }, icono("alerta"), h("span", { class: "punto", hidden: true })) : null,
          h("button", { class: "icono-btn", id: "tema", type: "button", title: "Cambiar tema", "aria-label": "Cambiar entre modo claro y oscuro", onClick: alternarTema }, icono(temaOscuro() ? "sol" : "luna")),
          h("div", { class: "usuario" }, h("div", { class: "avatar", text: inicial }), h("div", null, h("b", { text: S.yo.nombre }), h("span", { text: esAdmin() ? "Administrador" : S.yo.rol })),
            h("button", { class: "icono-btn", type: "button", title: "Cerrar sesión", "aria-label": "Cerrar sesión", onClick: cerrarSesion }, icono("salir"))))),
      vistasPermitidas().map((v) => VISTA[v.id][0]())));
}

function ir(vista) {
  if (!infoVista(vista)) vista = "resumen";
  const info = infoVista(vista);
  S.vista = vista; history.replaceState(null, "", "#" + vista);
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("activo", b.dataset.vista === vista));
  document.querySelectorAll(".vista").forEach((v) => v.classList.toggle("activa", v.id === "v-" + vista));
  $("titulo").textContent = info.nombre; $("subtitulo").textContent = info.sub;
  if (vista === "admin") cargarAdmin();
  if (vista === "alertas" && S.alertasTab === "historial") cargarHistorialAlertas();
  gestionarVideos(); pintar();
  if (vista === "reportes") { pintarReportes(); cargarReportes(); }
  if (vista === "eventos" && S.eventos) S.eventos.forEach((e) => S.vistos.add(e.id));  // se pintan como nuevos una vez; después ya cuentan como vistos
  if (vista === "resumen") pintarSerieResumen();
  window.scrollTo(0, 0);
}

/* ── Lo que se pinta en todas las vistas ── */
function pintarComun() {
  const e = S.estado; if (!e || !$("salud")) return;
  const bdOk = e.base_de_datos.estado === "ok", camOk = e.camaras.en_linea === e.camaras.total && e.camaras.total > 0;
  const fallas = [!bdOk && "base de datos", !e.vision_conectada && "visión", e.vision_conectada && !camOk && `${e.camaras.total - e.camaras.en_linea} cámara(s)`].filter(Boolean);
  const salud = $("salud"); salud.className = "pildora" + (!bdOk || !e.vision_conectada ? " mal" : fallas.length ? " aviso" : "");
  salud.lastChild.textContent = fallas.length ? "Revisar: " + fallas.join(", ") : "Todo funcionando";
  $("lado-pie").textContent = `v${e.version} · ${e.camaras.en_linea}/${e.camaras.total} cámaras en línea`;

  const pendientes = (S.alertas || []).filter((a) => !a.atendida).length;
  const campana = $("campana"); if (campana) { campana.lastChild.hidden = !pendientes; campana.lastChild.textContent = pendientes > 99 ? "99+" : pendientes; }
  const ba = $("badge-alertas"); if (ba) { ba.hidden = !pendientes; ba.textContent = pendientes; }
  const be = $("badge-eventos"); if (be) { const nuevos = S.eventos ? S.eventos.filter((x) => !S.vistos.has(x.id)).length : 0; be.hidden = !(nuevos && S.vista !== "eventos"); be.textContent = nuevos; }
}
function pintar() {
  if (!S.estado) return;
  pintarComun();
  const v = VISTA[S.vista]; if (v) v[1]();
}
function conexion(ok) {
  const v = $("vivo"); if (!v) return;
  v.className = "vivo" + (ok ? "" : " mal"); v.lastChild.textContent = ok ? "En vivo" : "Sin conexión";
}

/* ── Ciclos ── */
async function cicloRapido() {
  const [estado, espacios, estancias, coches] = await Promise.all([api("/sistema/estado"), api("/espacios"), api("/sistema/estancias?limite=8"), api("/sistema/vehiculos?limite=8").catch(() => null)]);
  S.estado = estado; S.espacios = espacios || []; S.estancias = estancias || []; S.coches = coches;
  S.porNumero = new Map(S.espacios.map((e) => [e.numero, e]));
  for (const x of estado.vision) { const a = (S.latCam[x.camara] = S.latCam[x.camara] || []); a.push(x.latencia_ms); if (a.length > 60) a.shift(); }
  pintar();
  S.previo = new Map(S.espacios.map((e) => [e.numero, e.estado + e.monitoreado])); S.primera = false; conexion(true);
}
async function cicloLento() {
  const [avisos, eventos, camaras, alertas] = await Promise.all([api("/notificaciones"), api("/eventos?limit=200"), api("/camaras"), esAdmin() ? api("/alertas?estado=activas&limite=100").catch(() => null) : null]);
  S.avisos = avisos || []; S.camaras = camaras;
  if (alertas) {
    if (S.alertas) {  // avisa solo de las que aparecen después de abrir el panel
      const conocidas = new Set(S.alertas.map((a) => a.id));
      for (const a of alertas) if (!conocidas.has(a.id)) toast(a.mensaje, "mal");
    }
    S.alertas = alertas;
  }
  if (eventos && S.vistos.size) {
    for (const e of eventos.filter((x) => !S.vistos.has(x.id))) { if (e.tipo === "camara_desconectada") toast(e.descripcion, "mal"); else if (e.tipo === "camara_restablecida") toast(e.descripcion, "ok"); }
  }
  S.eventos = eventos;
  if (eventos && !S.vistos.size) eventos.forEach((e) => S.vistos.add(e.id));  // lo que ya estaba al abrir no cuenta como nuevo
  pintar();
  if (eventos && S.vista === "eventos") eventos.forEach((e) => S.vistos.add(e.id));
}
async function cicloSerie() { S.serie = (await api("/sistema/historial?minutos=60")) || []; pintarSerieResumen(); }

let redibujo = 0;
function alCambiarTamano() {
  clearTimeout(redibujo);
  redibujo = setTimeout(() => { if (!S.yo) return; if (S.vista === "resumen") pintarSerieResumen(); if (S.vista === "reportes") pintarReportes(); }, 150);
}

async function iniciar() {
  try { S.yo = await api("/auth/me"); } catch (e) { return vistaLogin(e.message === "Sesión expirada" ? "" : e.message); }
  Object.assign(S, { primera: true, vistos: new Set(), eventos: null, alertas: null });
  armarEstructura();
  let inicial = (location.hash || "#resumen").slice(1);
  if (inicial === "islas") { inicial = "mapa"; S.mapa.modo = "filas"; }  // enlace del panel anterior
  const aviso = () => conexion(false);
  await Promise.all([cicloRapido().catch(aviso), cicloLento().catch(() => {}), cicloSerie().catch(() => {})]);
  ir(inicial);
  timers.forEach(clearInterval);
  timers = [setInterval(() => cicloRapido().catch(aviso), 2000), setInterval(() => cicloLento().catch(() => {}), 4000), setInterval(() => cicloSerie().catch(() => {}), 10000)];
}
window.addEventListener("resize", alCambiarTamano);
window.addEventListener("hashchange", () => { const v = (location.hash || "").slice(1); if (S.yo && v !== S.vista && infoVista(v)) ir(v); });

token ? iniciar() : vistaLogin();
