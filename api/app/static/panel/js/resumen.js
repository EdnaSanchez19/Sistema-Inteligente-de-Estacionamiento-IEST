"use strict";
/* Vista Resumen: la disponibilidad de un vistazo, cámara en vivo, tendencia de la última hora y lo que pide atención. */

const R = {};  // referencias a los nodos que se actualizan en cada ciclo

function vistaResumen() {
  R.anillo = anillo(148, 13);
  const indicador = (clave, texto, ico, alClic) => {
    const t = h(alClic ? "button" : "div", { class: "tarjeta kpi", type: alClic ? "button" : null, onClick: alClic },
      h("div", { class: "kpi-etq" }, icono(ico, 16), texto), R[clave + "Valor"] = h("div", { class: "kpi-valor" }), R[clave + "Nota"] = h("div", { class: "kpi-nota" }), R[clave + "Extra"] = h("div", { class: "kpi-chispa" }));
    return t;
  };
  return h("section", { class: "vista", id: "v-resumen" },
    h("div", { class: "res-arriba" },
      h("section", { class: "tarjeta hero" },
        h("div", { class: "hero-anillo" }, R.anillo.el, h("div", { class: "hero-centro" }, R.pct = h("b"), h("span", { text: "ocupado" }))),
        h("div", { class: "hero-datos" },
          h("div", { class: "hero-etq" }, "Cajones libres ahora ", R.etq = h("span", { class: "etq" })),
          R.libres = h("div", { class: "hero-num" }),
          R.nota = h("p", { class: "hero-nota" }),
          R.seg = h("div", { class: "barra-seg", style: "margin-top:16px" }),
          R.ley = h("div", { class: "leyenda", style: "margin-top:10px" }))),
      h("div", { class: "kpis" },
        indicador("ocu", "Ocupados", "coche"),
        indicador("veh", "Vehículos detectados", "pulso"),
        indicador("cam", "Cámaras en línea", "camara", () => ir("camaras")),
        esAdmin() ? indicador("ale", "Alertas activas", "alerta", () => ir("alertas")) : indicador("obs", "Obstruidos", "obstaculo"))),

    h("div", { class: "res-medio" },
      h("div", { class: "columna" },
        tarjeta("Cámara en vivo", "Detección de vehículos con YOLO", R.pestanas = h("div"),
          h("div", { class: "video" },
            h("img", { class: "video", id: "video-resumen", alt: "Video de la cámara con las detecciones del modelo" }),
            h("div", { class: "fuera", id: "fuera-resumen", hidden: true }),
            h("button", { class: "video-ampliar", type: "button", title: "Ampliar", "aria-label": "Ampliar video", onClick: () => { const c = camaraActiva(); if (c) abrirVideo(c); } }, icono("ampliar", 16))),
          R.datosVideo = h("div", { class: "datos-video" })),
        tarjeta("Seguimiento de vehículos", "En vivo, por cámara", null, R.seguimiento = h("div"))),
      h("div", { class: "columna" },
        tarjeta("Ocupación · última hora", "Porcentaje de cajones con cámara que están ocupados", null, R.grafica = h("div")),
        tarjeta("Disponibilidad por fila", "Toca una fila para verla en el mapa", null, R.filas = h("div", { class: "filas-disp" })))),

    h("div", { class: "res-abajo" },
      tarjeta("Estancias más largas", "Vehículos que llevan más tiempo sin moverse", null, R.estancias = h("div", { class: "lista" })),
      tarjeta("Actividad reciente", null, esAdmin() ? h("button", { class: "enlace", type: "button", text: "Ver todos", onClick: () => ir("eventos") }) : null, R.eventos = h("div", { class: "lista" })),
      esAdmin()
        ? tarjeta("Alertas activas", null, h("button", { class: "enlace", type: "button", text: "Ver alertas", onClick: () => ir("alertas") }), R.alertas = h("div", { class: "lista" }))
        : tarjeta("Avisos", null, null, R.avisos = h("div", { class: "lista" }))));
}

