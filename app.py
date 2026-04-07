import streamlit as st
import requests
import pandas as pd
from fpdf import FPDF
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="Sistema de Análisis Hipotecario", layout="wide")

# CSS para mejorar la estética y la visibilidad de la UF
st.markdown("""
    <style>
    .uf-card {
        background-color: #1E3A8A;
        color: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 20px;
    }
    .main { background-color: #F3F4F6; }
    </style>
    """, unsafe_allow_html=True)

# --- BASE DE DATOS (SQLite) ---
def init_db():
    conn = sqlite3.connect('evaluaciones.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS evaluaciones 
                 (id INTEGER PRIMARY KEY, fecha TEXT, nombre TEXT, rut TEXT, renta REAL, rci REAL, cft REAL)''')
    conn.commit()
    conn.close()

init_db()

# --- FUNCIONES CORE ---
@st.cache_data(ttl=3600)
def get_uf():
    try:
        return requests.get("https://mindicador.cl/api/uf").json()['serie'][0]['valor']
    except: return 38000.0

uf = get_uf()

def generar_pdf(datos):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "Informe de Evaluación Hipotecaria", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    for k, v in datos.items():
        pdf.cell(200, 10, f"{k}: {v}", ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- SIDEBAR (UF Y DATOS PERSONALES) ---
with st.sidebar:
    st.markdown(f'<div class="uf-card"><h3>UF HOY</h3><h2>${uf:,.2f}</h2></div>', unsafe_allow_html=True)
    st.header("👤 Datos del Cliente")
    nombre = st.text_input("Nombre Completo")
    rut = st.text_input("RUT")
    email = st.text_input("Email")

# --- CUERPO PRINCIPAL ---
st.title("🛡️ Sistema de Análisis de Riesgo Hipotecario")

def calcular_renta(label):
    with st.container(border=True):
        st.subheader(f"💼 Ingresos {label}")
        tipo = st.selectbox("Tipo de Perfil", ["Dependiente", "Independiente"], key=f"t_{label}")
        
        col1, col2 = st.columns(2)
        with col1:
            fijo = st.number_input("Renta Fija / Base DAI", min_value=0, key=f"f_{label}")
            variable = st.number_input("Promedio Variables (Bonos)", min_value=0, key=f"v_{label}")
            no_imp = st.number_input("No Imponibles", min_value=0, key=f"n_{label}")
        with col2:
            boletas = st.number_input("Promedio Boletas (6m)", min_value=0, key=f"b_{label}")
            arriendos = st.number_input("Renta Arriendos", min_value=0, key=f"a_{label}")
            if tipo == "Independiente":
                st.file_uploader("Cargar DAI (PDF)", type="pdf", key=f"pdf_{label}")
        
        # Depuración
        total = fijo + (variable * 0.8) + no_imp + (boletas * 0.7) + (arriendos * 0.8)
        return total

c_t1, c_t2 = st.columns(2)
with c_t1: r1 = calcular_renta("Titular")
with c_t2: 
    usa_cod = st.checkbox("¿Incluir Codeudor?")
    r2 = calcular_renta("Codeudor") if usa_cod else 0

renta_depurada = r1 + r2

# --- DEUDA CMF ---
st.divider()
st.header("💳 Análisis de Deuda CMF")
col_d1, col_d2 = st.columns(2)
with col_d1:
    monto_cons = st.number_input("Monto Insoluto Consumo/TC", value=0)
    cuota_cons = st.number_input("Cuota Mensual Consumo (Real)", value=int(monto_cons * 0.05))
with col_d2:
    monto_hipo = st.number_input("Monto Insoluto Otros Hipotecarios", value=0)
    cuota_hipo = st.number_input("Cuota Mensual Otros Hipot. (Real)", value=int(monto_hipo * 0.015))

# --- SIMULACIÓN ---
st.divider()
st.header("🏠 Simulación de Crédito")
s1, s2, s3 = st.columns(3)
v_prop = s1.number_input("Valor Propiedad (UF)", value=3000)
m_cred = s2.number_input("Crédito Solicitado (UF)", value=2400)
plazo = s3.slider("Plazo (Años)", 5, 30, 20)

# Cálculo Dividendo (Tasa 5% + Seguros)
tasa = 0.05 / 12
n = plazo * 12
div_uf = m_cred * (tasa * (1 + tasa)**n) / ((1 + tasa)**n - 1)
div_clp = (div_uf * uf) * 1.15

# --- RESUMEN Y RECOMENDACIONES ---
st.divider()
rci = (div_clp / renta_depurada * 100) if renta_depurada > 0 else 0
cft = ((div_clp + cuota_cons + cuota_hipo) / renta_depurada * 100) if renta_depurada > 0 else 0

st.header("📋 Resumen Ejecutivo")
res1, res2, res3 = st.columns(3)
res1.metric("Renta Depurada Total", f"${renta_depurada:,.0f}")
res2.metric("RCI (Max 25-30%)", f"{rci:.1f}%")
res3.metric("CFT (Max 45-50%)", f"{cft:.1f}%")

# Lógica de Recomendación
recomendacion = ""
bancos = ""
if rci <= 25 and cft <= 45:
    recomendacion = "SUJETO APROBADO"
    bancos = "Santander, Chile, BCI, Scotiabank."
    st.success(f"✅ {recomendacion}: Califica en {bancos}")
elif cft <= 50:
    recomendacion = "APROBACIÓN CON RESTRICCIÓN"
    bancos = "Banco Estado, Coopeuch, Consorcio."
    st.warning(f"⚠️ {recomendacion}: Califica en {bancos}")
else:
    recomendacion = "RECHAZADO"
    bancos = "Ninguno (Sobreendeudamiento)"
    st.error(f"❌ {recomendacion}: Excede carga financiera máxima.")

# --- GUARDAR Y PDF ---
if st.button("💾 Guardar Evaluación y Generar Reporte"):
    # Guardar en BD
    conn = sqlite3.connect('evaluaciones.db')
    c = conn.cursor()
    c.execute("INSERT INTO evaluaciones (fecha, nombre, rut, renta, rci, cft) VALUES (?,?,?,?,?,?)",
              (datetime.now().strftime("%Y-%m-%d"), nombre, rut, renta_depurada, rci, cft))
    conn.commit()
    conn.close()
    
    # PDF
    datos_reporte = {
        "Fecha": datetime.now().strftime("%d/%m/%Y"),
        "Cliente": nombre,
        "RUT": rut,
        "Renta Depurada": f"${renta_depurada:,.0f}",
        "RCI": f"{rci:.1f}%",
        "CFT": f"{cft:.1f}%",
        "Dividendo Est.": f"${div_clp:,.0f}",
        "Resultado": recomendacion,
        "Bancos Sugeridos": bancos
    }
    pdf_bytes = generar_pdf(datos_reporte)
    st.download_button("📥 Descargar PDF de Evaluación", data=pdf_bytes, file_name=f"Evaluacion_{rut}.pdf", mime="application/pdf")
    st.success("Evaluación guardada exitosamente en la base de datos.")
