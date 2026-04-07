import streamlit as st
import requests
import PyPDF2
import pandas as pd

# --- CONFIGURACIÓN ESTÉTICA ---
st.set_page_config(page_title="Broker Digital Pro", layout="wide")
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def get_uf():
    try:
        return requests.get("https://mindicador.cl/api/uf").json()['serie'][0]['valor']
    except: return 38000.0

uf = get_uf()

# --- LÓGICA DE CÁLCULO DE RENTA ---
def calcular_renta(key):
    with st.container(border=True):
        st.subheader(f"📊 Ingresos {key}")
        tipo = st.selectbox(f"Perfil Principal", ["Dependiente", "Independiente"], key=f"tipo_{key}")
        
        r_fija = 0
        r_variable = 0
        r_no_imp = 0
        
        if tipo == "Dependiente":
            c1, c2, c3 = st.columns(3)
            r_fija = c1.number_input("Sueldo Base + Gratif.", min_value=0, key=f"f_{key}")
            r_variable = c2.number_input("Promedio Variables (Bonos)", min_value=0, key=f"v_{key}")
            r_no_imp = c3.number_input("Colación + Movil.", min_value=0, key=f"n_{key}")
        else:
            archivo = st.file_uploader("Cargar DAI (PDF)", type="pdf", key=f"pdf_{key}")
            if archivo:
                st.success("PDF cargado. Extrayendo datos...")
                # Aquí iría la lógica de extracción específica
            r_fija = st.number_input("Promedio Renta Líquida DAI", min_value=0, key=f"dai_{key}")
            r_fija = r_fija * 0.7 # Castigo independiente

        # EXTRAS (Boletas y Arriendos)
        with st.expander("➕ Sumar Boletas o Arriendos"):
            col_a, col_b = st.columns(2)
            boletas = col_a.number_input("Promedio Boletas (6 meses)", min_value=0, key=f"bol_{key}")
            arriendos = col_b.number_input("Ingreso por Arriendos", min_value=0, key=f"arr_{key}")
        
        total_depurado = r_fija + (r_variable * 0.8) + r_no_imp + (boletas * 0.7) + (arriendos * 0.8)
        return total_depurado

# --- INTERFAZ PRINCIPAL ---
st.title("🏆 Evaluador Hipotecario Profesional")
st.sidebar.metric("UF ACTUAL", f"${uf:,.2f}")

col_t1, col_t2 = st.columns(2)
with col_t1: renta1 = calcular_renta("Titular 1")
with col_t2: 
    act_cod = st.checkbox("¿Incluir Codeudor?")
    renta2 = calcular_renta("Codeudor") if act_cod else 0

renta_total = renta1 + renta2

# --- DEUDA CMF ---
st.divider()
st.header("💳 Deuda CMF (Carga Financiera)")
with st.container(border=True):
    d1, d2, d3 = st.columns(3)
    
    # Consumo
    monto_cons = d1.number_input("Monto Insoluto Consumo/TC", min_value=0)
    cuota_cons_sug = monto_cons * 0.05
    cuota_cons = d1.number_input("Cuota Real Consumo", value=int(cuota_cons_sug), help="Sugerido: 5% de la deuda")
    
    # Hipotecario
    monto_hipo = d2.number_input("Monto Insoluto Hipotecario", min_value=0)
    cuota_hipo_sug = monto_hipo * 0.015
    cuota_hipo = d2.number_input("Cuota Real Hipotecaria", value=int(cuota_hipo_sug), help="Sugerido: 1.5% de la deuda")
    
    # Otros
    monto_com = d3.number_input("Monto Insoluto Comercial/Otros", min_value=0)
    cuota_com = d3.number_input("Cuota Real Otros", value=int(monto_com * 0.05))

total_cuotas_cmf = cuota_cons + cuota_hipo + cuota_com

# --- SIMULACIÓN CRÉDITO ---
st.divider()
st.header("🏠 Parámetros del Crédito")
s1, s2, s3 = st.columns(3)
val_prop = s1.number_input("Valor Propiedad (UF)", value=3000)
monto_uf = s2.number_input("Monto Crédito (UF)", value=2400)
plazo = s3.slider("Plazo (Años)", 5, 30, 20)

# Cálculo Dividendo
tasa = 0.05 / 12
n = plazo * 12
div_uf = monto_uf * (tasa * (1 + tasa)**n) / ((1 + tasa)**n - 1)
div_clp = (div_uf * uf) * 1.15 # Seguros

# --- RESUMEN Y RECOMENDACIÓN ---
st.divider()
rci = (div_clp / renta_total) * 100 if renta_total > 0 else 0
cft = ((div_clp + total_cuotas_cmf) / renta_total) * 100 if renta_total > 0 else 0

st.subheader("📝 Resumen de Evaluación")
res1, res2, res3 = st.columns(3)
res1.metric("Renta Total Depurada", f"${renta_total:,.0f}")
res2.metric("RCI (Solo Hipotecario)", f"{rci:.1f}%")
res3.metric("CFT (Carga Total)", f"{cft:.1f}%")

# LÓGICA DE RECOMENDACIÓN BANCARIA
st.subheader("💡 Recomendación Bancaria")
if rci > 30:
    st.error("❌ NO CALIFICA: El dividendo supera el 30% de la renta. Debe bajar el monto o subir el plazo.")
elif cft > 50:
    st.warning("⚠️ ALTO RIESGO: La carga financiera total es muy alta. Recomendación: Banco Estado o Coopeuch (suelen ser más flexibles).")
elif rci <= 25 and cft <= 40:
    st.success("✅ EXCELENTE PERFIL: Califica en Santander, Chile, BCI y Scotiabank con tasas preferenciales.")
else:
    st.info("ℹ️ PERFIL MEDIO: Califica en BICE o Itaú. Revise si puede consolidar deudas de consumo.")
