import streamlit as st
import pandas as pd
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="ACCR-T Analytics", page_icon="🩺", layout="wide")

# BASE DE DATOS ESTUDIANTES (Simulada para el ejemplo)
DB_ESTUDIANTES = {
    "1001": "Juan Pérez", "1002": "Maria Gomez", "1003": "Carlos Ruiz",
    "MED-2025": "Estudiante Prueba"
}

# --- 2. CONEXIÓN GOOGLE SHEETS ---
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
        # Convertir fecha texto a objeto fecha para filtrar
        if not df.empty and 'Fecha' in df.columns:
            df['Fecha_dt'] = pd.to_datetime(df['Fecha']).dt.date
        return df
    except Exception as e:
        return pd.DataFrame()

def guardar_registro(data_list):
    try:
        sheet = conectar_sheet()
        sheet.append_row(data_list)
        return True
    except Exception as e:
        st.error(f"Error guardando: {e}")
        return False

# --- 3. LOGIN DOCENTE ---
if 'auth' not in st.session_state: st.session_state['auth'] = False

def login(u, p):
    if u == st.secrets["admin_user"] and p == st.secrets["admin_password"]:
        st.session_state['auth'] = True

# --- 4. INTERFAZ ---
with st.sidebar:
    st.image("https://img.icons8.com/color/96/health-graph.png", width=60)
    st.title("ACCR-T Portal")
    if not st.session_state['auth']:
        with st.expander("🔐 Acceso Docente"):
            login(st.text_input("Usuario"), st.text_input("Clave", type="password"))
    else:
        if st.button("Cerrar Sesión"): 
            st.session_state['auth'] = False
            st.rerun()

tabs = st.tabs(["👨‍🎓 Registro Estudiante", "📊 Analítica Docente"])

# --- PESTAÑA 1: ESTUDIANTES ---
with tabs[0]:
    st.header("Envío de Reporte Clínico")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        codigo = st.text_input("Tu Código:", placeholder="1001")
        grupo = st.selectbox("Grupo de Rotación:", list("ABCDEFGHIJKLMNOP"))
        nombre = DB_ESTUDIANTES.get(codigo)
        if nombre: st.success(f"Hola, {nombre}")
        elif codigo: st.error("Código no encontrado.")

    if nombre:
        with col2:
            json_txt = st.text_area("Pega el JSON del GPT:", height=200)
            c_h1, c_h2 = st.columns(2)
            h_ini = c_h1.text_input("Hora Inicio (HH:MM)", placeholder="08:00")
            h_fin = c_h2.text_input("Hora Fin (HH:MM)", placeholder="08:45")
            
            if st.button("Registrar Caso", type="primary"):
                try:
                    d = json.loads(json_txt)
                    cri = d.get("evaluacion_cri_ht_s", {})
                    
                    # Cálculos Desglosados
                    # Diagnóstico = Recolección + Síntesis + Hipótesis + Interpretación (Max 8)
                    score_dx = (float(cri.get("recoleccion_datos", {}).get("puntaje", 0)) +
                                float(cri.get("representacion_problema", {}).get("puntaje", 0)) +
                                float(cri.get("generacion_hipotesis", {}).get("puntaje", 0)) +
                                float(cri.get("interpretacion_datos", {}).get("puntaje", 0)))
                    
                    # Terapéutico = Manejo/OMS (Max 2)
                    score_tx = float(cri.get("toma_decisiones", {}).get("puntaje", 0))

                    # Duración
                    fmt = "%H:%M"
                    dur = (datetime.strptime(h_fin, fmt) - datetime.strptime(h_ini, fmt)).seconds // 60
                    
                    # Orden para Google Sheets (COINCIDIR CON ENCABEZADOS)
                    row = [
                        str(date.today()), grupo, codigo, nombre,
                        d.get("metadata", {}).get("caso_id"),
                        d.get("metadata", {}).get("nivel"),
                        d.get("metadata", {}).get("diagnostico_real"),
                        cri.get("total_sobre_10"),
                        score_dx, score_tx, # Nuevos campos desglosados
                        h_ini, h_fin, dur,
                        cri.get("recoleccion_datos", {}).get("puntaje"),
                        cri.get("representacion_problema", {}).get("puntaje"),
                        cri.get("generacion_hipotesis", {}).get("puntaje"),
                        cri.get("interpretacion_datos", {}).get("puntaje"),
                        cri.get("toma_decisiones", {}).get("puntaje"),
                        ", ".join(d.get("sesgos_cognitivos", {}).get("detectados", [])),
                        d.get("traza_cognitiva", {}).get("illness_script_estudiante")
                    ]
                    
                    if guardar_registro(row):
                        st.balloons()
                        st.success("✅ ¡Caso registrado exitosamente!")
                except Exception as e:
                    st.error(f"Error: {e}")

# --- PESTAÑA 2: DOCENTE ---
with tabs[1]:
    if st.session_state['auth']:
        df = cargar_datos()
        if not df.empty:
            st.markdown("### 🎛️ Filtros de Análisis")
            fc1, fc2, fc3 = st.columns(3)
            
            # Filtro Fechas
            min_date = df['Fecha_dt'].min()
            max_date = df['Fecha_dt'].max()
            date_range = fc1.date_input("Rango de Fechas", [min_date, max_date])
            
            # Filtro Grupo
            gr_opts = ["Todos"] + sorted(df['Grupo'].unique().tolist())
            sel_grupo = fc2.selectbox("Filtrar Grupo:", gr_opts)
            
            # Aplicar Filtros
            mask = (df['Fecha_dt'] >= date_range[0]) & (df['Fecha_dt'] <= date_range[1])
            if sel_grupo != "Todos": mask = mask & (df['Grupo'] == sel_grupo)
            df_filtered = df[mask]
            
            st.divider()
            
            # --- DASHBOARD ---
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Casos Totales", len(df_filtered))
            
            # Promedios
            avg_total = df_filtered['Puntaje_Total'].mean()
            avg_dx = df_filtered['Score_Diagnostico'].mean() # Sobre 8
            avg_tx = df_filtered['Score_Terapeutico'].mean() # Sobre 2
            
            m2.metric("Promedio Global (0-10)", f"{avg_total:.1f}")
            m3.metric("🧠 Raz. Diagnóstico (0-8)", f"{avg_dx:.1f}", delta_color="normal")
            m4.metric("💊 Raz. Terapéutico (0-2)", f"{avg_tx:.1f}", delta_color="normal")
            
            st.markdown("### 📉 Análisis Comparativo")
            c_chart1, c_chart2 = st.columns(2)
            
            with c_chart1:
                st.caption("Desempeño Diagnóstico vs Terapéutico por Estudiante")
                st.scatter_chart(df_filtered, x='Score_Diagnostico', y='Score_Terapeutico', color='Nivel')
            
            with c_chart2:
                st.caption("Evolución de Notas Promedio")
                st.line_chart(df_filtered.set_index('Fecha')['Puntaje_Total'])
            
            st.dataframe(df_filtered)
        else:
            st.info("No hay datos.")
        st.info("🔒 Inicie sesión en la barra lateral para ver los datos.")



