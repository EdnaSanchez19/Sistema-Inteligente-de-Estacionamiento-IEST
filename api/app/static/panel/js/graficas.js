"use strict";
/* Gráficas en SVG, sin bibliotecas. Una sola serie por gráfica (azul), un solo eje, rejilla tenue,
   y siempre con capa de consulta: cruz + globo en las líneas, globo por marca en barras y celdas. */

/** Anillo de porcentaje. Devuelve { el, poner(porcentaje, tono) }; el color indica gravedad y va acompañado de texto. */
function anillo(tam, grosor) {
  const r = (tam - grosor) / 2, largo = 2 * Math.PI * r;
  const valor = s("circle", { class: "anillo-valor", cx: tam / 2, cy: tam / 2, r, "stroke-width": grosor, "stroke-dasharray": largo, "stroke-dashoffset": largo });
  const el = s("svg", { width: tam, height: tam, viewBox: `0 0 ${tam} ${tam}`, style: "transform:rotate(-90deg);flex:none", "aria-hidden": "true" },
    s("circle", { class: "anillo-pista", cx: tam / 2, cy: tam / 2, r, "stroke-width": grosor }), valor);
  return { el, poner(porcentaje, tono) {
    valor.setAttribute("stroke-dashoffset", largo * (1 - Math.max(0, Math.min(100, porcentaje)) / 100));
    valor.style.stroke = `var(--${tono || "serie"})`;
  } };
}

/** Línea diminuta de tendencia para un indicador (sin ejes: el número grande ya da el valor). */
function chispa(valores) {
  const svg = s("svg", { viewBox: "0 0 100 30", preserveAspectRatio: "none", "aria-hidden": "true" });
  const v = (valores || []).filter((x) => x != null);
  if (v.length < 2) return svg;
  const min = Math.min(...v), max = Math.max(...v), rango = max - min || 1;
  const pts = v.map((y, i) => [(i / (v.length - 1)) * 100, 26 - ((y - min) / rango) * 22]);
  const linea = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(2) + " " + p[1].toFixed(2)).join("");
  svg.append(s("path", { d: `${linea}L100 30L0 30Z`, class: "g-area" }),
    s("path", { d: linea, class: "g-linea", style: "stroke-width:1.5", "vector-effect": "non-scaling-stroke" }));
  return svg;
}

function marcasY(max) {
  if (max <= 100 && max > 50) return [0, 25, 50, 75, 100];
  const paso = [1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000].find((p) => max / p <= 4) || 1000;
  const m = []; for (let y = 0; y <= Math.ceil(max / paso) * paso; y += paso) m.push(y);
  return m;
}

/** Gráfica de área de una serie.
 *  puntos: [{ y, eje (rótulo del eje X o null), titulo, filas: [[etiqueta, valor]] }]   opciones: { alto, max, sufijo } */