function pintarResumen() {
  if (!S.estado || !R.libres) return;
  const e = S.estado.espacios, v = S.estado.vision, monit = e.monitoreados;
  const ocupacion = pct(e.ocupado + e.obstruido, monit), tono = gravedad(ocupacion);

  // Disponibilidad
  R.anillo.poner(monit ? ocupacion : 0, tono);
  R.pct.textContent = monit ? ocupacion + "%" : "—";
  R.libres.textContent = monit ? num(e.libre) : "—";
  R.etq.className = "etq " + (monit ? tono : ""); R.etq.textContent = monit ? TEXTO_GRAVEDAD[tono] : "Sin datos";
  R.nota.textContent = monit ? `de ${num(monit)} cajones con cámara · ${num(e.total)} en todo el estacionamiento` : "Ninguna cámara está reportando todavía.";
  const partes = [["Libres", e.libre, "m-libre"], ["Ocupados", e.ocupado, "m-ocupado"], ["Obstruidos", e.obstruido, "m-obstruido"], ["Reservados", e.reservado, "m-reservado"]].filter((p) => p[1] > 0 || p[0] === "Libres" || p[0] === "Ocupados");
  R.seg.replaceChildren(...partes.filter((p) => p[1] > 0).map((p) => h("i", { class: p[2], style: `flex:${p[1]} 0 0`, title: `${p[0]}: ${p[1]}` })));
  R.ley.replaceChildren(...partes.map((p) => h("span", null, h("i", { class: p[2] }), p[0] + " ", h("b", { text: num(p[1]) }))));

  // Indicadores
  const vehiculos = v.reduce((a, x) => a + x.vehiculos, 0);
  R.ocuValor.textContent = num(e.ocupado); R.ocuNota.textContent = monit ? `${pct(e.ocupado, monit)} % de los cajones con cámara` : "Sin datos todavía";
  R.ocuExtra.replaceChildren(chispa(S.serie.map((p) => p.ocupados)));
  S.histVeh = [...(S.histVeh || []), vehiculos].slice(-60);
  R.vehValor.textContent = num(vehiculos); R.vehNota.textContent = v.length ? `En ${v.length} cámara${v.length > 1 ? "s" : ""}, incluye los que circulan` : "Sin servidor de visión";
  R.vehExtra.replaceChildren(chispa(S.histVeh));
  const cam = S.estado.camaras;
  R.camValor.replaceChildren(num(cam.en_linea), h("small", { text: `de ${cam.total}` }));
  R.camNota.textContent = `${num(S.estado.eventos_ultimo_minuto)} eventos en el último minuto`;
  R.camExtra.replaceChildren(h("div", { class: "medidor " + (cam.en_linea === cam.total ? "" : cam.en_linea ? "aviso" : "critico"), style: "margin-top:12px" }, h("i", { style: `width:${Math.max(4, pct(cam.en_linea, cam.total))}%` })));
  if (R.aleValor) {
    const activas = S.alertas || [], pendientes = activas.filter((a) => !a.atendida).length;
    R.aleValor.textContent = num(activas.length);
    R.aleNota.textContent = !activas.length ? "Nada pide atención" : pendientes ? `${pendientes} sin atender` : "Todas atendidas";
    R.aleExtra.replaceChildren(h("div", { class: "medidor " + (pendientes ? "critico" : ""), style: "margin-top:12px" }, h("i", { style: `width:${activas.length ? Math.max(6, pct(activas.length - pendientes, activas.length)) : 100}%` })));
  }
  if (R.obsValor) { R.obsValor.textContent = num(e.obstruido); R.obsNota.textContent = e.obstruido ? "Un objeto ocupa el cajón sin ser un vehículo" : "Ningún objeto en cajones vacíos"; }

  pintarVideoResumen(v);
  pintarSeguimiento();

  // Disponibilidad por fila
  R.filas.replaceChildren(...agruparIslas().map((i) => {
    const o = pct(i.ocupados + i.obstruidos, i.monit), t = gravedad(o);
    return h("button", { type: "button", class: "fila-disp", onClick: () => { S.isla = i.nombre; S.mapa.modo = "filas"; ir("mapa"); } },
      h("span", { class: "fila-disp-nom", text: rotulo(i.nombre) }),
      i.monit ? h("span", { class: "fila-disp-val" }, h("b", { text: num(i.libres) }), " libres") : h("span", { class: "fila-disp-val tenue", text: "Sin cámara" }),
      h("div", { class: "medidor " + (i.monit ? t : "") }, h("i", { style: `width:${i.monit ? o : 0}%` })));
  }));

  // Listas
  R.estancias.replaceChildren(...(S.estancias.length
    ? S.estancias.slice(0, 6).map((x) => h("div", { class: "fila" },
      h("div", { class: "insignia " + (x.duracion_s >= ESTANCIA_LARGA_S ? "aviso" : "") }, icono("reloj", 16)),
      h("div", { class: "fila-txt" }, h("b", null, refCajon(x.numero)), h("span", { text: rotulo(x.zona) })),
      h("div", { class: "fila-der", text: (x.desde_observado ? "" : "≥ ") + dur(x.duracion_s) })))
    : [vacio("coche", "Aún no hay vehículos observados")]));

  const ev = S.eventos;
  R.eventos.replaceChildren(...(ev === null ? [vacio("eventos", "Solo para administradores", "El detalle de eventos requiere una cuenta de administrador.")]
    : !ev.length ? [vacio("eventos", "Sin actividad todavía", "Se registra cuando un vehículo entra o sale de un cajón con cámara.")]
    : ev.slice(0, 6).map((x) => filaEvento(x))));

  if (R.alertas) {
    const activas = S.alertas || [];
    R.alertas.replaceChildren(...(activas.length ? activas.slice(0, 5).map((a) => filaAlerta(a)) : [vacio("check", "Todo en orden", "No hay alertas activas.")]));
  }
  if (R.avisos) {
    R.avisos.replaceChildren(...(S.avisos.length ? S.avisos.slice(0, 5).map((a) => h("div", { class: "fila" },
      h("div", { class: "insignia info" }, icono("alerta", 16)), h("div", { class: "fila-txt" }, h("b", { text: a.titulo }), h("span", { text: a.mensaje })), h("div", { class: "fila-der", text: hace(a.fecha) })))
      : [vacio("check", "No hay avisos", "Se generan cuando una fila con cobertura completa se llena.")]));
  }
}

