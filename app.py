import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
import os

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="ACCR-T Dashboard", page_icon="🫀", layout="wide")
DB_FILE = 'registro_academico.csv'

# --- ESTILOS VISUALES ---
st.markdown("""
<style>
    .big-font {font-size:20px !important; font-weight: bold;}
    .stButton>button {width: 100%;}
</style>
""", unsafe_allow_html=True)

# --- GESTIÓN DE DATOS ---
def cargar_datos():
    if not os.path.exists(DB_FILE):
        cols = [
            # DATOS DE AUDITORÍA (Lo que pediste)
            "Fecha_Carga", "Hora_Carga", 
            
            # DATOS DEL ESTUDIANTE
            "ID_Estudiante", "Grupo_Rotacion",
            
            # DATOS DEL CASO
            "Caso_ID", "Nivel", "Dx_Real",
            
            # TIEMPOS DEL EJERCICIO (Manuales)
            "Hora_Inicio_Ej", "Hora_Fin_Ej", "Duracion_Min",
            
            # NOTAS
            "Puntaje_Total", "Score_Recoleccion", "Score_Sintesis", 
            "Score_Hipotesis", "Score_Interp", "Score_Terapeutica",
            
            # DETALLES CUALITATIVOS
            "Illness_Script", "Hipotesis_Alumno", "Manejo_Final", 
            "Sesgos_Detectados", "JSON_Raw"
        ]
        return pd.DataFrame(columns=cols)
    return pd.read_csv(DB_FILE)

def guardar_registro(data_dict):
    df = cargar_datos()
    new_row = pd.DataFrame([data_dict])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(DB_FILE, index=False)

# --- BARRA LATERAL ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/heart-monitor.png", width=60)
    st.title("ACCR-T | Registro")
    st.markdown("---")
    st.info("Sistema de Trazabilidad Académica")

# --- INTERFAZ PRINCIPAL ---
st.title("🫀 ACCR-T: Sistema de Registro Clínico")

tab1, tab2 = st.tabs(["📥 Cargar Caso", "📊 Tablero Docente"])

# PESTAÑA 1: CARGAR
with tab1:
    col_input, col_viz = st.columns([1, 1])
    
    with col_input:
        st.subheader("1. Pegar Código JSON")
        json_input = st.text_area("Pega aquí el código que te dio el Dr. CardioSim:", height=300)
        
        st.subheader("2. Validar Tiempos")
        # El estudiante confirma sus tiempos manualmente aquí
        c1, c2 = st.columns(2)
        h_inicio = c1.time_input("Hora Inicio Ejercicio:")
        h_fin = c2.time_input("Hora Fin Ejercicio:")
        
        # Calcular duración
        t1 = datetime.combine(datetime.today(), h_inicio)
        t2 = datetime.combine(datetime.today(), h_fin)
        if t2 < t1: t2 += timedelta(days=1)
        duracion = int((t2 - t1).total_seconds() / 60)
        
        if st.button("🚀 REGISTRAR CASO", type="primary"):
            if not json_input:
                st.error("⚠️ El campo JSON está vacío.")
            else:
                try:
                    d = json.loads(json_input)
                    
                    # Extracción segura de datos (Prompt V16/17)
                    meta = d.get("metadata", {})
                    cog = d.get("traza_cognitiva", {})
                    cri = d.get("evaluacion_cri_ht_s", {})
                    sesgos = d.get("sesgos_cognitivos", {})
                    
                    # TIMESTAMP DEL SISTEMA (Tu requerimiento)
                    ahora = datetime.now()
                    
                    registro = {
                        # AUDITORÍA AUTOMÁTICA
                        "Fecha_Carga": ahora.strftime("%Y-%m-%d"),
                        "Hora_Carga": ahora.strftime("%H:%M:%S"), # Hora exacta del clic
                        
                        # DATOS
                        "ID_Estudiante": meta.get("estudiante_id", "Anon"),
                        "Grupo_Rotacion": meta.get("grupo_rotacion", "A"),
                        "Caso_ID": meta.get("caso_id", "N/A"),
                        "Nivel": meta.get("nivel", "N/A"),
                        "Dx_Real": meta.get("diagnostico_real", "N/A"),
                        
                        # TIEMPOS
                        "Hora_Inicio_Ej": h_inicio.strftime("%H:%M"),
                        "Hora_Fin_Ej": h_fin.strftime("%H:%M"),
                        "Duracion_Min": duracion,
                        
                        # NOTAS
                        "Puntaje_Total": cri.get("total_sobre_10", 0),
                        "Score_Recoleccion": cri.get("recoleccion", "0/2"),
                        "Score_Sintesis": cri.get("sintesis", "0/2"),
                        "Score_Hipotesis": cri.get("hipotesis", "0/2"),
                        "Score_Interp": cri.get("interpretacion", "0/2"),
                        "Score_Terapeutica": cri.get("terapeutica", "0/2"),
                        
                        # CUALITATIVO
                        "Illness_Script": cog.get("illness_script", ""),
                        "Hipotesis_Alumno": str(cog.get("hipotesis", "")),
                        "Manejo_Final": cog.get("manejo_final", ""),
                        "Sesgos_Detectados": str(sesgos.get("detectados", "")),
                        "JSON_Raw": json_input
                    }
                    
                    guardar_registro(registro)
                    st.success(f"✅ Caso guardado a las {registro['Hora_Carga']}")
                    st.balloons()
                    
                except json.JSONDecodeError:
                    st.error("Error: El texto no es un JSON válido.")
                except Exception as e:
                    st.error(f"Error interno: {e}")

    with col_viz:
        if json_input:
            try:
                data = json.loads(json_input)
                st.info("Vista Previa:")
                st.json(data.get("evaluacion_cri_ht_s", {}))
            except: pass

# PESTAÑA 2: DASHBOARD
with tab2:
    df = cargar_datos()
    if not df.empty:
        st.header("📊 Trazabilidad Docente")
        
        # Filtros
        col_f1, col_f2 = st.columns(2)
        grupo = col_f1.selectbox("Filtrar Grupo:", ["Todos"] + list(df["Grupo_Rotacion"].unique()))
        
        df_view = df if grupo == "Todos" else df[df["Grupo_Rotacion"] == grupo]
        
        # Tabla
        st.dataframe(
            df_view[[
                "Fecha_Carga", "Hora_Carga", # Aquí verás cuándo lo subieron
                "ID_Estudiante", "Grupo_Rotacion", 
                "Caso_ID", "Puntaje_Total", "Duracion_Min"
            ]].sort_values(by="Fecha_Carga", ascending=False),
            use_container_width=True
        )
        
        # Botón Descarga
        st.download_button("📥 Descargar Excel Completo", df.to_csv(index=False), "registro_accr_t.csv")
    else:
        st.warning("No hay datos.")