function graficaSerie(cont, puntos, opciones) {
  const o = { alto: 220, sufijo: "%", ...(opciones || {}) };
  const ancho = cont.clientWidth;
  cont.classList.add("grafica");
  if (!ancho) return;
  if (!puntos || puntos.length < 2) { cont.replaceChildren(vacio("reportes", "Todavía no hay datos", "La gráfica se llena conforme el sistema toma muestras.")); return; }
  const mg = { i: 38, d: 14, a: 12, b: 24 }, w = ancho - mg.i - mg.d, hh = o.alto - mg.a - mg.b;
  const marcas = marcasY(o.max || Math.max(1, ...puntos.map((p) => p.y))), tope = marcas[marcas.length - 1];
  const X = (i) => mg.i + (i / (puntos.length - 1)) * w, Y = (y) => mg.a + hh - (y / tope) * hh;
  const svg = s("svg", { width: ancho, height: o.alto, viewBox: `0 0 ${ancho} ${o.alto}`, role: "img", "aria-label": o.titulo || "Gráfica" });

  for (const m of marcas) {
    svg.append(s("line", { class: m ? "g-rejilla" : "g-base", x1: mg.i, x2: ancho - mg.d, y1: Y(m), y2: Y(m) }),
      s("text", { class: "g-eje", x: mg.i - 8, y: Y(m) + 4, "text-anchor": "end", text: m + o.sufijo }));
  }
  // Rótulos del eje X: los que caben sin tocarse
  const conEje = puntos.map((p, i) => (p.eje ? i : -1)).filter((i) => i >= 0), cada = Math.max(1, Math.ceil(conEje.length / Math.max(2, Math.floor(w / 120))));
  conEje.forEach((i, k) => { if (k % cada === 0) svg.append(s("text", { class: "g-eje", x: X(i), y: o.alto - 6, "text-anchor": i === 0 ? "start" : i === puntos.length - 1 ? "end" : "middle", text: puntos[i].eje })); });

  const linea = puntos.map((p, i) => (i ? "L" : "M") + X(i).toFixed(1) + " " + Y(p.y).toFixed(1)).join("");
  const fin = puntos.length - 1;
  svg.append(s("path", { class: "g-area", d: `${linea}L${X(fin)} ${Y(0)}L${X(0)} ${Y(0)}Z` }), s("path", { class: "g-linea", d: linea }),
    s("circle", { class: "g-punto", cx: X(fin), cy: Y(puntos[fin].y), r: 4 }));

  // Capa de consulta: la cruz sigue al cursor y el globo da los valores del punto más cercano
  const cruz = s("line", { class: "g-cruz", y1: mg.a, y2: Y(0), visibility: "hidden" }), punto = s("circle", { class: "g-punto", r: 4.5, visibility: "hidden" });
  const mover = (e) => {
    const caja = svg.getBoundingClientRect(), i = Math.max(0, Math.min(fin, Math.round(((e.clientX - caja.left - mg.i) / w) * fin))), p = puntos[i];
    cruz.setAttribute("x1", X(i)); cruz.setAttribute("x2", X(i)); cruz.setAttribute("visibility", "visible");
    punto.setAttribute("cx", X(i)); punto.setAttribute("cy", Y(p.y)); punto.setAttribute("visibility", "visible");
    mostrarTip(p.titulo, p.filas, e.clientX, e.clientY);
  };
  const salir = () => { cruz.setAttribute("visibility", "hidden"); punto.setAttribute("visibility", "hidden"); ocultarTip(); };
  svg.append(cruz, punto, s("rect", { x: mg.i, y: mg.a, width: w, height: hh, fill: "transparent", onMousemove: mover, onMouseleave: salir, onTouchstart: (e) => mover(e.touches[0]), onTouchmove: (e) => mover(e.touches[0]), onTouchend: salir }));
  cont.replaceChildren(svg);
}

/** Barras verticales (p. ej. las 24 horas del día). datos: [{ y | null, eje, titulo, filas }]. Resalta y rotula solo la más alta. */
function graficaBarras(cont, datos, opciones) {
  const o = { alto: 210, sufijo: "%", ...(opciones || {}) };
  const ancho = cont.clientWidth;
  cont.classList.add("grafica");
  if (!ancho) return;
  const conDato = datos.filter((d) => d.y != null);
  if (!conDato.length) { cont.replaceChildren(vacio("reportes", "Todavía no hay datos", "Aparecerán cuando haya muestras en el periodo.")); return; }
  const mg = { i: 38, d: 8, a: 22, b: 24 }, w = ancho - mg.i - mg.d, hh = o.alto - mg.a - mg.b;
  const marcas = marcasY(o.max || Math.max(1, ...conDato.map((d) => d.y))), tope = marcas[marcas.length - 1];
  const banda = w / datos.length, grosor = Math.max(3, Math.min(24, banda - 2)), Y = (y) => mg.a + hh - (y / tope) * hh;
  const mayor = conDato.reduce((a, b) => (b.y > a.y ? b : a));
  const svg = s("svg", { width: ancho, height: o.alto, viewBox: `0 0 ${ancho} ${o.alto}`, role: "img", "aria-label": o.titulo || "Gráfica de barras" });
  for (const m of marcas) {
    svg.append(s("line", { class: m ? "g-rejilla" : "g-base", x1: mg.i, x2: ancho - mg.d, y1: Y(m), y2: Y(m) }),
      s("text", { class: "g-eje", x: mg.i - 8, y: Y(m) + 4, "text-anchor": "end", text: m + o.sufijo }));
  }
  const cadaEje = banda < 26 ? 3 : banda < 40 ? 2 : 1;
  datos.forEach((d, i) => {
    const cx = mg.i + banda * (i + 0.5);
    if (d.eje != null && i % cadaEje === 0) svg.append(s("text", { class: "g-eje", x: cx, y: o.alto - 6, "text-anchor": "middle", text: d.eje }));
    if (d.y == null) return;
    const y = Y(d.y), alto = Math.max(1, Y(0) - y), r = Math.min(4, grosor / 2, alto), x = cx - grosor / 2;
    const barra = s("path", { class: "g-barra" + (d === mayor ? " max" : ""), d: `M${x} ${Y(0)}V${y + r}Q${x} ${y} ${x + r} ${y}H${x + grosor - r}Q${x + grosor} ${y} ${x + grosor} ${y + r}V${Y(0)}Z` });
    svg.append(barra);
    if (d === mayor) svg.append(s("text", { class: "g-rotulo", x: Math.max(mg.i + 14, Math.min(ancho - mg.d - 14, cx)), y: y - 6, "text-anchor": "middle", text: num(d.y) + o.sufijo }));
    // Zona de consulta más grande que la barra: toda la franja
    svg.append(s("rect", { x: mg.i + banda * i, y: mg.a, width: banda, height: hh, fill: "transparent",
      onMousemove: (e) => { barra.classList.add("sobre"); mostrarTip(d.titulo, d.filas, e.clientX, e.clientY); },
      onMouseleave: () => { barra.classList.remove("sobre"); ocultarTip(); } }));
  });
  cont.replaceChildren(svg);
}

