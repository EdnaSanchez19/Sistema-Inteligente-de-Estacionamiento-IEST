"use strict";
/* Vista Mapa de cajones: el plano esquemático o la lista por fila, con filtros por estado, búsqueda
   y la opción de ver el tiempo transcurrido dentro de cada cajón. */

const ZONA_DEL_PLANO = { "Lateral caseta": "caseta", "Entrada lateral": "entrada", "Lateral biblioteca": "biblioteca", "Lateral gimnasio": "gimnasio", "Lateral callejón": "callejon", "Esquina motos": "motos" };
const FILTROS_MAPA = [["todos", "Todos", null], ["libre", "Libres", "m-libre"], ["ocupado", "Ocupados", "m-ocupado"], ["obstruido", "Obstruidos", "m-obstruido"], ["largo", "Estancia larga (+4 h)", null], ["sin", "Sin cámara", "m-sin"]];
const M = { firma: "", bloques: new Map() };

function vistaMapa() {
  M.firma = ""; M.bloques = new Map();
  M.segModo = segmentado([["croquis", "Croquis"], ["plano", "Esquema"], ["filas", "Por fila"]], S.mapa.modo, (v) => { S.mapa.modo = v; pintarMapa(); });
  M.chips = h("div", { class: "chips" }, FILTROS_MAPA.map(([valor, texto, marca]) =>
    h("button", { type: "button", class: "chip", "data-f": valor, onClick: () => { S.mapa.filtro = valor; pintarMapa(); } }, marca ? h("i", { class: marca }) : null, texto + " ", h("b"))));
  M.selFila = h("div", { class: "chips", style: "margin-bottom:14px" });
  return h("section", { class: "vista", id: "v-mapa" },
    h("div", { class: "tarjeta mapa-barra" },
      h("div", { class: "mapa-controles" },
        M.segModo,
        segmentado([["numero", "Número"], ["tiempo", "Tiempo"]], S.mapa.rotulo, (v) => { S.mapa.rotulo = v; pintarMapa(); }),
        h("label", { class: "buscar", style: "margin-left:auto" }, icono("buscar", 15),
          h("input", { class: "entrada", type: "search", placeholder: "Buscar cajón, p. ej. C-12", "aria-label": "Buscar cajón", value: S.mapa.buscar, onInput: (e) => { S.mapa.buscar = e.target.value; pintarMapa(); } }))),
      M.chips),
    M.selFila,
    M.cuerpo = h("div"),
    h("div", { class: "mapa-pie" }, leyendaCajones(), M.nota = h("p", { class: "nota" })));
}

function bloqueZona(z, clase) {
  const b = { det: h("span"), medidor: h("i"), cajones: h("div", { class: "cajones" }) };
  b.el = h("div", { class: "tarjeta zona " + (clase || "") },
    h("div", { class: "zona-cab" }, h("h3", { text: rotulo(z.nombre) }), b.det),
    h("div", { class: "medidor", style: "margin-bottom:12px" }, b.medidor), b.cajones);
  return b;
}

function pintarMapa() {
  if (!M.cuerpo) return;
  const zonas = agruparIslas(), modo = S.mapa.modo;
  for (const b of M.segModo.children) b.classList.toggle("activo", b.dataset.v === modo);

  // Contadores de cada filtro
  const cuenta = { todos: S.espacios.length, libre: 0, ocupado: 0, obstruido: 0, largo: 0, sin: 0 };
  for (const e of S.espacios) { if (!e.monitoreado) cuenta.sin++; else if (cuenta[e.estado] != null) cuenta[e.estado]++; if (estanciaLarga(e)) cuenta.largo++; }
  for (const c of M.chips.children) { c.classList.toggle("activo", c.dataset.f === S.mapa.filtro); c.lastChild.textContent = num(cuenta[c.dataset.f]); }

  // La estructura solo se vuelve a armar si cambia el modo o la lista de zonas; después se actualiza en su sitio
  const firma = modo + "|" + zonas.map((z) => z.nombre).join();
  if (firma !== M.firma) {
    M.firma = firma; M.bloques = new Map();
    const nuevo = (z, clase) => { const b = bloqueZona(z, clase); M.bloques.set(z.nombre, b); return b.el; };
    if (modo === "croquis") {
      M.cuerpo.replaceChildren(armarCroquis(zonas));
    } else if (modo === "plano") {
      const islas = zonas.filter((z) => z.nombre.length === 1), perimetro = zonas.filter((z) => z.nombre.length > 1);
      M.cuerpo.replaceChildren(h("div", { class: "plano" }, ...perimetro.map((z) => nuevo(z, "z-" + (ZONA_DEL_PLANO[z.nombre] || "otra"))), h("div", { class: "z-islas" }, islas.map((z) => nuevo(z)))));
    } else {
      M.cuerpo.replaceChildren(h("div", { class: "filas-mapa" }, zonas.map((z) => nuevo(z))));
    }
    M.selFila.replaceChildren(...[["todas", "Todas las filas"], ...zonas.map((z) => [z.nombre, rotulo(z.nombre)])].map(([valor, texto]) =>
      h("button", { type: "button", class: "chip", "data-f": valor, text: texto, onClick: () => { S.isla = valor; pintarMapa(); } })));
  }
  M.selFila.hidden = modo !== "filas";
  for (const c of M.selFila.children) c.classList.toggle("activo", c.dataset.f === S.isla);

  if (modo === "croquis") pintarCroquis(zonas);
  for (const z of modo === "croquis" ? [] : zonas) {
    const b = M.bloques.get(z.nombre); if (!b) continue;
    b.el.hidden = modo === "filas" && S.isla !== "todas" && S.isla !== z.nombre;
    const o = pct(z.ocupados + z.obstruidos, z.monit);
    b.det.textContent = z.monit ? `${z.libres} libres · ${z.ocupados} ocupados` + (z.obstruidos ? ` · ${z.obstruidos} obstruidos` : "") + (z.monit < z.total ? ` · ${z.monit} de ${z.total} con cámara` : "") : `Sin cámara · ${z.total} cajones`;
    b.medidor.parentNode.className = "medidor " + (z.monit ? gravedad(o) : "");
    b.medidor.style.width = (z.monit ? o : 0) + "%";
    pintarCajones(b.cajones, z.lista, { filtrar: true, tiempo: S.mapa.rotulo === "tiempo" });
  }
  const total = S.espacios.length, vigilados = S.espacios.filter((e) => e.monitoreado).length;
  M.nota.textContent = (modo === "croquis" ? "Croquis aproximado de la distribución real; el orden de los cajones dentro de cada fila está por confirmar en sitio. " : modo === "plano" ? "Esquema: la posición de cada bloque es aproximada y no está a escala. " : "") + `${total} cajones, ${vigilados} con cámara. El punto amarillo marca una estancia de más de 4 h. Toca un cajón para ver su detalle.`;
}
