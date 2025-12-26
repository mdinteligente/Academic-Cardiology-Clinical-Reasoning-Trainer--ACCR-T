import streamlit as st
import pandas as pd
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz # Para hora local (Colombia)

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="ACCR-T Analytics", page_icon="🩺", layout="wide")
TIMEZONE = pytz.timezone('America/Bogota')

# BASE DE DATOS ESTUDIANTES (Ejemplo)
DB_ESTUDIANTES = {
    "1001": "Juan Pérez", "1002": "Maria Gomez", "1003": "Carlos Ruiz",
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
        if not df.empty and 'Fecha_Registro' in df.columns:
            df['Fecha_dt'] = pd.to_datetime(df['Fecha_Registro'])
        return df
    except Exception:
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
    st.title("🫀 ACCR-T Portal")
    if not st.session_state['auth']:
        with st.expander("🔐 Acceso Docente"):
            login(st.text_input("Usuario"), st.text_input("Clave", type="password"))
    else:
        st.success("Docente Conectado")
        if st.button("Salir"): st.session_state['auth'] = False; st.rerun()

tabs = st.tabs(["👨‍🎓 Estudiante", "📊 Analítica Docente"])

# --- PESTAÑA ESTUDIANTE ---
with tabs[0]:
    st.header("Carga de Caso Clínico")
    c1, c2 = st.columns([1, 2])
    with c1:
        codigo = st.text_input("Tu Código:", placeholder="1001")
        grupo = st.selectbox("Grupo Rotación:", list("ABCDEFGHIJKLMNOP"))
        nombre = DB_ESTUDIANTES.get(codigo)
        if nombre: st.success(f"Hola, {nombre}")
    
    if nombre:
        with c2:
            json_txt = st.text_area("Pega el JSON del GPT:", height=250)
            
            if st.button("Enviar Reporte Oficial", type="primary"):
                try:
                    d = json.loads(json_txt)
                    cri = d.get("evaluacion_cri_ht_s", {})
                    
                    # Validación Matemática Estricta
                    # DX (8 pts max) + TX (2 pts max)
                    s_recol = float(cri.get("recoleccion_datos", {}).get("puntaje", 0))
                    s_sint = float(cri.get("representacion_problema", {}).get("puntaje", 0))
                    s_hipo = float(cri.get("generacion_hipotesis", {}).get("puntaje", 0))
                    s_interp = float(cri.get("interpretacion_datos", {}).get("puntaje", 0))
                    s_manejo = float(cri.get("toma_decisiones", {}).get("puntaje", 0)) # Terapéutico
                    
                    score_dx = s_recol + s_sint + s_hipo + s_interp
                    score_tx = s_manejo
                    total_calc = score_dx + score_tx
                    
                    # Timestamp Automático (Bogotá)
                    now = datetime.now(TIMEZONE)
                    fecha_reg = now.strftime("%Y-%m-%d")
                    hora_reg = now.strftime("%H:%M:%S")

                    # Fila para Google Sheets
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
                        st.success(f"✅ Registrado el {fecha_reg} a las {hora_reg}")
                except Exception as e:
                    st.error(f"Error en JSON: {e}")

# --- PESTAÑA DOCENTE ---
with tabs[1]:
    if st.session_state['auth']:
        df = cargar_datos()
        if not df.empty:
            st.markdown("### 🎛️ Filtros Avanzados")
            
            # 1. Filtros Demográficos
            f1, f2, f3 = st.columns(3)
            filtro_grupo = f1.multiselect("Filtrar Grupo:", sorted(df['Grupo'].unique()))
            
            # Estudiantes dinámicos según grupo seleccionado
            if filtro_grupo:
                estudiantes_disponibles = df[df['Grupo'].isin(filtro_grupo)]['Nombre'].unique()
            else:
                estudiantes_disponibles = df['Nombre'].unique()
                
            filtro_estudiante = f2.multiselect("Filtrar Estudiante:", estudiantes_disponibles)
            
            # 2. Filtros de Desempeño (Sliders)
            st.markdown("---")
            st.markdown("#### 🎯 Filtrar por Notas")
            s1, s2, s3 = st.columns(3)
            min_dx = s1.slider("Min. Razonamiento Diagnóstico (0-8)", 0.0, 8.0, 0.0)
            min_tx = s2.slider("Min. Razonamiento Terapéutico (0-2)", 0.0, 2.0, 0.0)
            min_tot = s3.slider("Min. Nota Global (0-10)", 0.0, 10.0, 0.0)

            # APLICAR LÓGICA DE FILTRADO
            df_view = df.copy()
            if filtro_grupo: df_view = df_view[df_view['Grupo'].isin(filtro_grupo)]
            if filtro_estudiante: df_view = df_view[df_view['Nombre'].isin(filtro_estudiante)]
            
            # Filtro Numérico
            df_view = df_view[
                (df_view['Score_Diagnostico'] >= min_dx) &
                (df_view['Score_Terapeutico'] >= min_tx) &
                (df_view['Puntaje_Total'] >= min_tot)
            ]

            # --- VISUALIZACIÓN ---
            st.divider()
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Registros Filtrados", len(df_view))
            k2.metric("Promedio Global", f"{df_view['Puntaje_Total'].mean():.1f}/10")
            k3.metric("Promedio Dx (Max 8)", f"{df_view['Score_Diagnostico'].mean():.1f}")
            k4.metric("Promedio Tx (Max 2)", f"{df_view['Score_Terapeutico'].mean():.1f}")
            
            st.subheader("📋 Tabla Detallada")
            st.dataframe(
                df_view[['Fecha_Registro', 'Hora_Registro', 'Grupo', 'Nombre', 'Caso_ID', 
                         'Puntaje_Total', 'Score_Diagnostico', 'Score_Terapeutico', 'Sesgos']],
                use_container_width=True
            )
            
            st.subheader("📉 Dispersión: Diagnóstico vs Terapéutica")
            st.scatter_chart(df_view, x='Score_Diagnostico', y='Score_Terapeutico', color='Grupo')

        else:
            st.info("No hay datos cargados.")
        st.info("🔒 Inicie sesión en la barra lateral para ver los datos.")




