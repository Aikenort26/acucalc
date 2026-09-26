import base64
import datetime as dt
import matplotlib.pyplot as plt
import streamlit as st
from core import dane, geo, network, project as pj, study_map as sm
from core.imagenes import reducir_a_b64
from pages_common import (SAVES_DIR, AUTOSAVE_FILE, page_setup, num_input, int_input,
                          clear_widget_state, sel_state, txt_state)

p = page_setup()
st.header("1 · Proyecto")

c1, c2 = st.columns(2)
with c1:
    p.nombre = st.text_input("Nombre del proyecto", key=txt_state("txt_nombre", p.nombre))
    dptos = dane.departamentos()
    p.poblacion.dpto = st.selectbox(
        "Departamento (DANE)", dptos, key=sel_state(dptos, "sel_dpto", p.poblacion.dpto))
    p.departamento = p.poblacion.dpto
    mpios = dane.municipios(p.poblacion.dpto)
    p.poblacion.mpio = st.selectbox(
        "Municipio (DANE)", mpios, key=sel_state(mpios, "sel_mpio", p.poblacion.mpio))
    p.municipio = p.poblacion.mpio
    p.poblacion.tipo = st.radio(
        "El estudio es en:", ["municipio", "corregimiento"],
        format_func={"municipio": "Cabecera municipal",
                     "corregimiento": "Corregimiento / vereda"}.get,
        horizontal=True,
        key=sel_state(["municipio", "corregimiento"], "radio_tipo", p.poblacion.tipo))
    if p.poblacion.tipo == "corregimiento":
        p.corregimiento = st.text_input("Nombre del corregimiento / vereda",
                                        key=txt_state("txt_corr", p.corregimiento))
    else:
        p.corregimiento = ""
with c2:
    p.consultor = st.text_input("Consultor / entidad", key=txt_state("txt_consultor", p.consultor))
    p.fecha = st.text_input("Fecha", key=txt_state("txt_fecha",
                                                 p.fecha or dt.date.today().isoformat()))
    p.altitud = num_input("Altitud promedio [m.s.n.m.]", "altitud", p.altitud,
                          decimals=0, min_value=0.0, max_value=4500.0)
    p.temperatura = num_input("Temperatura del agua [°C]", "temperatura", p.temperatura,
                              decimals=1, min_value=0.0, max_value=50.0)

if AUTOSAVE_FILE.exists() and not p.nombre:
    st.info("Hay una sesión anterior sin guardar explícitamente.")
    with st.popover("♻ Restaurar última sesión (autosave)"):
        st.warning("Esto reemplaza los datos actuales (no guardados) con el autosave.")
        if st.button("Restaurar definitivamente", key="w_confirm_restore_autosave"):
            try:
                st.session_state["project"] = pj.load(AUTOSAVE_FILE)
                clear_widget_state()
                st.rerun()
            except pj.SchemaError as e:
                st.error(f"No se pudo restaurar el autosave: {e}")

st.caption("La serie de población DANE del municipio seleccionado alimenta la página "
           "2 (tasas de crecimiento y proyección).")

with st.expander("Logos de portada del informe", expanded=False):
    l1, l2 = st.columns(2)
    up_cli = l1.file_uploader("Logo del cliente/entidad", type=["png", "jpg", "jpeg"],
                              key="w_up_logo_cli")
    if up_cli is not None:
        p.logo_cliente_b64 = reducir_a_b64(up_cli.getvalue())
    if p.logo_cliente_b64:
        l1.image(base64.b64decode(p.logo_cliente_b64), width=160)
        if l1.button("Quitar logo del cliente", key="w_rm_logo_cli"):
            p.logo_cliente_b64 = ""
            st.rerun()
    up_con = l2.file_uploader("Logo del consultor", type=["png", "jpg", "jpeg"],
                              key="w_up_logo_con")
    if up_con is not None:
        p.logo_consultor_b64 = reducir_a_b64(up_con.getvalue())
    if p.logo_consultor_b64:
        l2.image(base64.b64decode(p.logo_consultor_b64), width=160)
        if l2.button("Quitar logo del consultor", key="w_rm_logo_con"):
            p.logo_consultor_b64 = ""
            st.rerun()

