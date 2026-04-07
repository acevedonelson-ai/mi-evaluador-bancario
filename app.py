import streamlit as st
import requests
import pdfplumber
import pandas as pd
from fpdf import FPDF
import re

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Broker AI - Analista F22", layout="wide")

@st.cache_data(ttl=3600)
def get_uf():
    try: return requests.get("https://mindicador.cl/api/uf").json()['serie'][0]['valor']
    except: return 38000.0

uf_hoy = get_uf()

# --- MOTOR DE ANÁLISIS F22 ---
def analizar_f22(file):
    texto_completo = ""
    datos_extraidos = {"sueldos": 0, "honorarios": 0, "rut": "", "nombre": ""}
    
    with pdfplumber.open(file) as pdf:
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text()
            
    # Buscamos códigos específicos del F22
    # Código 1098: Sueldos 
    match_sueldos = re.search(r"1098\s+([\d.]+)", texto_completo)
    if match_sueldos:
        datos_extraidos["sueldos"] = float(match_sueldos.group(1).replace(".", ""))
        
    # Código 110: Honorarios 
    match_honor = re.search(r"110\s+([\d.]+)", texto_completo)
    if match_honor:
        datos_extraidos["honorarios"] = float(match_honor.group(1).replace(".", ""))
        
    # Identificación básica 
    match_rut = re.search(r"(\d{1,2}\.\d{3}\.\d{3}-[\dkK]|\d{7,8}-[\dkK])", texto_completo)
    if match_rut: datos_extraidos["rut"] = match_rut.group(1)
    
    return datos_extraidos

# --- INTERFAZ ---
st.markdown(f'<div style="background-color:#1E3A8A;color:white;padding:15px;border-radius:10px;text-align:center">UF HOY: ${uf_hoy:,.2f}</div>', unsafe_allow_html=True)
st.title("🛡️ Sistema de Evaluación Hipotecaria")

# SECCIÓN DE CARGA DE DOCUMENTOS
with st.sidebar:
    st.header("📂 Análisis de Documentos")
    f22_file = st.file_uploader("Subir Formulario 22 (F22)", type="pdf")
    
    analisis = None
    if f22_file:
        with st.spinner("Analizando F22..."):
            analisis = analizar_f22(f22_file)
            st.success("Análisis Completado")
            st.write(f"**RUT:** {analisis['rut']}")

# --- LÓGICA DE RENTA ---
st.header("💼 Perfil de Ingresos")
col1, col2 = st.columns(2)

with col1:
    st.subheader("Ingresos como Dependiente")
    # Si el análisis detectó sueldos (Código 1098), los pone automáticamente 
    sueldo_base_anual = analisis['sueldos'] if analisis else 0
    sueldo_mensual = st.number_input("Sueldo Mensual (Fijo)", value=int(sueldo_base_anual/12) if sueldo_base_anual > 0 else 0)
    
    # Variables con promedio de 3 meses (Castigo 30%)
    st.caption("Variables (Castigo 30%)")
    v_cols = st.columns(3)
    vm1 = v_cols[0].number_input("Mes 1", value=0, key="v1")
    vm2 = v_cols[1].number_input("Mes 2", value=0, key="v2")
    vm3 = v_cols[2].number_input("Mes 3", value=0, key="v3")
    validos = [v for v in [vm1, vm2, vm3] if v > 0]
    prom_var = (sum(validos)/len(validos) * 0.7) if len(validos) >= 3 else 0

with col2:
    st.subheader("Ingresos Independientes / Boletas")
    # Si detectó honorarios (Código 110) 
    honor_anual = analisis['honorarios'] if analisis else 0
    honor_mensual = st.number_input("Honorarios Brutos Mensuales", value=int(honor_anual/12) if honor_anual > 0 else 0)
    renta_indep = honor_mensual * 0.7 # Castigo 30% automático

renta_total_depurada = sueldo_mensual + prom_var + renta_indep

# --- ANÁLISIS DE DEUDA CMF ---
st.divider()
st.header("💳 Deuda CMF")
d_col1, d_col2, d_col3 = st.columns(3)

with d_col1:
    m_cons = st.number_input("Monto Deuda Consumo ($)", value=0)
    c_cons = st.number_input("Cuota Real Consumo", value=int(m_cons * 0.05))

with d_col2:
    m_tc = st.number_input("Monto Deuda TC ($)", value=0)
    c_tc = st.number_input("Pago Mensual TC", value=int(m_tc * 0.05))

with d_col3:
    m_hip = st.number_input("Monto Deuda Hipotecaria ($)", value=0)
    c_hip = st.number_input("Dividendo Real", value=int(m_hip * 0.015))

total_deuda = c_cons + c_tc + c_hip

# --- SIMULACIÓN Y RESULTADOS ---
st.divider()
s1, s2 = st.columns(2)
m_prop = s1.number_input("Valor Propiedad (UF)", value=3000)
m_cred = s2.number_input("Crédito Solicitado (UF)", value=2400)

div_uf = (m_cred * 0.005) # Estimación rápida tasa + seguros
div_clp = div_uf * uf_hoy

rci = (div_clp / renta_total_depurada * 100) if renta_total_depurada > 0 else 0
cft = ((div_clp + total_deuda) / renta_total_depurada * 100) if renta_total_depurada > 0 else 0

st.header("📋 Resumen Final")
r_col1, r_col2, r_col3 = st.columns(3)
r_col1.metric("Renta Depurada", f"${renta_total_depurada:,.0f}")
r_col2.metric("Carga Hipotecaria (RCI)", f"{rci:.1f}%")
r_col3.metric("Carga Total (CFT)", f"{cft:.1f}%")

if rci <= 25 and cft <= 45:
    st.success("✅ CALIFICA: Perfil óptimo para Bancos Tradicionales.")
else:
    st.error("❌ NO CALIFICA: Excede los límites de carga financiera.")