function pintarVideoResumen(v) {
  const lista = v.map((x) => x.camara), actual = camaraActiva();
  if (R.pestanas.dataset.lista !== lista.join()) {
    R.pestanas.dataset.lista = lista.join();
    R.pestanas.replaceChildren(lista.length > 1 ? segmentado(lista.map((c) => [c, c]), actual, (c) => { S.camSel = c; gestionarVideos(); pintarResumen(); }) : null);
  }
  gestionarVideos();
  if (!lista.length) {
    $("fuera-resumen").hidden = false;
    $("fuera-resumen").replaceChildren(icono("camara_off", 30), h("b", { text: "Ninguna cámara está reportando" }), h("span", { text: "Cuando el servidor de visión arranque, aquí se verá el video con las detecciones." }));
  }
  const cam = v.find((x) => x.camara === actual);
  R.datosVideo.replaceChildren(...(cam ? [["Vehículos", num(cam.vehiculos)], ["Ocupados", num(cam.ocupados)], ["Libres", num(cam.libres)], ["Latencia", `${cam.latencia_ms.toFixed(0)} ms`], ["Resolución", cam.resolucion || "—"], ["Último reporte", `hace ${cam.hace_s.toFixed(0)} s`]]
    .map(([k, val]) => h("div", null, h("span", { text: k }), h("b", { text: val }))) : []));
}

function pintarSeguimiento() {
  const c = S.coches;
  if (!c || !c.camaras.length) { R.seguimiento.replaceChildren(vacio("coche", "Ninguna cámara está reportando vehículos")); return; }
  const dato = (texto, valor) => h("div", null, h("b", { text: num(valor) }), h("span", { text: texto }));
  R.seguimiento.replaceChildren(
    h("div", { class: "cifras" }, dato("Vehículos", c.total), dato("Quietos", c.quietos), dato("En movimiento", c.en_movimiento), dato("Quietos fuera de cajón", c.fuera_de_cajon)),
    h("p", { class: "nota", text: c.camaras.map((x) => `${x.nombre || x.camara}: ${x.total}`).join(" · ") + ". Un vehículo que ven dos cámaras se cuenta en las dos." }));
}

/** La gráfica solo se redibuja cuando llega una serie nueva o cambia el ancho (no cada 2 s: así no parpadea bajo el cursor). */
function pintarSerieResumen() {
  if (S.vista !== "resumen" || !R.grafica) return;
  const puntos = S.serie.filter((p) => p.monitoreados).map((p) => {
    const o = (p.ocupados + (p.obstruidos || 0)) / p.monitoreados * 100;
    return { y: o, eje: hora(p.t), titulo: new Date(p.t).toLocaleTimeString("es-MX"), filas: [["Ocupación", num(o, 1) + " %"], ["Ocupados", num(p.ocupados)], ["Libres", num(p.libres)]] };
  });
  graficaSerie(R.grafica, puntos, { alto: 200, max: 100, titulo: "Ocupación en la última hora" });
}
