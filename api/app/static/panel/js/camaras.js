"use strict";
/* Video en vivo (MJPEG del servidor de visión) y la vista Cámaras. */

const PIXEL = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==";
const urlVideo = (cam) => `${VISION}/stream/${cam}`;

function conectarVideo(img, cam, fuera) {
  if (img.dataset.cam === cam && img.getAttribute("src")) return;
  img.dataset.cam = cam; if (fuera) fuera.hidden = true;
  img.onload = () => { if (fuera) fuera.hidden = true; };
  img.onerror = () => {
    if (fuera) {
      fuera.hidden = false;
      fuera.replaceChildren(icono("camara_off", 30), h("b", { text: "Sin señal de video" }), h("span", { text: "El servidor de visión no está transmitiendo. Los datos de ocupación siguen llegando; el video vuelve solo cuando el servidor arranque." }));
    }
    setTimeout(() => { if (img.dataset.cam === cam && img.dataset.activo === "1") { img.removeAttribute("src"); img.src = `${urlVideo(cam)}?t=${Date.now()}`; } }, 4000);
  };
  img.dataset.activo = "1"; img.src = `${urlVideo(cam)}?t=${Date.now()}`;
}
/* Quitar el atributo src no corta un MJPEG ya abierto: hay que reemplazarlo, o las conexiones se acumulan (el navegador permite 6 por servidor). */
function desconectarVideo(img) { if (!img) return; img.dataset.activo = "0"; img.dataset.cam = ""; img.src = PIXEL; }

/** Solo la vista visible mantiene sus videos abiertos. */
function gestionarVideos() {
  const v = $("video-resumen");
  if (v) { const cam = S.vista === "resumen" && $("modal").hidden ? camaraActiva() : null; if (cam) conectarVideo(v, cam, $("fuera-resumen")); else desconectarVideo(v); }
  document.querySelectorAll(".camara-tarj img.video").forEach((img) => { if (S.vista === "camaras" && $("modal").hidden) conectarVideo(img, img.dataset.camara, img.nextElementSibling); else desconectarVideo(img); });
}
function camaraActiva() {
  const lista = (S.estado ? S.estado.vision : []).map((v) => v.camara);
  if (!lista.length) return null;
  if (!S.camSel || !lista.includes(S.camSel)) S.camSel = lista[0];
  return S.camSel;
}

function abrirVideo(cam) {
  // Mientras se ve en grande, las demás cámaras se pausan: así el video ampliado siempre tiene una conexión libre
  document.querySelectorAll(".camara-tarj img.video").forEach(desconectarVideo); desconectarVideo($("video-resumen"));
  const aviso = h("div", { class: "fuera" }, h("span", { text: "Cargando el video…" }));
  const img = h("img", { class: "video", alt: "Video ampliado de " + cam });
  img.onload = () => { aviso.hidden = true; };
  img.onerror = () => { aviso.hidden = false; aviso.replaceChildren(icono("camara_off", 30), h("b", { text: "No se pudo abrir el video" }), h("span", { text: "El servidor de visión no responde. Cierra esta ventana y vuelve a intentarlo." })); };
  abrirModal(h("div", null, h("div", { class: "video-titulo" }, h("b", { text: cam }), etq("En vivo", "ok")), h("div", { class: "video grande" }, img, aviso)), true);
  img.src = `${urlVideo(cam)}?t=${Date.now()}`;
}

function vistaCamaras() { return h("section", { class: "vista", id: "v-camaras" }, h("div", { class: "camaras", id: "camaras" })); }

function pintarCamaras() {
  const cont = $("camaras"); if (!cont || !S.estado) return;
  const vision = new Map(S.estado.vision.map((v) => [v.camara, v]));
  const lista = (S.camaras ? S.camaras.map((c) => ({ codigo: c.camara, nombre: c.nombre, zona: c.zona, estado: c.estado, senal: c.ultimaSenal })) : S.estado.vision.map((v) => ({ codigo: v.camara, estado: "en_linea" })))
    .sort((a, b) => a.codigo.localeCompare(b.codigo));
  if (!lista.length) { cont.replaceChildren(vacio("camara_off", "No hay cámaras registradas")); return; }
  for (const c of lista) {
    let t = cont.querySelector(`[data-tarjeta="${CSS.escape(c.codigo)}"]`);
    const v = vision.get(c.codigo), enLinea = c.estado === "en_linea";
    if (!t) { t = h("section", { class: "tarjeta camara-tarj", "data-tarjeta": c.codigo }, h("div", { class: "tarjeta-cab" }), h("div", { class: "cuerpo-video" }), h("div", { class: "datos-video" })); cont.append(t); }
    t.querySelector(".tarjeta-cab").replaceChildren(
      h("div", null, h("h2", { text: c.codigo }), h("p", { text: c.nombre || (c.zona ? rotulo(c.zona) : "Sin zona asignada") })),
      etq(enLinea ? "En línea" : "Desconectada", enLinea ? "ok" : "critico"));
    const cv = t.querySelector(".cuerpo-video");
    if (v && !cv.querySelector("img")) {
      const img = h("img", { class: "video", "data-camara": c.codigo, alt: "Video de " + c.codigo });
      cv.replaceChildren(h("div", { class: "video", style: "cursor:zoom-in", onClick: () => abrirVideo(c.codigo) }, img, h("div", { class: "fuera", hidden: true })));
      if (S.vista === "camaras") conectarVideo(img, c.codigo, img.nextElementSibling);
    } else if (!v && !cv.querySelector(".sinvideo")) {
      const hay = S.estado.vision.length;
      cv.replaceChildren(h("div", { class: "video sinvideo" }, h("div", { class: "fuera" }, icono("camara_off", 30),
        h("b", { text: hay ? "Sin video configurado" : "Esperando al servidor de visión" }),
        h("span", { text: hay ? "Esta cámara todavía no tiene video conectado al modelo." : "Al encender el equipo puede tardar unos minutos. Esta pantalla se actualiza sola." }))));
    }
    t.querySelector(".datos-video").replaceChildren(...(v
      ? [["Vehículos", num(v.vehiculos)], ["Ocupados", num(v.ocupados)], ["Libres", num(v.libres)], ["Latencia", `${v.latencia_ms.toFixed(0)} ms`], ["Video", `${num(v.fps_video, 1)} fps`]]
      : [["Última señal", hace(c.senal)]]).map(([k, val]) => h("div", null, h("span", { text: k }), h("b", { text: val }))));
  }
}
