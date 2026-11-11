"use strict";
/* Vista Sistema: el recorrido del dato (cámara → visión → API → base de datos → pantallas) y el estado de cada modelo. */

const SI = { tarjetas: new Map() };
const LUZ = { normal: "Normal", baja: "Poca luz", noche: "Noche", contraluz: "Contraluz", sobreexpuesta: "Sobreexpuesta" };

function vistaSistema() {
  SI.tarjetas = new Map();
  SI.flujo = h("div", { class: "flujo" });
  SI.modelos = h("div", { class: "modelos" });
  return h("section", { class: "vista", id: "v-sistema" },
    tarjeta("Flujo del sistema", "De la cámara a la pantalla: cada bloque indica si está funcionando", null, SI.flujo),
    SI.modelos);
}

function pintarSistema() {
  if (!SI.flujo || !S.estado) return;
  const e = S.estado, v = e.vision, visOk = e.vision_conectada, c0 = v[0], bdOk = e.base_de_datos.estado === "ok";
  const nodos = [
    ["camara", "Cámaras", e.camaras.en_linea > 0, `${e.camaras.en_linea} de ${e.camaras.total} en línea`, c0 ? `${c0.resolucion} · ${num(c0.fps_video, 1)} fps` : "Sin video"],
    ["sistema", "Visión · YOLO", visOk, c0 ? c0.modelo : "Servidor sin conexión", c0 ? `${c0.dispositivo.startsWith("cuda") ? "GPU" : c0.dispositivo} · ${c0.latencia_ms.toFixed(0)} ms` : "No reporta"],
    ["nube", "API", true, "FastAPI v" + e.version, `${num(e.eventos_ultimo_minuto)} eventos/min`],
    ["base", "Base de datos", bdOk, e.base_de_datos.motor, `${num(e.espacios.total)} cajones`],
    ["pantalla", "Panel y app móvil", true, `${num(e.espacios.monitoreados)} cajones con datos reales`, "Actualización cada 2 s"],
  ];
  SI.flujo.replaceChildren(...nodos.flatMap(([ico, nombre, ok, dato, dato2], i) => [
    h("div", { class: "nodo" + (ok ? "" : " mal") }, h("div", { class: "insignia " + (ok ? "ok" : "critico") }, icono(ico, 20)),
      h("b", { text: nombre }), h("span", { text: dato }), h("span", { text: dato2 }), etq(ok ? "Funcionando" : "Sin conexión", ok ? "ok" : "critico")),
    i < nodos.length - 1 ? h("div", { class: "nodo-enlace" + (ok && nodos[i + 1][2] ? " activo" : "") }, icono("flecha", 18)) : null,
  ]));

  if (!v.length) {
    SI.tarjetas = new Map();
    SI.modelos.replaceChildren(h("section", { class: "tarjeta" }, vacio("camara_off", "El servidor de visión no está reportando", "Inícialo con: python scripts/iniciar_sistema.py")));
    return;
  }
  if (SI.modelos.querySelector(".vacio")) SI.modelos.replaceChildren();
  for (const x of v) {
    let t = SI.tarjetas.get(x.camara);
    if (!t) {
      t = { cab: h("div", { class: "tarjeta-cab" }), dl: h("dl", { class: "detalle" }), chispa: h("div", { class: "kpi-chispa lat" }) };
      t.el = h("section", { class: "tarjeta" }, t.cab, t.dl, h("div", { class: "detalle-sub", text: "Latencia reciente" }), t.chispa);
      SI.tarjetas.set(x.camara, t); SI.modelos.append(t.el);
    }
    const vivo = x.hace_s <= 15;
    t.cab.replaceChildren(h("div", null, h("h2", { text: x.camara }), h("p", { text: x.modelo })), etq(vivo ? "Reportando" : "Sin reporte", vivo ? "ok" : "critico"));
    const filas = [["Dispositivo", x.dispositivo.startsWith("cuda") ? `GPU (${x.dispositivo})` : x.dispositivo], ["Tamaño de entrada", x.imgsz + " px"], ["Confianza mínima", Math.round(x.umbral_confianza * 100) + " %"],
      ["Latencia por detección", x.latencia_ms.toFixed(0) + " ms"], ["Detecciones por segundo", num(x.fps_deteccion, 1)], ["Video", `${x.resolucion} · ${num(x.fps_video, 1)} fps`], ["Cajones vigilados", num(x.espacios)]];
    if (x.luz) filas.push(["Iluminación", LUZ[x.luz] || x.luz]);
    if (x.espera_gpu_ms != null) filas.push(["Espera por la GPU", num(x.espera_gpu_ms) + " ms"]);
    if (x.errores != null) filas.push(["Errores de lectura", num(x.errores)]);
    filas.push(["Último reporte", "hace " + dur(x.hace_s)]);
    t.dl.replaceChildren(...filas.flatMap(([k, val]) => [h("dt", { text: k }), h("dd", { text: String(val) })]));
    t.chispa.replaceChildren(chispa(S.latCam[x.camara] || []));
  }
  for (const [cam, t] of SI.tarjetas) if (!v.some((x) => x.camara === cam)) { t.el.remove(); SI.tarjetas.delete(cam); }
}
