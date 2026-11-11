"use strict";
/* Croquis 2D del estacionamiento: cada fila de cajones en el lugar que ocupa en el terreno.
   TODO el acomodo está en la tabla CROQUIS.bloques: para corregir una fila (moverla, invertir su numeración)
   basta cambiar su renglón, sin tocar el resto del código.

   Unidades: el croquis mide CROQUIS.ancho × CROQUIS.alto y se escala solo al ancho de la pantalla.
   x, y, w, h  → posición y tamaño del bloque.
   col         → cuántos cajones caben por renglón (los cajones se llenan de izquierda a derecha y de arriba abajo).
   inv         → true para numerar al revés (el 01 queda en el extremo contrario).
   Posiciones tomadas de la foto satelital: PENDIENTES DE CONFIRMAR en sitio (orden de las filas y sentido de la numeración). */
const CROQUIS = {
  ancho: 1000, alto: 870,
  bloques: [
    // Perímetro superior: caseta y entrada
    { zona: "Lateral caseta", x: 124, y: 30, w: 560, h: 34, col: 16 },
    { zona: "Entrada lateral", x: 704, y: 30, w: 152, h: 34, col: 4 },
    // Costados: biblioteca (junto a los edificios) y callejón (junto a la calle)
    { zona: "Lateral biblioteca", x: 14, y: 96, w: 92, h: 676, col: 2, angosto: true },
    { zona: "Lateral callejón", x: 884, y: 96, w: 100, h: 676, col: 2, angosto: true },
    // Islas: la fila 1 (A) arriba y la 8 (H) abajo; cada isla son dos renglones de cajones espalda con espalda
    ...[..."ABCDEFGH"].map((zona, i) => ({ zona, x: 124, y: 96 + i * 88, w: 732, h: 62, col: zona === "H" ? 14 : zona === "B" || "CDEF".includes(zona) ? 18 : 16 })),
    // Perímetro inferior: gimnasio y esquina de motos
    { zona: "Lateral gimnasio", x: 124, y: 804, w: 560, h: 34, col: 18 },
    { zona: "Esquina motos", x: 704, y: 792, w: 152, h: 60, col: 4 },
  ],
};

const CQ = { firma: "", bloques: new Map() };

/** Arma el croquis (una vez) y devuelve su contenedor. */
function armarCroquis(zonas) {
  CQ.bloques = new Map();
  const escenario = h("div", { class: "cq-escenario", style: `width:${CROQUIS.ancho}px;height:${CROQUIS.alto}px` });
  for (const d of CROQUIS.bloques) {
    if (!zonas.some((z) => z.nombre === d.zona)) continue;
    const det = h("span"), cajones = h("div", { class: "cq-cajones", style: `grid-template-columns:repeat(${d.col},minmax(0,1fr))${d.inv ? ";direction:rtl" : ""}` });
    escenario.append(h("div", { class: "cq-bloque" + (d.angosto ? " angosto" : ""), style: `left:${d.x}px;top:${d.y}px;width:${d.w}px;height:${d.h}px` },
      h("div", { class: "cq-et" }, h("b", { text: rotulo(d.zona) }), det), cajones));
    CQ.bloques.set(d.zona, { det, cajones });
  }
  CQ.escenario = escenario;
  CQ.caja = h("div", { class: "cq-caja" }, escenario);
  return CQ.caja;
}

/** Ajusta la escala al ancho disponible (si la vista está oculta no hace nada). */
function escalarCroquis() {
  if (!CQ.caja || !CQ.caja.clientWidth) return;
  const k = Math.min(1.5, CQ.caja.clientWidth / CROQUIS.ancho);
  CQ.escenario.style.transform = `scale(${k})`;
  CQ.caja.style.height = Math.round(CROQUIS.alto * k) + "px";
}

function pintarCroquis(zonas) {
  for (const z of zonas) {
    const b = CQ.bloques.get(z.nombre); if (!b) continue;
    b.det.textContent = z.monit ? `${z.libres} libres` : "sin cámara";
    pintarCajones(b.cajones, z.lista, { filtrar: true, tiempo: S.mapa.rotulo === "tiempo" });
  }
  escalarCroquis();
}