with st.expander("Localización y mapas de la zona de estudio", expanded=False):
    ub = p.ubicacion
    st.caption("Los mapas se descargan una sola vez con el botón y quedan guardados en el "
               "proyecto: el informe se genera sin conexión. Fuentes: OpenStreetMap o Esri "
               "World Imagery, con su atribución impresa en cada mapa.")
    b1, b2 = st.columns([4, 1], vertical_alignment="bottom")
    lugar_def = ", ".join(x for x in (p.corregimiento, p.municipio, p.departamento) if x)
    ub.busqueda = b1.text_input("Buscar lugar (Nominatim, OpenStreetMap)",
                                key=txt_state("txt_ub_buscar", ub.busqueda or lugar_def))
    if b2.button("🔎 Buscar", key="w_ub_btn_buscar", width="stretch"):
        try:
            st.session_state["ub_lugares"] = geo.buscar(ub.busqueda)
            if not st.session_state["ub_lugares"]:
                st.warning("Sin resultados: pruebe con «municipio, departamento» o ingrese "
                           "las coordenadas.")
        except geo.GeoError as e:
            st.error(str(e))
    lugares = st.session_state.get("ub_lugares") or []
    if lugares:
        r1, r2 = st.columns([4, 1], vertical_alignment="bottom")
        i_l = r1.selectbox("Resultados", range(len(lugares)), key="w_ub_resultado",
                           format_func=lambda i: f"{lugares[i].nombre} "
                                                 f"({lugares[i].lat:.5f}, {lugares[i].lon:.5f})")
        if r2.button("Usar este lugar", key="w_ub_usar", width="stretch"):
            ub.lat, ub.lon = lugares[i_l].lat, lugares[i_l].lon
            st.session_state["w_ub_lat"] = round(ub.lat, 6)
            st.session_state["w_ub_lon"] = round(ub.lon, 6)
            st.session_state.pop("ub_lugares", None)
            st.rerun()
    g1, g2, g3, g4 = st.columns(4)
    ub.lat = num_input("Latitud [°] (WGS84, + norte)", "ub_lat", ub.lat, decimals=6,
                       container=g1, min_value=-85.0, max_value=85.0)
    ub.lon = num_input("Longitud [°] (WGS84, − oeste)", "ub_lon", ub.lon, decimals=6,
                       container=g2, min_value=-180.0, max_value=180.0)
    ub.zoom_general = int_input("Zoom del mapa general", "ub_zg", ub.zoom_general,
                                container=g3, min_value=3, max_value=14,
                                help="8–10 muestra el municipio y su región.")
    ub.zoom_zona = int_input("Zoom de la zona de estudio", "ub_zz", ub.zoom_zona,
                             container=g4, min_value=10, max_value=19,
                             help="15–17 muestra la cabecera o el corregimiento.")
    f1, f2 = st.columns(2)
    fuentes = list(geo.FUENTES)
    ub.fuente = f1.radio("Fuente", fuentes, horizontal=True, key=sel_state(fuentes, "radio_ub_fuente",
                                                                           ub.fuente),
                         format_func=lambda k: geo.FUENTES[k].nombre)
    epsgs = list(sm.EPSG_RED)
    ub.epsg_red = f2.selectbox("Coordenadas del .inp de la red (para superponerla)", epsgs,
                               key=sel_state(epsgs, "sel_ub_epsg", ub.epsg_red),
                               format_func=sm.EPSG_RED.get)
    if ub.fuente == "esri":
        st.caption("Esri World Imagery: uso sujeto a los términos de Esri; verifique que su "
                   "licencia cubre la publicación del informe.")
    ub.en_informe = st.checkbox("Incluir la localización en la memoria", value=ub.en_informe,
                                key="w_chk_ub_inf")
    d1, d2 = st.columns([1, 1])
    if d1.button("🗺️ Descargar mapas", key="w_ub_descargar", type="primary",
                 disabled=not (ub.lat or ub.lon)):
        with st.spinner("Descargando teselas…"):
            try:
                ub.mapas = sm.componer_mapas(ub)
            except (geo.GeoError, ValueError) as e:
                st.error(str(e))
    if ub.mapas and d2.button("Quitar mapas guardados", key="w_ub_quitar"):
        ub.mapas = []
        st.rerun()
    por_nombre = {m.nombre: m for m in ub.mapas}
    if por_nombre:
        zona, general = por_nombre.get("zona"), por_nombre.get("general")
        desactualizado = any(
            m.fuente != ub.fuente or m.z != z or not (
                sm.extension(m)[0] < ub.lat < sm.extension(m)[2]
                and sm.extension(m)[1] < ub.lon < sm.extension(m)[3])
            for m, z in ((general, ub.zoom_general), (zona, ub.zoom_zona)) if m)
        if desactualizado:
            st.warning("Los mapas guardados no corresponden a la ubicación, el zoom o la "
                       "fuente actuales: vuelva a descargarlos.")
        segmentos = None
        if ub.epsg_red and p.red_inp and zona:
            try:
                segmentos = sm.red_a_latlon(network.parse_inp(p.red_inp), ub.epsg_red)
                if segmentos and sm.fraccion_dentro(zona, segmentos) < 0.5:
                    st.warning("La mayor parte de la red cae fuera del mapa de la zona: revise "
                               "el sistema de coordenadas del .inp o el zoom.")
            except (ValueError, geo.GeoError) as e:
                st.warning(f"No se pudo superponer la red: {e}")
        m1, m2 = st.columns(2)
        for col, mapa, titulo, kw in (
                (m1, general, "Localización general",
                 {"recuadro": sm.extension(zona) if zona else None}),
                (m2, zona, "Zona de estudio", {"segmentos": segmentos})):
            fig = sm.fig_localizacion(mapa, ub.lat, ub.lon, titulo, **kw)
            if fig is not None:
                col.pyplot(fig)
                plt.close(fig)

