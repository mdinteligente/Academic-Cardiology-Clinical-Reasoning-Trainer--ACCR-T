import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
import os

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="ACCR-T Portal", page_icon="🔒", layout="wide")
DB_FILE = 'registro_completo.csv'

# --- 2. GESTIÓN DE ESTADO (SESIÓN) ---
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

def check_login(user, password):
    if user == "razonadx" and password == "javier26":
        st.session_state['authenticated'] = True
        st.success("✅ Acceso Docente Autorizado")
    else:
        st.error("❌ Credenciales incorrectas")

def logout():
    st.session_state['authenticated'] = False

# --- 3. FUNCIONES DE BASE DE DATOS ---
def cargar_datos():
    if not os.path.exists(DB_FILE):
        cols = [
            "Fecha_Registro", "Estudiante", "Caso_ID", "Nivel", "Dx_Real", "Puntaje_Total",
            "Hora_Inicio", "Hora_Fin", "Duracion_Minutos",
            "Illness_Script", "Hipotesis", "Manejo",
            "Score_Recoleccion", "Score_Sintesis", "Score_Hipotesis", "Score_Interp", "Score_Manejo",
            "Sesgos", "JSON_Raw"
        ]
        return pd.DataFrame(columns=cols)
    return pd.read_csv(DB_FILE)

def guardar_registro(data_dict):
    df = cargar_datos()
    new_row = pd.DataFrame([data_dict])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(DB_FILE, index=False)

# --- 4. BARRA LATERAL (IDENTIFICACIÓN Y LOGIN) ---
with st.sidebar:
    st.image("https://img.icons8.com/color/96/heart-with-pulse.png", width=50)
    st.title("ACCR-T Portal")
    
    # --- ZONA DE ESTUDIANTE (Siempre visible) ---
    st.markdown("### 👨‍🎓 Zona Estudiante")
    student_id = st.text_input("Nombre / Código:", key="student_id", placeholder="Ej. Juan Pérez - 102030")
    
    st.markdown("---")
    
    # --- ZONA DOCENTE (Login) ---
    st.markdown("### 👨‍🏫 Zona Docente")
    
    if st.session_state['authenticated']:
        st.success("Modo Administrador Activo")
        if st.button("Cerrar Sesión"):
            logout()
            st.rerun()
    else:
        with st.expander("Acceso Privado"):
            user_input = st.text_input("Usuario")
            pass_input = st.text_input("Contraseña", type="password")
            if st.button("Ingresar"):
                check_login(user_input, pass_input)
                st.rerun()

# --- 5. INTERFAZ PRINCIPAL ---

# Si el docente está logueado, ve dos pestañas. Si no, solo ve una.
tabs_list = ["📥 Carga de Archivos (Estudiantes)"]
if st.session_state['authenticated']:
    tabs_list.append("📊 Dashboard Docente (Privado)")

tabs = st.tabs(tabs_list)

