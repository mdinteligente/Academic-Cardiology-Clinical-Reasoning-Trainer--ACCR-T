import streamlit as st
import pandas as pd
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import altair as alt
import ast # Para leer listas guardadas como texto

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="ACCR-T Analytics", page_icon="🩺", layout="wide")
TIMEZONE = pytz.timezone('America/Bogota')

# BASE DE DATOS ESTUDIANTES
DB_ESTUDIANTES = {
    "1001": "Juan Pérez", "1002": "Maria Gomez", "1003": "Carlos Ruiz",
    "MED-2025": "Estudiante Prueba", "DOCENTE": "Usuario Prueba"
}

# --- CONEXIÓN GOOGLE SHEETS ---
def conectar_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    return client.open("registro_accr_t").sheet1

def cargar_datos():
    try:
        sheet = conectar_sheet()
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            # LIMPIEZA NUMÉRICA
            cols_nums = [
                'Puntaje_Total', 'Score_Diagnostico', 'Score_Terapeutico',
                'CRI_Recoleccion', 'CRI_Sintesis', 'CRI_Hipotesis', 
                'CRI_Interpretacion', 'OMS_Manejo'
            ]
            for col in cols_nums:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
            # LIMPIEZA DE FECHAS
            if 'Fecha_Registro' in df.columns:
                df['Fecha_dt'] = pd.to_datetime(df['Fecha_Registro'], errors='coerce').dt.date
                
        return df
    except Exception as e:
        st.error(f"Error conectando a la nube: {e}")
        return pd.DataFrame()

def guardar_registro(data_list):
    try:
        sheet = conectar_sheet()
        sheet.append_row(data_list)
        return True
    except Exception as e:
        st.error(f"Error guardando: {e}")
        return False

# --- FUNCIÓN AUXILIAR PARA LIMPIAR SESGOS ---
def parse_sesgos(sesgo_str):
    """Convierte strings sucios en listas limpias de sesgos"""
    if not sesgo_str or str(sesgo_str).strip() == "":
        return []
    
    texto = str(sesgo_str).strip()
    
    # Intenta interpretar si viene como lista de Python "['A', 'B']"
    try:
        if texto.startswith("[") and texto.endswith("]"):
            lista = ast.literal_eval(texto)
            if isinstance(lista, list):
                return [s.strip() for s in lista]
    except:
        pass
    
    # Si falla, asume separado por comas "A, B, C"
    return [s.strip() for s in texto.split(',') if s.strip()]

# --- LOGIN ---
if 'auth' not in st.session_state: st.session_state['auth'] = False

def login(u, p):
    if u == st.secrets["admin_user"] and p == st.secrets["admin_password"]:
        st.session_state['auth'] = True

# --- INTERFAZ ---
with st.sidebar:
    st.image("https://img.icons8.com/color/96/health-graph.png", width=50)
    st.title("ACCR-T Portal")
    if not st.session_state['auth']:
        with st.expander("🔐 Acceso Docente"):
            login(st.text_input("Usuario"), st.text_input("Clave", type="password"))
    else:
        st.success("Docente Activo")
        if st.button("Salir"): st.session_state['auth'] = False; st.rerun()

tabs = st.tabs(["👨‍🎓 Registro Estudiante", "📊 Analítica Docente"])

# --- PESTAÑA 1: ESTUDIANTE ---
with tabs[0]:
    st.subheader("Carga de Caso Clínico")
    c1, c2 = st.columns([1, 2])
    with c1:
        codigo = st.text_input("Tu Código:", placeholder="Ej: 1001")
        grupo = st.selectbox("Grupo Rotación:", list("ABCDEFGHIJKLMNOP"))
        nombre = DB_ESTUDIANTES.get(codigo)
        if nombre: st.success(f"Hola, {nombre}")
    
    if nombre:
        with c2:
            st.info("Pega aquí el código JSON del GPT:")
            json_txt = st.text_area("JSON:", height=200)
            
            if st.button("Registrar Resultados", type="primary"):
                try:
                    d = json.loads(json_txt)
                    cri = d.get("evaluacion_cri_ht_s", {})
                    
                    s_recol = float(cri.get("recoleccion_datos", {}).get("puntaje", 0))
                    s_sint = float(cri.get("representacion_problema", {}).get("puntaje", 0))
                    s_hipo = float(cri.get("generacion_hipotesis", {}).get("puntaje", 0))
                    s_interp = float(cri.get("interpretacion_datos", {}).get("puntaje", 0))
                    s_manejo = float(cri.get("toma_decisiones", {}).get("puntaje", 0))
                    
                    score_dx = s_recol + s_sint + s_hipo + s_interp
                    score_tx = s_manejo
                    total_calc = score_dx + score_tx
                    
                    now = datetime.now(TIMEZONE)
                    f_reg = now.strftime("%Y-%m-%d")
                    h_reg = now.strftime("%H:%M:%S")
                    
                    # Manejo seguro de sesgos (lista a string)
                    raw_sesgos = d.get("sesgos_cognitivos", {}).get("detectados", [])
                    if isinstance(raw_sesgos, list):
                        str_sesgos = ", ".join(raw_sesgos)
                    else:
                        str_sesgos = str(raw_sesgos)

                    row = [
                        f_reg, h_reg, grupo, codigo, nombre,
                        d.get("metadata", {}).get("caso_id"),
                        d.get("metadata", {}).get("nivel"),
                        d.get("metadata", {}).get("diagnostico_real"),
                        total_calc, score_dx, score_tx,
                        s_recol, s_sint, s_hipo, s_interp, s_manejo,
                        str_sesgos,
                        d.get("traza_cognitiva", {}).get("illness_script_estudiante")
                    ]
                    
                    if guardar_registro(row):
                        st.balloons()
                        st.success(f"✅ Registrado: {f_reg} - {h_reg}")
                except Exception as e:
                    st.error(f"Error JSON: {e}")

