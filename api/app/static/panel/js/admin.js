"use strict";
/* Vista Administración: alta de usuarios, vehículos y colgantes, y sus listados. */

const ROLES = { estudiante: "Estudiante", docente: "Docente", directivo: "Directivo", administrativo: "Administrativo", externo: "Externo", admin: "Administrador" };
const AD = {};

function vistaAdmin() {
  const campo = (rotuloCampo, control) => h("label", { class: "campo" }, h("span", { text: rotuloCampo }), control);
  const entrada = (props) => h("input", { class: "entrada", ...props });
  const lista = (props, opciones) => h("select", { class: "entrada", ...props }, opciones.map(([valor, texto]) => h("option", { value: valor, text: texto })));
  const formulario = (titulo, sub, boton, campos, ruta, cuerpo, mensaje) => {
    const f = h("form", { class: "campos" }, campos, h("button", { class: "btn primario", type: "submit", text: boton }));
    f.addEventListener("submit", (ev) => enviarAdmin(ev, ruta, cuerpo, f, mensaje));
    return tarjeta(titulo, sub, null, f);
  };

  const nombre = entrada({ required: true, minlength: 2, placeholder: "Nombre completo" }), correo = entrada({ type: "email", required: true, placeholder: "correo@iest.edu.mx" });
  const rol = lista({}, Object.entries(ROLES)), clave = entrada({ type: "password", required: true, minlength: 8, placeholder: "Mínimo 8 caracteres", autocomplete: "new-password" });
  AD.selUsuario = h("select", { class: "entrada", required: true });
  const placa = entrada({ placeholder: "ABC-123-D" }), marca = entrada({ required: true, placeholder: "Marca" }), modelo = entrada({ required: true, placeholder: "Modelo" }), color = entrada({ required: true, placeholder: "Color" });
  const codigo = entrada({ required: true, minlength: 3, placeholder: "IEST-000123" });
  const tipo = lista({}, [["estudiante", "Estudiante"], ["docente", "Docente"], ["directivo", "Directivo"], ["administrativo", "Administrativo"], ["visitante", "Visitante"]]);
  AD.selVehiculo = h("select", { class: "entrada" });
  AD.usuarios = h("div"); AD.vehiculos = h("div");
  AD.cuentaUs = h("p"); AD.cuentaVe = h("p");

  return h("section", { class: "vista", id: "v-admin" },
    h("div", { class: "formularios" },
      formulario("Registrar usuario", "Acceso al panel y a la app", "Registrar usuario", [campo("Nombre", nombre), campo("Correo", correo), campo("Rol", rol), campo("Contraseña inicial", clave)],
        "/usuarios", () => ({ nombre: nombre.value, correo: correo.value, rol: rol.value, password: clave.value }), "Usuario registrado"),
      formulario("Registrar vehículo", "Se asocia a un usuario", "Registrar vehículo", [campo("Usuario", AD.selUsuario), campo("Placa (opcional)", placa), campo("Marca", marca), campo("Modelo", modelo), campo("Color", color)],
        "/vehiculos", () => ({ usuario_id: +AD.selUsuario.value, placa: placa.value || null, marca: marca.value, modelo: modelo.value, color: color.value }), "Vehículo registrado"),
      formulario("Asignar colgante", "Identifica al vehículo en el cajón", "Asignar colgante", [campo("Código del colgante", codigo), campo("Tipo", tipo), campo("Vehículo", AD.selVehiculo)],
        "/colgantes", () => ({ codigo: codigo.value, tipo: tipo.value, vehiculo_id: AD.selVehiculo.value ? +AD.selVehiculo.value : null }), "Colgante asignado")),
    h("section", { class: "tarjeta" }, h("div", { class: "tarjeta-cab" }, h("div", null, h("h2", { text: "Usuarios" }), AD.cuentaUs)), AD.usuarios),
    h("section", { class: "tarjeta" }, h("div", { class: "tarjeta-cab" }, h("div", null, h("h2", { text: "Vehículos y colgantes" }), AD.cuentaVe)), AD.vehiculos));
}

async function enviarAdmin(ev, ruta, cuerpo, form, mensaje) {
  ev.preventDefault(); const b = form.querySelector("button[type=submit]"); b.disabled = true;
  try { await post(ruta, cuerpo()); toast(mensaje, "ok"); form.reset(); await cargarAdmin(); } catch (e) { toast(e.message, "mal"); } finally { b.disabled = false; }
}

async function cargarAdmin() {
  if (!AD.usuarios) return;
  try {
    const [us, ve] = await Promise.all([api("/usuarios"), api("/vehiculos")]);
    S.admin = { us: us || [], ve: ve || [] };
    pintarAdmin();
  } catch (e) { toast(e.message, "mal"); }
}

function pintarAdmin() {
  const { us, ve } = S.admin; if (!us || !AD.usuarios) return;
  const tabla = (columnas, filas) => h("div", { class: "tabla-caja" }, h("table", { class: "tabla" }, h("thead", null, h("tr", null, columnas.map((c) => h("th", { text: c })))), h("tbody", null, filas)));
  AD.cuentaUs.textContent = `${us.length} registrados`; AD.cuentaVe.textContent = `${ve.length} registrados · ${ve.filter((v) => v.colgante).length} con colgante`;
  AD.usuarios.replaceChildren(us.length ? tabla(["Nombre", "Correo", "Rol", "Cajón asignado"], us.map((u) => h("tr", null,
    h("td", null, h("div", { class: "persona" }, h("div", { class: "avatar chico", text: (u.nombre || "?").trim().charAt(0).toUpperCase() }), u.nombre)),
    h("td", { text: u.correo }), h("td", null, etq(ROLES[u.rol] || u.rol, u.rol === "admin" ? "info" : "")), h("td", null, u.espacioAsignado ? refCajon(u.espacioAsignado) : "—"))))
    : vacio("usuario", "Aún no hay usuarios"));
  const dueno = (v) => { const u = us.find((x) => x.id === v.usuario_id); return u ? u.nombre : "—"; };
  AD.vehiculos.replaceChildren(ve.length ? tabla(["Placa", "Vehículo", "Propietario", "Colgante"], ve.map((v) => h("tr", null,
    h("td", { class: "num", text: v.placa || "—" }), h("td", { text: `${v.marca} ${v.modelo} · ${v.color}` }), h("td", { text: dueno(v) }),
    h("td", null, v.colgante ? etq(`${v.colgante.codigo} · ${v.colgante.tipo}`, "ok") : h("span", { class: "tenue", text: "Sin colgante" })))))
    : vacio("coche", "Aún no hay vehículos registrados"));
  const previo = AD.selUsuario.value;
  AD.selUsuario.replaceChildren(...us.map((u) => h("option", { value: u.id, text: `${u.nombre} (${u.correo})` })));
  if (previo) AD.selUsuario.value = previo;
  AD.selVehiculo.replaceChildren(h("option", { value: "", text: "— sin vehículo —" }), ...ve.filter((v) => !v.colgante).map((v) => h("option", { value: v.id, text: `${v.placa || "sin placa"} · ${v.marca} ${v.modelo}` })));
}