st.divider()
p.ruta_guardado = st.text_input(
    "📁 Ruta de guardado del proyecto (carpeta o archivo .acucalc.json en tu computador)",
    key=txt_state("txt_ruta_guardado", p.ruta_guardado),
    placeholder=r"ej. C:\Users\aiken\Proyectos\San_Jacinto   —   o un archivo .acucalc.json",
    help="El botón '💾 Guardar estado del proyecto' de la barra lateral y el autosave "
         "escribirán AQUÍ (tu carpeta), no en la carpeta interna de la app. Si dejas "
         "esto vacío, se guarda en saves/ del programa como antes. Como la app corre "
         "local, puede escribir a cualquier ruta absoluta que teclees o pegues. "
         "Consejo: apunta al ARCHIVO exacto (…\\proyecto.acucalc.json) — si pones solo "
         "la carpeta, el nombre del archivo sigue al nombre del proyecto y renombrarlo "
         "crearía un archivo nuevo.")
if p.ruta_guardado.strip():
    from pages_common import resolve_save_path
    st.caption(f"Se guardará en: `{resolve_save_path(p)}`")

c3, c4 = st.columns(2)
with c3:
    st.download_button(
        "💾 Guardar proyecto (.json)",
        data=__import__("json").dumps(
            {"schema_version": pj.SCHEMA_VERSION, "project": __import__("dataclasses").asdict(p)},
            ensure_ascii=False, indent=1),
        file_name=f"{(p.nombre or 'proyecto').replace(' ', '_')}.acucalc.json",
        mime="application/json",
    )
with c4:
    guardados = sorted(SAVES_DIR.glob("*.acucalc.json")) if SAVES_DIR.exists() else []
    if guardados:
        sel_g = st.selectbox("Proyectos guardados (saves/)",
                             ["—"] + [g.name for g in guardados], key="w_sel_save")
        if sel_g != "—" and st.button("📂 Abrir guardado"):
            try:
                st.session_state["project"] = pj.load(SAVES_DIR / sel_g)
                clear_widget_state()
                st.rerun()
            except pj.SchemaError as e:
                st.error(f"No se pudo cargar: {e}")
    up = st.file_uploader("…o cargar archivo de proyecto", type=["json"])
    # El uploader conserva el archivo entre reruns: sin este guard cada rerun lo
    # volvía a cargar (bucle de st.rerun y ediciones de la página pisadas).
    if up is not None and st.session_state.get("proy_upload_id") != up.file_id:
        st.session_state["proy_upload_id"] = up.file_id
        import tempfile, pathlib
        tmp = pathlib.Path(tempfile.mkstemp(suffix=".json")[1])
        tmp.write_bytes(up.getvalue())
        try:
            st.session_state["project"] = pj.load(tmp)
            clear_widget_state()
            st.success("Proyecto cargado. Revisa las demás páginas.")
            st.rerun()
        except pj.SchemaError as e:
            st.error(f"No se pudo cargar: {e}")
