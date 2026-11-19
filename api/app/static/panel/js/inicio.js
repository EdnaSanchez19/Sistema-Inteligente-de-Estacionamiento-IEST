"use strict";
/* Inicio para quien no es administrador: la disponibilidad del estacionamiento y lo que es suyo (cajón asignado, vehículos, avisos).
   No muestra cámaras, alertas ni datos del sistema: esas vistas son solo para administradores. */

const I = {};  // referencias a los nodos que se actualizan en cada ciclo
const HORAS_UTILES = [6, 22];  // rango de horas que se muestra: de 6:00 a 21:59

function vistaInicio() {
  const indicador = (clave, texto, ico, alClic) => h(alClic ? "button" : "div", { class: "tarjeta kpi", type: alClic ? "button" : null, onClick: alClic },
    h("div", { class: "kpi-etq" }, icono(ico, 16), texto), I[clave + "Valor"] = h("div", { class: "kpi-valor" }), I[clave + "Nota"] = h("div", { class: "kpi-nota" }));
  return h("section", { class: "vista", id: "v-resumen" },
    h("section", { class: "tarjeta hero" },
      h("div", { class: "hero-datos" },
        h("div", { class: "hero-etq" }, I.saludo = h("span"), I.etq = h("span", { class: "etq" })),
        I.libres = h("div", { class: "hero-num" }),
        I.nota = h("p", { class: "hero-nota" }),
        I.seg = h("div", { class: "barra-seg", style: "margin-top:16px" }),
        I.ley = h("div", { class: "leyenda", style: "margin-top:10px" }))),
    h("div", { class: "kpis" },
      indicador("mejor", "Fila con más lugar", "mapa", () => ir("mapa")),
      indicador("cajon", "Tu cajón asignado", "coche"),
      indicador("coches", "Tus vehículos", "coche"),
      indicador("hora", "Mejor hora para llegar", "reloj")),
    h("div", { class: "res-medio" },
      h("div", { class: "columna" }, tarjeta("Disponibilidad por fila", "Toca una fila para verla en el mapa", null, I.filas = h("div", { class: "filas-disp" }))),
      h("div", { class: "columna" }, tarjeta("Ocupación típica por hora", "Promedio de la última semana: elige cuándo llegar", null, I.horas = h("div")))),
    h("div", { class: "res-abajo inicio-abajo" },
      tarjeta("Tus vehículos", "Los que tienes registrados", null, I.vehiculos = h("div", { class: "lista" })),
      tarjeta("Avisos", "Para ti y para toda la comunidad", null, I.avisos = h("div", { class: "lista" }))));
}

/** La hora con menos ocupación media entre las horas útiles que tienen datos, o null si aún no hay. */
function mejorHora(horas) {
  const buenas = (horas || []).filter((x) => x.muestras > 0 && x.hora >= HORAS_UTILES[0] && x.hora < HORAS_UTILES[1] && x.ocupacion_media_pct != null);
  return buenas.length ? buenas.reduce((a, b) => (b.ocupacion_media_pct < a.ocupacion_media_pct ? b : a)) : null;
}

