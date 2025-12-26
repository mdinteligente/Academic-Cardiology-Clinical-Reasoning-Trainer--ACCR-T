import streamlit as st
import pandas as pd
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN Y BASES DE CONOCIMIENTO ---
st.set_page_config(page_title="ACCR-T Portal", page_icon="🫀", layout="wide")

# BASE DE DATOS DE ESTUDIANTES (Código: Nombre)
# En el futuro, esto podría venir de otro Excel.
DB_ESTUDIANTES = {
    "1001": "Juan Pérez",
    "1002": "Maria Gomez",
    "1003": "Carlos Ruiz",
    "MED-2025": "Estudiante Prueba"
}

# DICCIONARIO DE SESGOS (Educativo)
DICT_SESGOS = {
    "Cierre Prematuro": "Aceptar un diagnóstico inicial sin buscar evidencia contraria.",
    "Anclaje": "Aferrarse a un dato inicial (ej. troponina normal) ignorando la clínica.",
    "Disponibilidad": "Diagnosticar lo que se ha visto recientemente o es más memorable.",
    "Confirmación": "Buscar solo datos que apoyen tu idea y descartar los que la niegan.",
    "Representatividad": "Juzgar por prototipos clásicos ignorando presentaciones atípicas."
}

# --- 2. CONEXIÓN A GOOGLE SHEETS ---
def conectar_google_sheet():
    # Usamos los secretos cargados en Streamlit Cloud
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    # Abre la hoja por nombre (Asegúrate de haberla creado y compartido en Drive)
    sheet = client.open("registro_accr_t").sheet1 
    return sheet

def cargar_datos():
    try:
        sheet = conectar_google_sheet()
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error conectando a Google Sheets: {e}")
        return pd.DataFrame()

def guardar_registro(data_dict):
    try:
        sheet = conectar_google_sheet()
        # Convertir diccionario a lista de valores respetando el orden de columnas si fuera necesario
        # Para simplicidad, append_row usa una lista.
        valores = list(data_dict.values())
        sheet.append_row(valores)
        return True
    except Exception as e:
        st.error(f"Error guardando en la nube: {e}")
        return False

# --- 3. AUTENTICACIÓN DOCENTE ---
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

def check_login(user, password):
    if user == st.secrets["admin_user"] and password == st.secrets["admin_password"]:
        st.session_state['authenticated'] = True
    else:
        st.error("❌ Credenciales incorrectas")

# --- 4. INTERFAZ ---
with st.sidebar:
    st.title("🫀 ACCR-T Portal")
    st.markdown("---")
    
    # LOGIN DOCENTE
    if not st.session_state['authenticated']:
        with st.expander("🔐 Acceso Docente"):
            u = st.text_input("Usuario")
            p = st.text_input("Clave", type="password")
            if st.button("Entrar"):
                check_login(u, p)
                st.rerun()
    else:
        st.success(f"Docente: {st.secrets['admin_user']}")
        if st.button("Cerrar Sesión"):
            st.session_state['authenticated'] = False
            st.rerun()

# PESTAÑAS
tabs = st.tabs(["👨‍🎓 Zona Estudiante", "👨‍🏫 Tablero de Control (Docente)"])

