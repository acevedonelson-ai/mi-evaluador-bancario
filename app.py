import streamlit as st
import requests
import pandas as pd
from fpdf import FPDF
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Analista Riesgo Hipotecario", layout="wide")

st.markdown("""
    <style>
    .uf-card { background-color: #1E3A8A; color: white; padding: 20px; border-radius: 10px; text-align: center; }
    .stMetric { border: 1px solid #ddd; padding: 10px; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def get_uf():
    try: return requests.get("https://mindicador.cl/api/uf").json()['serie'][0]['valor']
    except: return 38000.0

uf_hoy = get_uf()

# --- FUNCIONES DE CÁLCULO ---
def calcular_promedio_castigado(lista_montos, castigo=0.3):
    # Filtra valores mayores a 0
    validos = [m for m in lista_montos if m > 0]
    if len(validos) < 3: return 0
    promedio = sum(validos) / len(validos)
    return promedio * (1 - castigo)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f'<div class="uf-card"><h3>UF ACTUAL</h3><h2>${uf_hoy:,.2f}</h2></div>', unsafe_allow_html=True)
    st.header("👤 Datos del Titular")
    nombre = st.text_input("Nombre Completo")
    rut = st.text_input("RUT")

# --- CUERPO PRINCIPAL ---
st.title("🛡️ Sistema de Evaluación de Riesgo Bancario")

def seccion_ingresos(label):
    st.header(f"💼 Perfil Ingresos: {label}")
    
    # 1. Definir Naturaleza de la Renta
    c1, c2 = st.columns(2)
    es_dep = c1.checkbox(f"{label} es Dependiente", value=True, key=f"dep_{label}")
    es_ind = c2.checkbox(f"{label} es Independiente", key=f"ind_{label}")
    
    renta_final = 0
    
    # SECCIÓN DEPENDIENTE
    if es_dep:
        with st.expander(f"Detalle Liquidaciones - {label}", expanded=True):
            col_f, col_v, col_n = st.columns(3)
            with col_f:
                st.subheader("Fijos")
                base = st.number_input(f"Sueldo Base ($)", min_value=0, key=f"base_{label}")
                grat = st.number_input(f"Gratificación ($)", min_value=0, key=f"grat_{label}")
            with col_v:
                st.subheader("Variables (Castigo 30%)")
                st.caption("Ingrese al menos 3 meses")
                v1 = st.number_input("Mes 1", min_value=0, key=f"v1_{label}")
                v2 = st.number_input("Mes 2", min_value=0, key=f"v2_{label}")
                v3 = st.number_input("Mes 3", min_value=0, key=f"v3_{label}")
                v_prom = calcular_promedio_castigado([v1, v2, v3])
            with col_n:
                st.subheader("No Imponibles")
                colac = st.number_input(f"Colación ($)", min_value=0, key=f"col_{label}")
                movil = st.number_input(f"Movilización ($)", min_value=0, key=f"mov_{label}")
            
            renta_final += (base + grat + colac + movil + v_prom)

    # SECCIÓN INDEPENDIENTE
    if es_ind:
        with st.expander(f"Detalle Tributario (DAI) - {label}", expanded=True):
            st.info("Cargue PDF de Declaración de Impuestos para análisis")
            archivo = st.file_uploader("Subir DAI", type="pdf", key=f"pdf_{label}")
            # Simulamos lectura de DAI (Castigo 30% estándar bancario)
            monto_dai = st.number_input("Renta Líquida Anual Declarada ($)", min_value=0, key=f"dai_m_{label}")
            renta_final += (monto_dai / 12) * 0.7

    # SECCIÓN OPCIONAL: BOLETAS Y ARRIENDOS
    with st.expander(f"Ingresos Adicionales (Boletas/Arriendos) - {label}"):
        tiene_bol = st.checkbox("¿Tiene Boletas de Honorarios?", key=f"has_bol_{label}")
        if tiene_bol:
            st.caption("Promedio 6 meses (Castigo 30%)")
            b_cols = st.columns(3)
            bols = [b_cols[i%3].number_input(f"Mes {i+1}", min_value=0, key=f"bol_{i}_{label}") for i in range(6)]
            renta_final += calcular_promedio_castigado(bols)
            
        tiene_arr = st.checkbox("¿Tiene Ingresos por Arriendo?", key=f"has_arr_{label}")
        if tiene_arr:
            arr_monto = st.number_input("Monto mensual Arriendo ($)", min_value=0, key=f"arr_val_{label}")
            renta_final += (arr_monto * 0.8) # 20% vacancia

    return renta_final

# Ejecutar secciones
r1 = seccion_ingresos("Titular")
r2 = 0
if st.checkbox("👥 Agregar Codeudor"):
    r2 = seccion_ingresos("Codeudor")

renta_total = r1 + r2

# --- ANÁLISIS DE DEUDA CMF ---
st.divider()
st.header("💳 Análisis de Deuda CMF (Consolidado)")
with st.container(border=True):
    d1, d2, d3 = st.columns(3)
    
    # Consumo
    m_cons = d1.number_input("Deuda Total Consumo ($)", min_value=0)
    c_cons_sug = m_cons * 0.05
    c_cons = d1.number_input("Cuota Mensual Consumo Real ($)", value=int(c_cons_sug))
    
    # Tarjetas
    m_tc = d2.number_input("Cupo Utilizado TC ($)", min_value=0)
    c_tc_sug = m_tc * 0.05
    c_tc = d2.number_input("Pago Mensual TC Real ($)", value=int(c_tc_sug))
    
    # Hipotecario
    m_hipo = d3.number_input("Deuda Total Hipotecaria ($)", min_value=0)
    c_hipo_sug = m_hipo * 0.015
    c_hipo = d3.number_input("Dividendo Mensual Real ($)", value=int(c_hipo_sug))

total_cuotas_previas = c_cons + c_tc + c_hipo

# --- SIMULACIÓN NUEVO CRÉDITO ---
st.divider()
st.header("🏠 Simulación Nuevo Crédito")
s1, s2, s3 = st.columns(3)
v_prop_uf = s1.number_input("Valor Propiedad (UF)", value=3500)
m_cred_uf = s2.number_input("Crédito Solicitado (UF)", value=2800)
plazo = s3.slider("Plazo en Años", 5, 30, 20)

# Cálculo Matemático Financiero
tasa_anual = 0.05
tasa_mensual = tasa_anual / 12
n = plazo * 12
div_uf = m_cred_uf * (tasa_mensual * (1 + tasa_mensual)**n) / ((1 + tasa_mensual)**n - 1)
div_clp = (div_uf * uf_hoy) * 1.15 # Seguros

# --- RESUMEN DE CARGAS ---
st.divider()
rci = (div_clp / renta_total * 100) if renta_total > 0 else 0
cft = ((div_clp + total_cuotas_previas) / renta_total * 100) if renta_total > 0 else 0

st.header("📊 Resultado Evaluación Financiera")
res1, res2, res3 = st.columns(3)
res1.metric("Renta Líquida Depurada", f"${renta_total:,.0f}")
res2.metric("Carga Hipotecaria (RCI)", f"{rci:.1f}%")
res3.metric("Carga Financiera Total (CFT)", f"{cft:.1f}%")

# RECOMENDACIONES BANCARIAS
with st.expander("📝 Ver Recomendaciones y Análisis"):
    st.write(f"**Análisis para {nombre}:**")
    if rci > 25:
        st.error(f"⚠️ RCI Alto ({rci:.1f}%): Supera el 25% recomendado. El dividendo es muy alto para esta renta.")
    if cft > 45:
        st.error(f"⚠️ Sobreendeudamiento ({cft:.1f}%): La carga financiera total supera el 45%.")
    
    if rci <= 25 and cft <= 40:
        st.success("✅ Califica en: Bancos Tradicionales (Chile, Santander, BCI, Scotiabank).")
    elif cft <= 50:
        st.warning("✅ Califica en: Banco Estado o Mutuales (más flexibles con la carga total).")
    else:
        st.error("❌ No califica actualmente. Se recomienda prepagar deuda de consumo antes de postular.")

# --- PDF ---
if st.button("📄 Descargar Resumen en PDF"):
    st.info("Generando archivo...")
    # (Aquí iría la lógica simplificada del PDF con FPDF)