function pintarInicio() {
  if (!I.libres) return;
  const vigilados = S.espacios.filter((e) => e.monitoreado);
  const cuenta = (estado) => vigilados.filter((e) => e.estado === estado).length;
  const libres = cuenta("libre"), ocupados = cuenta("ocupado"), obstruidos = cuenta("obstruido"), reservados = cuenta("reservado");
  const monit = vigilados.length, ocupacion = pct(ocupados + obstruidos, monit), tono = gravedad(ocupacion);

  // Disponibilidad ahora
  const nombre = ((S.yo && S.yo.nombre) || "").trim().split(/\s+/)[0] || "";
  I.saludo.textContent = nombre ? `Hola, ${nombre} · lugares libres ahora` : "Lugares libres ahora";
  I.etq.className = "etq " + (monit ? tono : ""); I.etq.textContent = monit ? TEXTO_GRAVEDAD[tono] : "Sin datos";
  I.libres.textContent = monit ? num(libres) : "—";
  I.nota.textContent = monit ? `de ${num(monit)} cajones con cámara · ${num(S.espacios.length)} en todo el estacionamiento` : "Todavía no hay información de disponibilidad.";
  const partes = [["Libres", libres, "m-libre"], ["Ocupados", ocupados, "m-ocupado"], ["Obstruidos", obstruidos, "m-obstruido"], ["Reservados", reservados, "m-reservado"]];
  I.seg.replaceChildren(...partes.filter((p) => p[1] > 0).map((p) => h("i", { class: p[2], style: `flex:${p[1]} 0 0`, title: `${p[0]}: ${p[1]}` })));
  I.ley.replaceChildren(...partes.filter((p) => p[1] > 0 || p[0] === "Libres" || p[0] === "Ocupados").map((p) => h("span", null, h("i", { class: p[2] }), p[0] + " ", h("b", { text: num(p[1]) }))));

  // Indicadores
  const filas = agruparIslas(), mejor = filas.filter((f) => f.monit > 0).reduce((a, b) => (!a || b.libres > a.libres ? b : a), null);
  I.mejorValor.textContent = mejor ? rotulo(mejor.nombre) : "—";
  I.mejorNota.textContent = mejor ? `${num(mejor.libres)} lugares libres de ${num(mejor.monit)}` : "Sin datos todavía";

  const asignado = S.yo && S.yo.espacioAsignado, cajon = asignado ? S.porNumero.get(asignado) : null;
  I.cajonValor.textContent = asignado || "—";
  I.cajonNota.textContent = asignado ? (cajon ? `Ahora está ${cajon.monitoreado ? cajon.estado.replace("_", " ") : "sin información"}` : "Asignado a tu cuenta") : "Todavía no tienes uno asignado";

  const coches = S.misCoches || [], conColgante = coches.filter((c) => c.colgante).length;
  I.cochesValor.textContent = num(coches.length);
  I.cochesNota.textContent = coches.length ? `${conColgante} con colgante registrado` : "Ninguno registrado";

  const hora = mejorHora(S.horas);
  I.horaValor.textContent = hora ? `${hora.hora}:00` : "—";
  I.horaNota.textContent = hora ? `Suele estar ${Math.round(hora.ocupacion_media_pct)} % ocupado` : "Aún no hay datos suficientes";

  // Disponibilidad por fila
  I.filas.replaceChildren(...filas.map((f) => {
    const o = pct(f.ocupados + f.obstruidos, f.monit), t = gravedad(o);
    return h("button", { type: "button", class: "fila-disp", onClick: () => { S.isla = f.nombre; S.mapa.modo = "filas"; ir("mapa"); } },
      h("span", { class: "fila-disp-nom", text: rotulo(f.nombre) }),
      f.monit ? h("span", { class: "fila-disp-val" }, h("b", { text: num(f.libres) }), " libres") : h("span", { class: "fila-disp-val tenue", text: "Sin cámara" }),
      h("div", { class: "medidor " + (f.monit ? t : "") }, h("i", { style: `width:${f.monit ? o : 0}%` })));
  }));

  // Ocupación típica por hora (de 6:00 a 21:59)
  const horas = (S.horas || []).filter((x) => x.hora >= HORAS_UTILES[0] && x.hora < HORAS_UTILES[1]);
  const ahora = new Date().getHours();
  I.horas.replaceChildren(horas.some((x) => x.muestras > 0)
    ? h("div", { class: "horas-barras", role: "img", "aria-label": "Ocupación media por hora del día" }, horas.map((x) => {
      const o = x.ocupacion_media_pct, conDatos = x.muestras > 0 && o != null;
      return h("div", { class: "hb" + (x.hora === ahora ? " ahora" : ""), title: conDatos ? `${x.hora}:00 · ${Math.round(o)} % ocupado` : `${x.hora}:00 · sin datos` },
        h("div", { class: "hb-col " + (conDatos ? gravedad(o) : "vacia"), style: `height:${conDatos ? Math.max(4, o) : 4}%` }), h("span", { text: x.hora }));
    }))
    : vacio("reloj", "Aún no hay datos suficientes", "Se llena con la ocupación que se va registrando durante la semana."));

  // Mis vehículos
  I.vehiculos.replaceChildren(...(coches.length ? coches.map((c) => h("div", { class: "fila" },
    h("div", { class: "insignia" }, icono("coche", 16)),
    h("div", { class: "fila-txt" }, h("b", { text: `${c.marca} ${c.modelo}`.trim() }), h("span", { text: [c.color, c.placa].filter(Boolean).join(" · ") })),
    h("div", { class: "fila-der", text: c.colgante ? c.colgante.codigo : "Sin colgante" })))
    : [vacio("coche", "No tienes vehículos registrados", "Pide a un administrador que registre el tuyo.")]));

  // Avisos
  const avisos = S.avisos || [];
  I.avisos.replaceChildren(...(avisos.length ? avisos.slice(0, 5).map((a) => h("div", { class: "fila" },
    h("div", { class: "insignia info" }, icono("alerta", 16)), h("div", { class: "fila-txt" }, h("b", { text: a.titulo }), h("span", { text: a.mensaje })), h("div", { class: "fila-der", text: hace(a.fecha) })))
    : [vacio("check", "No hay avisos", "Aquí aparecen los avisos para ti, por ejemplo cuando una fila se llena.")]));
}
