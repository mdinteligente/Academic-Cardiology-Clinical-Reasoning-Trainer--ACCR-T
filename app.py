import streamlit as st
import pandas as pd
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import pytz
import altair as alt

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

                    row = [
                        f_reg, h_reg, grupo, codigo, nombre,
                        d.get("metadata", {}).get("caso_id"),
                        d.get("metadata", {}).get("nivel"),
                        d.get("metadata", {}).get("diagnostico_real"),
                        total_calc, score_dx, score_tx,
                        s_recol, s_sint, s_hipo, s_interp, s_manejo,
                        ", ".join(d.get("sesgos_cognitivos", {}).get("detectados", [])),
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
            # FILTROS
            st.markdown("### 🎛️ Panel de Control")
            f1, f2, f3 = st.columns(3)
            
            grupos = ["Todos"] + sorted(df['Grupo'].unique().tolist())
            sel_grupo = f1.selectbox("Grupo:", grupos)
            
            if sel_grupo != "Todos":
                est_list = ["Todos"] + df[df['Grupo'] == sel_grupo]['Nombre'].unique().tolist()
            else:
                est_list = ["Todos"] + df['Nombre'].unique().tolist()
            sel_est = f2.selectbox("Estudiante:", est_list)
            
            # APLICAR FILTROS
            df_view = df.copy()
            if sel_grupo != "Todos": df_view = df_view[df_view['Grupo'] == sel_grupo]
            if sel_est != "Todos": df_view = df_view[df_view['Nombre'] == sel_est]
            
            # KPI
            st.divider()
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Registros", len(df_view))
            k2.metric("Promedio Global", f"{df_view['Puntaje_Total'].mean():.1f}/10")
            k3.metric("Promedio Dx (0-8)", f"{df_view['Score_Diagnostico'].mean():.1f}")
            k4.metric("Promedio Tx (0-2)", f"{df_view['Score_Terapeutico'].mean():.1f}")
            
            # ANÁLISIS DE DOMINIOS
            st.markdown("### 🔬 Micro-Análisis de Dominios")
            dominios = {
                '1. Recolección': 'CRI_Recoleccion',
                '2. Síntesis (Script)': 'CRI_Sintesis',
                '3. Hipótesis': 'CRI_Hipotesis',
                '4. Interpretación': 'CRI_Interpretacion',
                '5. Manejo (OMS)': 'OMS_Manejo'
            }
            avg_data = {k: df_view[v].mean() for k, v in dominios.items()}
            df_chart = pd.DataFrame(list(avg_data.items()), columns=['Competencia', 'Puntaje Promedio'])
            
            chart = alt.Chart(df_chart).mark_bar().encode(
                x=alt.X('Competencia', sort=None),
                y=alt.Y('Puntaje Promedio', scale=alt.Scale(domain=[0, 2])),
                color=alt.condition(
                    alt.datum['Puntaje Promedio'] < 1.0,
                    alt.value('#FF4B4B'),  # Rojo
                    alt.value('#1C83E1')   # Azul
                ),
                tooltip=['Competencia', 'Puntaje Promedio']
            ).properties(height=300)
            st.altair_chart(chart, use_container_width=True)
            
            # TABLA SEMÁFORO (CORREGIDA)
            st.subheader("📋 Detalle por Estudiante")
            cols_detalle = ['Fecha_Registro', 'Nombre', 'Grupo', 
                           'CRI_Recoleccion', 'CRI_Sintesis', 'CRI_Hipotesis', 
                           'CRI_Interpretacion', 'OMS_Manejo', 'Puntaje_Total']
            
            cols_numericas_style = ['CRI_Recoleccion', 'CRI_Sintesis', 'CRI_Hipotesis', 
                                   'CRI_Interpretacion', 'OMS_Manejo']
            
            # AQUÍ ESTÁ LA CORRECCIÓN CLAVE: subset=cols_numericas_style
            st.dataframe(
                df_view[cols_detalle].style.background_gradient(
                    subset=cols_numericas_style,
                    cmap='RdYlGn', vmin=0, vmax=2
                ).format(
                    "{:.1f}", subset=cols_numericas_style + ['Puntaje_Total']
                ),
                use_container_width=True
            )
            
            # SESGOS
            st.divider()
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                st.subheader("🧠 Sesgos Detectados")
                if 'Sesgos' in df_view.columns:
                    all_biases = []
                    for s in df_view['Sesgos'].astype(str):
                        items = [b.strip() for b in s.split(',') if b.strip() and b.strip().lower() != 'ninguno']
                        all_biases.extend(items)
                    if all_biases:
                        st.bar_chart(pd.Series(all_biases).value_counts())
            
            with col_b2:
                st.subheader("📝 Scripts (Muestra)")
                samples = df_view['Illness_Script'].dropna().sample(min(5, len(df_view)))
                for s in samples: st.text(f"• {s}")
        else:
            st.info("Base de datos vacía.")




