import streamlit as st
import pandas as pd
from datetime import datetime
from PIL import Image
import os

# Cargar base de datos directamente (sin cache) en cada ejecución
def cargar_datos():
    df = pd.read_excel("verificacion_feria_prueba.xlsx")
    df['DNI'] = df['DNI'].astype(str)
    df['Nombre'] = df['Nombre'].astype(str)
    return df

def guardar_datos(df):
    df.to_excel("verificacion_feria_prueba.xlsx", index=False)

# Inicializar variables de sesión
if "confirmaciones" not in st.session_state:
    st.session_state.confirmaciones = {}

st.set_page_config(page_title="Verificación Feria", layout="wide")
df = cargar_datos()

# Estilo visual
st.markdown("""
    <style>
    .stButton>button {
        height: 3em;
        width: 100%;
        font-size: 16px;
        border-radius: 10px;
        border: 2px solid #5cb85c;
        background-color: #eaffea;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #d0f5d8;
    }
    .info-box {
        background-color: #ffffff;
        padding: 1.5em;
        border-radius: 15px;
        border: 1px solid #e0e0e0;
        margin-bottom: 2em;
        box-shadow: 2px 2px 8px rgba(0,0,0,0.05);
    }
    .info-box h4 {
        font-size: 22px;
        margin-bottom: 10px;
    }
    .info-box p {
        font-size: 16px;
        margin: 5px 0;
    }
    </style>
""", unsafe_allow_html=True)

st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/Check_green_icon.svg/1024px-Check_green_icon.svg.png", width=50)
st.markdown("<h1 style='font-size: 36px; margin-bottom: 20px;'>Verificación de Comerciantes - Feria</h1>", unsafe_allow_html=True)

busqueda = st.text_input("🔎 Buscar por DNI o Nombre:")

if busqueda:
    resultado = df[df['DNI'].str.contains(busqueda) | df['Nombre'].str.contains(busqueda, case=False)]

    if not resultado.empty:
        for idx, row in resultado.iterrows():
            with st.container():
                st.markdown(f"""
                    <div class=\"info-box\">
                    <h4>🧍‍♂️ <b>{row['Nombre']}</b> - 🏷️ Puesto <b>{row['Puesto']}</b></h4>
                    <p>📄 <b>DNI:</b> {row['DNI']}</p>
                    <p>🏪 <b>Rubro:</b> {row['Rubro']}</p>
                    <p>💵 <b>Pago:</b> {'✅' if row['Pago'] == 'Sí' else '❌ No'}</p>
                    </div>
                """, unsafe_allow_html=True)

                col1, col2, col3 = st.columns(3)
                for i, col in enumerate([col1, col2, col3], start=1):
                    turno_col = f'Turno {i}'
                    key_check = f"confirmar-{idx}-{i}"
                    key_button = f"verificar-{idx}-{i}"

                    if row[turno_col] == 'Sí':
                        with col:
                            st.success(f"{turno_col}: Verificado")
                    else:
                        with col:
                            confirmado = st.checkbox(f"¿Confirmar {turno_col}?", key=key_check)
                            if confirmado:
                                if st.button(f"✅ Verificar {turno_col}", key=key_button):
                                    df.at[idx, turno_col] = 'Sí'
                                    guardar_datos(df)
                                    st.success(f"{turno_col} marcado como verificado para {row['Nombre']}")
                                    st.session_state.confirmaciones = {}
                                    st.stop()
    else:
        st.warning("🚫 No se encontraron coincidencias.")
else:
    st.info("Ingresa un DNI o nombre para buscar al comerciante.")