# --- PESTAÑA 2: DOCENTE ---
with tabs[1]:
    if st.session_state['auth']:
        df = cargar_datos()
        
        if not df.empty:
            # --- FILTROS DE PERSONALIZACIÓN ---
            st.markdown("### 🎛️ Filtros de Análisis")
            f1, f2, f3 = st.columns(3)
            
            # Filtro 1: Grupo
            grupos = ["Todos"] + sorted(df['Grupo'].unique().astype(str).tolist())
            sel_grupo = f1.selectbox("1. Grupo:", grupos)
            
            # Filtro 2: Estudiante (Reactivo)
            df_temp = df if sel_grupo == "Todos" else df[df['Grupo'] == sel_grupo]
            ests = ["Todos"] + sorted(df_temp['Nombre'].unique().astype(str).tolist())
            sel_est = f2.selectbox("2. Estudiante:", ests)
            
            # Filtro 3: CASO ID (NUEVO)
            if sel_est != "Todos":
                df_temp = df_temp[df_temp['Nombre'] == sel_est]
            
            # Convertimos Caso_ID a string para filtrar bien
            df['Caso_ID'] = df['Caso_ID'].astype(str)
            casos_disp = ["Todos"] + sorted(df_temp['Caso_ID'].unique().tolist())
            sel_caso = f3.selectbox("3. Caso ID:", casos_disp)

            # --- APLICAR FILTROS ---
            df_view = df.copy()
            if sel_grupo != "Todos": df_view = df_view[df_view['Grupo'] == sel_grupo]
            if sel_est != "Todos": df_view = df_view[df_view['Nombre'] == sel_est]
            if sel_caso != "Todos": df_view = df_view[df_view['Caso_ID'] == sel_caso]
            
            # --- KPI ---
            st.divider()
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Registros", len(df_view))
            k2.metric("Nota Global", f"{df_view['Puntaje_Total'].mean():.1f}/10")
            k3.metric("Nota Diagnóstica", f"{df_view['Score_Diagnostico'].mean():.1f}/8")
            k4.metric("Nota Terapéutica", f"{df_view['Score_Terapeutico'].mean():.1f}/2")
            
            # --- DETALLE (HEATMAP) ---
            st.subheader("📋 Detalle de Resultados")
            cols_ver = ['Fecha_Registro', 'Nombre', 'Grupo', 'Caso_ID', # CASO ID INCLUIDO
                        'CRI_Recoleccion', 'CRI_Sintesis', 'CRI_Hipotesis', 
                        'CRI_Interpretacion', 'OMS_Manejo', 'Puntaje_Total']
            
            cols_style = ['CRI_Recoleccion', 'CRI_Sintesis', 'CRI_Hipotesis', 
                          'CRI_Interpretacion', 'OMS_Manejo']
            
            st.dataframe(
                df_view[cols_ver].style.background_gradient(
                    subset=cols_style, cmap='RdYlGn', vmin=0, vmax=2
                ).format("{:.1f}", subset=cols_style + ['Puntaje_Total']),
                use_container_width=True
            )
            
            # --- GRÁFICA DE SESGOS (CORREGIDA) ---
            st.divider()
            col_b1, col_b2 = st.columns(2)
            
            with col_b1:
                st.subheader("🧠 Tipos de Sesgos Detectados")
                if 'Sesgos' in df_view.columns:
                    all_biases = []
                    for s in df_view['Sesgos']:
                        # Usamos la función de limpieza robusta
                        limpios = parse_sesgos(s)
                        # Filtramos 'None', 'Ninguno', cadenas vacías
                        limpios = [b for b in limpios if len(b) > 2 and 'ningun' not in b.lower()]
                        all_biases.extend(limpios)
                    
                    if all_biases:
                        bias_counts = pd.Series(all_biases).value_counts().reset_index()
                        bias_counts.columns = ['Tipo de Sesgo', 'Frecuencia']
                        
                        # Gráfico Horizontal para leer bien los nombres
                        chart_bias = alt.Chart(bias_counts).mark_bar().encode(
                            x='Frecuencia',
                            y=alt.Y('Tipo de Sesgo', sort='-x'),
                            tooltip=['Tipo de Sesgo', 'Frecuencia'],
                            color=alt.value('#FF4B4B')
                        )
                        st.altair_chart(chart_bias, use_container_width=True)
                    else:
                        st.info("No se detectaron sesgos cognitivos específicos en la selección.")

            # --- ANÁLISIS DE DOMINIOS ---
            with col_b2:
                st.subheader("🔬 Rendimiento por Competencia")
                dominios = {
                    '1. Recolección': 'CRI_Recoleccion',
                    '2. Síntesis': 'CRI_Sintesis',
                    '3. Hipótesis': 'CRI_Hipotesis',
                    '4. Interpretación': 'CRI_Interpretacion',
                    '5. Manejo OMS': 'OMS_Manejo'
                }
                avg_data = {k: df_view[v].mean() for k, v in dominios.items()}
                df_chart = pd.DataFrame(list(avg_data.items()), columns=['Competencia', 'Nota'])
                
                chart_dom = alt.Chart(df_chart).mark_bar().encode(
                    x=alt.X('Competencia', sort=None),
                    y=alt.Y('Nota', scale=alt.Scale(domain=[0, 2])),
                    color=alt.condition(
                        alt.datum.Nota < 1.0,
                        alt.value('red'),
                        alt.value('steelblue')
                    )
                )
                st.altair_chart(chart_dom, use_container_width=True)

        else:
            st.info("No hay datos cargados.")



