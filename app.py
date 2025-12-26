import streamlit as st
import pandas as pd
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="ACCR-T Analytics", page_icon="🩺", layout="wide")
TIMEZONE = pytz.timezone('America/Bogota')

# BASE DE DATOS ESTUDIANTES (Personaliza esto con tu lista real)
DB_ESTUDIANTES = {
    "1001": "Juan Pérez", 
    "1002": "Maria Gomez", 
    "1003": "Carlos Ruiz",
    "MED-2025": "Estudiante Prueba"
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
            # --- 🛠️ CORRECCIÓN CRÍTICA DE TIPOS (TEXTO -> NÚMERO) ---
            cols_numericas = ['Puntaje_Total', 'Score_Diagnostico', 'Score_Terapeutico']
            for col in cols_numericas:
                if col in df.columns:
                    # Convierte a número, si falla pone 0.0
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
            # Corrección de Fechas
            if 'Fecha_Registro' in df.columns:
                df['Fecha_dt'] = pd.to_datetime(df['Fecha_Registro'], errors='coerce')
                
        return df
    except Exception as e:
        st.error(f"Error conectando a la base de datos: {e}")
        return pd.DataFrame()

def guardar_registro(data_list):
    try:
        sheet = conectar_sheet()
        sheet.append_row(data_list)
        return True
    except Exception as e:
        st.error(f"Error guardando: {e}")
        return False

# --- LOGIN DOCENTE ---
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
        st.success("Docente Conectado")
        if st.button("Cerrar Sesión"): st.session_state['auth'] = False; st.rerun()

tabs = st.tabs(["👨‍🎓 Estudiante", "📊 Analítica Docente"])

# --- PESTAÑA ESTUDIANTE ---
with tabs[0]:
    st.header("Carga de Caso Clínico")
    c1, c2 = st.columns([1, 2])
    with c1:
        codigo = st.text_input("Tu Código:", placeholder="Ej: 1001")
        grupo = st.selectbox("Grupo Rotación:", list("ABCDEFGHIJKLMNOP"))
        nombre = DB_ESTUDIANTES.get(codigo)
        if nombre: st.success(f"Hola, {nombre}")
    
    if nombre:
        with c2:
            st.info("Instrucción: Al finalizar la simulación con el GPT, copia el bloque de código y pégalo aquí.")
            json_txt = st.text_area("Pega el JSON aquí:", height=250)
            
            if st.button("Enviar Reporte Oficial", type="primary"):
                try:
                    d = json.loads(json_txt)
                    cri = d.get("evaluacion_cri_ht_s", {})
                    
                    # Cálculos Matemáticos
                    s_recol = float(cri.get("recoleccion_datos", {}).get("puntaje", 0))
                    s_sint = float(cri.get("representacion_problema", {}).get("puntaje", 0))
                    s_hipo = float(cri.get("generacion_hipotesis", {}).get("puntaje", 0))
                    s_interp = float(cri.get("interpretacion_datos", {}).get("puntaje", 0))
                    s_manejo = float(cri.get("toma_decisiones", {}).get("puntaje", 0))
                    
                    score_dx = s_recol + s_sint + s_hipo + s_interp
                    score_tx = s_manejo
                    total_calc = score_dx + score_tx
                    
                    # Tiempos
                    now = datetime.now(TIMEZONE)
                    fecha_reg = now.strftime("%Y-%m-%d")
                    hora_reg = now.strftime("%H:%M:%S")

                    # Fila para Google Sheets (Orden estricto según encabezados)
                    row = [
                        fecha_reg, hora_reg, grupo, codigo, nombre,
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
                        st.success(f"✅ Registrado exitosamente: {fecha_reg} {hora_reg}")
                except Exception as e:
                    st.error(f"Error procesando el archivo: {e}")

# --- PESTAÑA DOCENTE ---
with tabs[1]:
    if st.session_state['auth']:
        df = cargar_datos()
        
        if not df.empty:
            # --- FILTROS ---
            st.markdown("### 🎛️ Panel de Control")
            
            # Filtro 1: Grupo
            grupos_disponibles = sorted(df['Grupo'].unique().astype(str))
            sel_grupo = st.multiselect("1. Filtrar Grupo:", grupos_disponibles)
            
            # Filtro 2: Estudiante (Dinámico)
            if sel_grupo:
                estudiantes_disp = df[df['Grupo'].isin(sel_grupo)]['Nombre'].unique()
            else:
                estudiantes_disp = df['Nombre'].unique()
            sel_est = st.multiselect("2. Filtrar Estudiante:", estudiantes_disp)
            
            # Filtro 3: Notas (Sliders)
            st.markdown("---")
            c_f1, c_f2, c_f3 = st.columns(3)
            min_dx = c_f1.slider("Mínimo Raz. Diagnóstico (0-8)", 0.0, 8.0, 0.0)
            min_tx = c_f2.slider("Mínimo Raz. Terapéutico (0-2)", 0.0, 2.0, 0.0)
            min_tot = c_f3.slider("Mínimo Nota Global (0-10)", 0.0, 10.0, 0.0)
            
            # --- APLICACIÓN DE FILTROS ---
            df_view = df.copy()
            if sel_grupo: df_view = df_view[df_view['Grupo'].isin(sel_grupo)]
            if sel_est: df_view = df_view[df_view['Nombre'].isin(sel_est)]
            
            # Filtro numérico (Aquí es donde fallaba antes, ahora ya no gracias a pd.to_numeric)
            df_view = df_view[
                (df_view['Score_Diagnostico'] >= min_dx) &
                (df_view['Score_Terapeutico'] >= min_tx) &
                (df_view['Puntaje_Total'] >= min_tot)
            ]
            
            # --- KPI ---
            st.divider()
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Registros", len(df_view))
            if not df_view.empty:
                k2.metric("Promedio Global", f"{df_view['Puntaje_Total'].mean():.1f}")
                k3.metric("Promedio Dx (Max 8)", f"{df_view['Score_Diagnostico'].mean():.1f}")
                k4.metric("Promedio Tx (Max 2)", f"{df_view['Score_Terapeutico'].mean():.1f}")
            
            # --- GRÁFICAS ---
            st.subheader("📋 Detalle de Notas")
            st.dataframe(
                df_view[['Fecha_Registro', 'Grupo', 'Nombre', 'Caso_ID', 'Puntaje_Total', 'Score_Diagnostico', 'Score_Terapeutico']],
                use_container_width=True
            )
            
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.caption("Correlación: Diagnóstico vs Terapéutica")
                st.scatter_chart(df_view, x='Score_Diagnostico', y='Score_Terapeutico', color='Grupo')
            
            with col_g2:
                st.caption("Distribución de Sesgos")
                # Lógica simple para contar sesgos
                if 'Sesgos' in df_view.columns:
                    all_biases = []
                    for s in df_view['Sesgos'].astype(str):
                        all_biases.extend([b.strip() for b in s.split(',') if b.strip()])
                    if all_biases:
                        st.bar_chart(pd.Series(all_biases).value_counts())
        else:
            st.info("No hay datos cargados en la base de datos.")