/** Mapa de calor de la semana: 7 días × 24 horas, un solo tono de claro (poco) a oscuro (mucho).
 *  celdas: [{ dia (0 = lunes), hora, ocupacion_media_pct, muestras }] */
function calorSemana(cont, celdas) {
  const mapa = new Map((celdas || []).map((c) => [c.dia * 24 + c.hora, c]));
  if (!mapa.size) { cont.replaceChildren(vacio("reportes", "Todavía no hay datos", "Hace falta al menos un día de muestras.")); return; }
  const paso = (p) => (p == null ? 0 : 1 + Math.min(6, Math.floor((p / 100) * 7)));
  const rejilla = h("div", { class: "calor", role: "img", "aria-label": "Ocupación media por día de la semana y hora" });
  for (let d = 0; d < 7; d++) {
    rejilla.append(h("span", { text: DIAS[d] }));
    for (let hr = 0; hr < 24; hr++) {
      const c = mapa.get(d * 24 + hr);
      rejilla.append(h("i", { class: "calor-celda", style: `background:var(--calor-${paso(c ? c.ocupacion_media_pct : null)})`, "data-k": d * 24 + hr }));
    }
  }
  rejilla.append(h("span"));
  for (let hr = 0; hr < 24; hr++) rejilla.append(h("span", { class: "calor-hora", text: hr % 3 === 0 ? String(hr).padStart(2, "0") : "" }));
  rejilla.addEventListener("mousemove", (e) => {
    const k = e.target.dataset && e.target.dataset.k; if (k == null) return ocultarTip();
    const c = mapa.get(Number(k)), d = Math.floor(k / 24), hr = k % 24, titulo = `${DIAS[d]} · ${String(hr).padStart(2, "0")}:00 a ${String(hr + 1).padStart(2, "0")}:00`;
    mostrarTip(titulo, c ? [["Ocupación media", num(c.ocupacion_media_pct, 1) + " %"], ["Muestras", num(c.muestras)]] : ["Sin muestras"], e.clientX, e.clientY);
  });
  rejilla.addEventListener("mouseleave", ocultarTip);
  const leyenda = h("div", { class: "calor-ley" }, h("span", { text: "0 %" }), ...[1, 2, 3, 4, 5, 6, 7].map((n) => h("i", { style: `background:var(--calor-${n})` })), h("span", { text: "100 %" }),
    h("i", { style: "background:var(--calor-0);margin-left:14px" }), h("span", { text: "Sin muestras" }));
  cont.replaceChildren(rejilla, leyenda);
}
