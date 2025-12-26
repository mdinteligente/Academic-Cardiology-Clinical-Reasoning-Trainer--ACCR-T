import streamlit as st
import pandas as pd
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import pytz

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="ACCR-T Analytics", page_icon="🩺", layout="wide")
TIMEZONE = pytz.timezone('America/Bogota')

# BASE DE DATOS ESTUDIANTES (Simulada)
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
            # 1. LIMPIEZA DE NÚMEROS (Evita el TypeError)
            cols_nums = ['Puntaje_Total', 'Score_Diagnostico', 'Score_Terapeutico']
            for col in cols_nums:
                # Convierte texto a número, si falla pone 0.0
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
            # 2. LIMPIEZA DE FECHAS
            if 'Fecha_Registro' in df.columns:
                df['Fecha_dt'] = pd.to_datetime(df['Fecha_Registro'], errors='coerce').dt.date
                
        return df
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return pd.DataFrame()

def guardar_registro(data_list):
    try:
        sheet = conectar_sheet()
        sheet.append_row(data_list)
        return True
    except Exception as e:
        st.error(f"Error guardando en la nube: {e}")
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
            st.info("Pega aquí el código que te dio el GPT al finalizar el caso.")
            json_txt = st.text_area("JSON del Caso:", height=200)
            
            if st.button("Registrar en Base de Datos", type="primary"):
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
                    f_reg = now.strftime("%Y-%m-%d")
                    h_reg = now.strftime("%H:%M:%S")

                    # Fila para Google Sheets (Orden EXACTO a los encabezados)
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
                        st.success(f"✅ Registrado: {f_reg} a las {h_reg}")
                except Exception as e:
                    st.error(f"Error en el formato del JSON: {e}")

# --- PESTAÑA 2: DOCENTE ---
with tabs[1]:
    if st.session_state['auth']:
        df = cargar_datos()
        if not df.empty:
            st.markdown("### 🎛️ Filtros de Resultados")
            
            # Fila 1: Filtros de Identificación
            f1, f2, f3 = st.columns(3)
            
            # Filtro Fecha
            fechas_disp = df['Fecha_dt'].unique()
            if len(fechas_disp) > 0:
                min_f, max_f = min(fechas_disp), max(fechas_disp)
                rango_fecha = f1.date_input("Rango de Fechas", [min_f, max_f])
            else:
                rango_fecha = [date.today(), date.today()]

            # Filtro Grupo
            grupos = ["Todos"] + sorted(df['Grupo'].unique().tolist())
            sel_grupo = f2.selectbox("Grupo:", grupos)
            
            # Filtro Estudiante (Reactivo)
            if sel_grupo != "Todos":
                ests = ["Todos"] + df[df['Grupo'] == sel_grupo]['Nombre'].unique().tolist()
            else:
                ests = ["Todos"] + df['Nombre'].unique().tolist()
            sel_est = f3.selectbox("Estudiante:", ests)

            # Fila 2: Filtros de Notas (Sliders independientes)
            st.markdown("---")
            st.markdown("#### 🎯 Filtrar por Desempeño")
            s1, s2, s3 = st.columns(3)
            min_tot = s1.slider("Global Mínimo (0-10)", 0.0, 10.0, 0.0, step=0.5)
            min_dx = s2.slider("Diagnóstico Mínimo (0-8)", 0.0, 8.0, 0.0, step=0.5)
            min_tx = s3.slider("Terapéutico Mínimo (0-2)", 0.0, 2.0, 0.0, step=0.5)

            # --- LÓGICA DE FILTRADO ---
            df_view = df.copy()
            
            # Aplicar Fechas
            if len(rango_fecha) == 2:
                df_view = df_view[
                    (df_view['Fecha_dt'] >= rango_fecha[0]) & 
                    (df_view['Fecha_dt'] <= rango_fecha[1])
                ]
            
            # Aplicar Grupo/Estudiante
            if sel_grupo != "Todos": df_view = df_view[df_view['Grupo'] == sel_grupo]
            if sel_est != "Todos": df_view = df_view[df_view['Nombre'] == sel_est]
            
            # Aplicar Notas
            df_view = df_view[
                (df_view['Puntaje_Total'] >= min_tot) &
                (df_view['Score_Diagnostico'] >= min_dx) &
                (df_view['Score_Terapeutico'] >= min_tx)
            ]

            # --- VISUALIZACIÓN ---
            st.divider()
            
            # Métricas
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Registros Filtrados", len(df_view))
            if not df_view.empty:
                m2.metric("Prom. Global", f"{df_view['Puntaje_Total'].mean():.1f}")
                m3.metric("Prom. Diagnóstico", f"{df_view['Score_Diagnostico'].mean():.1f}")
                m4.metric("Prom. Terapéutico", f"{df_view['Score_Terapeutico'].mean():.1f}")
            
            # Tabla
            st.subheader("📋 Planilla de Notas")
            st.dataframe(
                df_view[['Fecha_Registro', 'Grupo', 'Nombre', 'Caso_ID', 'Puntaje_Total', 'Score_Diagnostico', 'Score_Terapeutico', 'Sesgos']],
                use_container_width=True
            )
            
            # Gráficas
            g1, g2 = st.columns(2)
            with g1:
                st.caption("Correlación: Buen Diagnóstico vs Buen Tratamiento")
                st.scatter_chart(df_view, x='Score_Diagnostico', y='Score_Terapeutico', color='Grupo')
            
            with g2:
                st.caption("Evolución Temporal del Grupo")
                # Agrupar por fecha para ver tendencia
                if not df_view.empty:
                    trend = df_view.groupby('Fecha_Registro')['Puntaje_Total'].mean()
                    st.line_chart(trend)

        else:
            st.info("La base de datos está vacía. Esperando registros de estudiantes.")