# --- PESTAÑA 1: ESTUDIANTES (PÚBLICA) ---
with tabs[0]:
    st.header("Registro de Actividad Clínica")
    st.info("Instrucciones: Al finalizar el caso en el GPT, copia el bloque de código JSON y pégalo abajo.")

    col_izq, col_der = st.columns([1, 1])
    
    with col_izq:
        st.subheader("1. Cálculo de Tiempos")
        ahora = datetime.now()
        h_inicio = st.time_input("Hora de Inicio:", value=(ahora - timedelta(minutes=20)).time())
        h_fin = st.time_input("Hora de Finalización:", value=ahora.time())
        
        # Calcular duración
        t_inicio = datetime.combine(datetime.today(), h_inicio)
        t_fin = datetime.combine(datetime.today(), h_fin)
        if t_fin < t_inicio: t_fin += timedelta(days=1) # Cambio de día
        duracion = t_fin - t_inicio
        minutos_totales = int(duracion.total_seconds() / 60)
        
        st.metric("Tiempo Invertido", f"{minutos_totales} min")

    with col_der:
        st.subheader("2. Carga de Datos")
        json_input = st.text_area("Pega tu JSON aquí:", height=200)
        
        if st.button("Enviar Registro", type="primary"):
            if not student_id:
                st.error("⚠️ Falta tu Nombre/Código.")
            elif not json_input:
                st.error("⚠️ Falta el código JSON.")
            else:
                try:
                    d = json.loads(json_input)
                    # Extracción segura de datos
                    registro = {
                        "Fecha_Registro": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Estudiante": student_id,
                        "Caso_ID": d.get("metadata", {}).get("caso_id", "N/A"),
                        "Nivel": d.get("metadata", {}).get("nivel", "N/A"),
                        "Dx_Real": d.get("metadata", {}).get("diagnostico_real", "N/A"),
                        "Puntaje_Total": d.get("evaluacion_cri_ht_s", {}).get("total_sobre_10", 0),
                        "Hora_Inicio": h_inicio.strftime("%H:%M"),
                        "Hora_Fin": h_fin.strftime("%H:%M"),
                        "Duracion_Minutos": minutos_totales,
                        # Datos Cognitivos
                        "Illness_Script": d.get("traza_cognitiva", {}).get("illness_script_estudiante", ""),
                        "Hipotesis": str(d.get("traza_cognitiva", {}).get("hipotesis_planteadas", "")),
                        "Manejo": d.get("traza_cognitiva", {}).get("tratamiento_propuesto", ""),
                        # Scores
                        "Score_Recoleccion": d.get("evaluacion_cri_ht_s", {}).get("recoleccion_datos", {}).get("puntaje", 0),
                        "Score_Sintesis": d.get("evaluacion_cri_ht_s", {}).get("representacion_problema", {}).get("puntaje", 0),
                        "Score_Hipotesis": d.get("evaluacion_cri_ht_s", {}).get("generacion_hipotesis", {}).get("puntaje", 0),
                        "Score_Interp": d.get("evaluacion_cri_ht_s", {}).get("interpretacion_datos", {}).get("puntaje", 0),
                        "Score_Manejo": d.get("evaluacion_cri_ht_s", {}).get("toma_decisiones", {}).get("puntaje", 0),
                        "Sesgos": str(d.get("sesgos_cognitivos", {}).get("detectados", "")),
                        "JSON_Raw": json_input
                    }
                    guardar_registro(registro)
                    st.success("✅ ¡Registro Exitoso! Tus datos han sido enviados al docente.")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error en el formato JSON: {e}")

# --- PESTAÑA 2: DOCENTE (PRIVADA) ---
if st.session_state['authenticated']:
    with tabs[1]:
        st.markdown("## 📊 Panel de Control Docente")
        st.markdown(f"**Usuario:** {st.session_state.get('user', 'razonadx')} | **Estado:** Conectado")
        
        df = cargar_datos()
        
        if not df.empty:
            # Métricas Globales
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Casos Resueltos", len(df))
            promedio_nota = pd.to_numeric(df['Puntaje_Total'], errors='coerce').mean()
            m2.metric("Promedio Curso (CRI-HT-S)", f"{promedio_nota:.1f}/10")
            promedio_tiempo = pd.to_numeric(df['Duracion_Minutos'], errors='coerce').mean()
            m3.metric("Tiempo Promedio/Caso", f"{promedio_tiempo:.0f} min")
            
            st.divider()
            
            # Tabla Maestra con Filtros
            st.subheader("Base de Datos Completa")
            
            # Filtros dinámicos
            filtro_estudiante = st.multiselect("Filtrar por Estudiante:", options=df['Estudiante'].unique())
            filtro_nivel = st.multiselect("Filtrar por Nivel:", options=df['Nivel'].unique())
            
            df_view = df.copy()
            if filtro_estudiante:
                df_view = df_view[df_view['Estudiante'].isin(filtro_estudiante)]
            if filtro_nivel:
                df_view = df_view[df_view['Nivel'].isin(filtro_nivel)]
                
            st.dataframe(
                df_view[['Fecha_Registro', 'Estudiante', 'Caso_ID', 'Dx_Real', 'Puntaje_Total', 'Duracion_Minutos', 'Sesgos']],
                use_container_width=True
            )
            
            # Descarga de Datos
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Descargar Reporte Completo (CSV)",
                csv,
                "reporte_clinico.csv",
                "text/csv",
                key='download-csv'
            )
            
            st.divider()
            
            # Análisis Gráfico
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("📈 Rendimiento vs Tiempo")
                st.scatter_chart(df, x='Duracion_Minutos', y='Puntaje_Total', color='Nivel')
            
            with c2:
                st.subheader("🧠 Sesgos Frecuentes")
                # Nube de palabras simple de sesgos
                st.write(df['Sesgos'].value_counts())
                
        else:
            st.info("Aún no hay datos cargados por los estudiantes.")