# --- ZONA ESTUDIANTE ---
with tabs[0]:
    st.header("Registro de Simulación Clínica")
    st.markdown("Ingrese su código para desbloquear el formulario.")
    
    col_auth, col_form = st.columns([1, 2])
    
    with col_auth:
        codigo_input = st.text_input("🆔 Tu Código Estudiantil:", placeholder="Ej. 1001")
        nombre_estudiante = DB_ESTUDIANTES.get(codigo_input)
        
        if codigo_input and not nombre_estudiante:
            st.error("⚠️ Código no reconocido. Verifique.")
        elif nombre_estudiante:
            st.success(f"Bienvenido/a: **{nombre_estudiante}**")
    
    # Solo mostrar formulario si el estudiante es válido
    if nombre_estudiante:
        with col_form:
            st.info("Pega aquí el código JSON generado por el GPT al final del caso.")
            json_input = st.text_area("Código JSON:", height=200)
            
            # Tiempos Flexibles (Texto libre con validación básica)
            c1, c2, c3 = st.columns(3)
            fecha_manual = c1.date_input("Fecha Realización", datetime.today())
            hora_inicio = c2.text_input("Hora Inicio (Militar HH:MM)", placeholder="14:00")
            hora_fin = c3.text_input("Hora Final (Militar HH:MM)", placeholder="14:45")
            
            if st.button("🚀 Enviar Registro a la Nube", type="primary"):
                if not json_input:
                    st.error("Falta el JSON.")
                elif not hora_inicio or not hora_fin:
                    st.error("Faltan los tiempos.")
                else:
                    try:
                        # Parsear JSON
                        d = json.loads(json_input)
                        
                        # Cálculo de tiempo (rudimentario para flexibilidad)
                        try:
                            fmt = "%H:%M"
                            t1 = datetime.strptime(hora_inicio, fmt)
                            t2 = datetime.strptime(hora_fin, fmt)
                            duracion = (t2 - t1).seconds // 60
                            if duracion < 0: duracion += 1440 # Cambio de día
                        except:
                            duracion = 0 # Error de formato
                            st.warning("Formato de hora no válido, se registró tiempo 0.")

                        # Estructura Plana para Google Sheets
                        registro = {
                            "Fecha": str(fecha_manual),
                            "Codigo": codigo_input,
                            "Nombre": nombre_estudiante,
                            "Caso_ID": d.get("metadata", {}).get("caso_id", "N/A"),
                            "Nivel": d.get("metadata", {}).get("nivel", "N/A"),
                            "Dx_Real": d.get("metadata", {}).get("diagnostico_real", "N/A"),
                            "Puntaje_Total": d.get("evaluacion_cri_ht_s", {}).get("total_sobre_10", 0),
                            # Tiempos
                            "H_Inicio": hora_inicio,
                            "H_Fin": hora_fin,
                            "Minutos": duracion,
                            # Dominios CRI-HT-S
                            "CRI_Recoleccion": d.get("evaluacion_cri_ht_s", {}).get("recoleccion_datos", {}).get("puntaje", 0),
                            "CRI_Sintesis": d.get("evaluacion_cri_ht_s", {}).get("representacion_problema", {}).get("puntaje", 0),
                            "CRI_Hipotesis": d.get("evaluacion_cri_ht_s", {}).get("generacion_hipotesis", {}).get("puntaje", 0),
                            "CRI_Interpretacion": d.get("evaluacion_cri_ht_s", {}).get("interpretacion_datos", {}).get("puntaje", 0),
                            # Guía OMS (Manejo)
                            "OMS_Manejo": d.get("evaluacion_cri_ht_s", {}).get("toma_decisiones", {}).get("puntaje", 0),
                            # Sesgos
                            "Sesgos": ", ".join(d.get("sesgos_cognitivos", {}).get("detectados", [])),
                            "Illness_Script": d.get("traza_cognitiva", {}).get("illness_script_estudiante", "")
                        }
                        
                        exito = guardar_registro(registro)
                        if exito:
                            st.success(f"✅ Registro guardado en Google Drive. Duración: {duracion} min.")
                            st.balloons()
                            
                    except json.JSONDecodeError:
                        st.error("El texto no es un JSON válido.")

# --- ZONA DOCENTE ---
with tabs[1]:
    if st.session_state['authenticated']:
        st.markdown("## 📊 Tablero de Control Académico")
        
        df = cargar_datos()
        
        if not df.empty:
            # --- FILTROS DE PERSONALIZACIÓN ---
            st.sidebar.markdown("### 🔍 Filtros Docente")
            filtro_est = st.sidebar.multiselect("Estudiante:", options=df['Nombre'].unique())
            filtro_caso = st.sidebar.multiselect("Caso ID:", options=df['Caso_ID'].unique())
            
            df_view = df.copy()
            if filtro_est: df_view = df_view[df_view['Nombre'].isin(filtro_est)]
            if filtro_caso: df_view = df_view[df_view['Caso_ID'].isin(filtro_caso)]

            # --- KPI ---
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Casos Evaluados", len(df_view))
            
            # Promedios seguros
            try:
                avg_score = df_view['Puntaje_Total'].mean()
                avg_oms = df_view['OMS_Manejo'].mean()
                k2.metric("Promedio Global", f"{avg_score:.1f}/10")
                k3.metric("Adherencia OMS (Manejo)", f"{avg_oms:.1f}/2")
            except:
                pass

            st.divider()

            # --- ANÁLISIS POR DOMINIOS (CRI-HT-S) ---
            st.subheader("📡 Radar de Competencias (CRI-HT-S)")
            dominios = ['CRI_Recoleccion', 'CRI_Sintesis', 'CRI_Hipotesis', 'CRI_Interpretacion', 'OMS_Manejo']
            try:
                # Promedio por dominio para los datos filtrados
                radar_data = df_view[dominios].mean().reset_index()
                radar_data.columns = ['Dominio', 'Puntaje Promedio (0-2)']
                st.bar_chart(radar_data.set_index('Dominio'))
            except:
                st.info("Faltan datos numéricos para graficar.")

            st.divider()

            # --- ANÁLISIS DE SESGOS COGNITIVOS ---
            c_bias, c_dict = st.columns([2, 1])
            with c_bias:
                st.subheader("🧠 Sesgos Detectados")
                if 'Sesgos' in df_view.columns:
                    # Contar frecuencia de sesgos
                    all_biases = []
                    for s in df_view['Sesgos'].astype(str):
                        all_biases.extend([b.strip() for b in s.split(',') if b.strip()])
                    
                    if all_biases:
                        bias_counts = pd.Series(all_biases).value_counts()
                        st.bar_chart(bias_counts)
                    else:
                        st.write("No se han detectado sesgos en la selección actual.")

            with c_dict:
                with st.expander("📚 Diccionario de Sesgos"):
                    for k, v in DICT_SESGOS.items():
                        st.markdown(f"**{k}:** {v}")

            st.divider()

            # --- TABLA DETALLADA ---
            st.subheader("📋 Registro Detallado")
            st.dataframe(df_view, use_container_width=True)
            
        else:
            st.warning("La base de datos en Google Sheets está vacía o no se pudo conectar.")
    else:
        st.info("🔒 Inicie sesión en la barra lateral para ver los datos.")


