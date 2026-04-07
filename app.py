import streamlit as st
import requests
import pdfplumber
import pandas as pd
from fpdf import FPDF
import re
from datetime import datetime

# --- CONFIGURACIÓN DE MARCA Y UI ---
st.set_page_config(page_title="Analista Pro - Crédito Hipotecario", layout="wide", page_icon="🏦")

# CSS Personalizado para Interfaz Amistosa
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    .stApp { max-width: 1200px; margin: 0 auto; }
    .status-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .uf-header {
        background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE APOYO ---
@st.cache_data(ttl=3600)
def get_uf():
    try: return requests.get("https://mindicador.cl/api/uf").json()['serie'][0]['valor']
    except: return 38500.0

def calcular_promedio_estricto(lista, castigo=1.0):
    validos = [m for m in lista if m > 0]
    if len(validos) < 3:
        return 0, len(validos)
    promedio = sum(validos) / len(validos)
    return promedio * castigo, len(validos)

def extraer_f22(file):
    datos = {"sueldos": 0, "honorarios": 0, "retiros": 0, "rut": ""}
    with pdfplumber.open(file) as pdf:
        texto = "".join([p.extract_text() for p in pdf.pages])
    
    # Búsqueda de Códigos SII
    s = re.search(r"1098\s+([\d.]+)", texto) # Sueldos
    h = re.search(r"110\s+([\d.]+)", texto)  # Honorarios
    r = re.search(r"104\s+([\d.]+)", texto)  # Retiros
    rut = re.search(r"(\d{1,2}\.\d{3}\.\d{3}-[\dkK])", texto)

    if s: datos["sueldos"] = float(s.group(1).replace(".", ""))
    if h: datos["honorarios"] = float(h.group(1).replace(".", ""))
    if r: datos["retiros"] = float(r.group(1).replace(".", ""))
    if rut: datos["rut"] = rut.group(1)
    return datos

# --- INICIO DE APP ---
uf_hoy = get_uf()
st.markdown(f'<div class="uf-header">VALOR UF HOY: ${uf_hoy:,.2f}</div>', unsafe_allow_html=True)

# SIDEBAR: DATOS PERSONALES
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=100)
    st.header("👤 Datos del Evaluado")
    nombre = st.text_input("Nombre Completo", placeholder="Ej: Nelson Acevedo")
    rut_cliente = st.text_input("RUT", placeholder="12.345.678-K")
    st.divider()
    f22_file = st.file_uploader("📂 Cargar F22 (Solo Indep/Mixto)", type="pdf")
    
    f22_data = None
    if f22_file:
        f22_data = extraer_f22(f22_file)
        st.success(f"F22 de {f22_data['rut']} procesado.")

# CUERPO PRINCIPAL (TABS)
tab1, tab2, tab3 = st.tabs(["💰 Ingresos Depurados", "💳 Carga CMF", "📊 Resultado"])

with tab1:
    def seccion_ingresos(key):
        st.subheader(f"Análisis para {key}")
        col_t1, col_t2 = st.columns(2)
        is_dep = col_t1.checkbox(f"Renta Dependiente", value=True, key=f"is_dep_{key}")
        is_ind = col_t2.checkbox(f"Renta Independiente / Mixta", key=f"is_ind_{key}")
        
        r_total = 0
        
        # 1. DEPENDIENTE
        if is_dep:
            with st.expander("📝 Liquidaciones (Últimos 6 meses)"):
                st.caption("Complete al menos 3 meses para validar")
                c1, c2, c3 = st.columns(3)
                fijos = [c1.number_input(f"Fijo Mes {i+1} ($)", min_value=0, key=f"f{i}_{key}") for i in range(6)]
                vars = [c2.number_input(f"Variable Mes {i+1} ($)", min_value=0, key=f"v{i}_{key}") for i in range(6)]
                no_imp = [c3.number_input(f"No Imp. Mes {i+1} ($)", min_value=0, key=f"n{i}_{key}") for i in range(6)]
                
                p_fijo, _ = calcular_promedio_estricto(fijos)
                p_var, _ = calcular_promedio_estricto(vars, castigo=0.7)
                p_no_imp, _ = calcular_promedio_estricto(no_imp)
                r_total += (p_fijo + p_var + p_no_imp)

        # 2. INDEPENDIENTE (F22 + Boletas)
        if is_ind:
            with st.expander("💼 Honorarios y Retiros (F22)"):
                val_honor = f22_data['honorarios']/12 if f22_data else 0
                val_retiros = f22_data['retiros']/12 if f22_data else 0
                
                h_mensual = st.number_input("Promedio Honorarios Brutos ($)", value=int(val_honor), key=f"h_{key}")
                r_mensual = st.number_input("Promedio Retiros ($)", value=int(val_retiros), key=f"r_{key}")
                
                r_total += (h_mensual * 0.7) + (r_mensual * 0.7)
                
                if st.checkbox("¿Tiene Boletas adicionales?", key=f"has_b_{key}"):
                    st.caption("Boletas últimos 6 meses")
                    bc1, bc2 = st.columns(2)
                    bols = [bc1.number_input(f"Boleta Mes {i+1}", min_value=0, key=f"b_{i}_{key}") for i in range(6)]
                    p_bol, _ = calcular_promedio_estricto(bols, castigo=0.7)
                    r_total += p_bol

        # 3. ARRIENDOS (OPCIONAL)
        if st.checkbox("🏠 ¿Percibe Arriendos?", key=f"has_a_{key}"):
            arr = st.number_input("Monto total arriendos ($)", min_value=0, key=f"arr_{key}")
            r_total += (arr * 0.8)
            
        return r_total

    r1 = seccion_ingresos("Titular")
    r2 = 0
    if st.checkbox("➕ Agregar Codeudor"):
        r2 = seccion_ingresos("Codeudor")
    
    renta_total = r1 + r2
    st.metric("Renta Mensual Depurada Total", f"${renta_total:,.0f}")

with tab2:
    st.header("Análisis de Deuda Actual")
    col_d1, col_d2 = st.columns(2)
    
    with col_d1:
        st.subheader("Deuda Consumo / Tarjetas")
        m_cons = st.number_input("Monto Insoluto Consumo ($)", min_value=0)
        c_cons = st.number_input("Cuota Real Consumo ($)", value=int(m_cons * 0.05))
        m_tc = st.number_input("Deuda utilizada TC ($)", min_value=0)
        c_tc = st.number_input("Cuota Real TC ($)", value=int(m_tc * 0.05))
        
    with col_d2:
        st.subheader("Deuda Hipotecaria")
        m_hipo = st.number_input("Monto Insoluto Hipotecario ($)", min_value=0)
        c_hipo = st.number_input("Dividendo Real ($)", value=int(m_hipo * 0.015))

    total_cmf = c_cons + c_tc + c_hipo

with tab3:
    st.header("Simulación de Crédito")
    c_s1, c_s2, c_s3 = st.columns(3)
    val_p = c_s1.number_input("Valor Propiedad (UF)", value=3000)
    m_c = c_s2.number_input("Crédito (UF)", value=2400)
    plazo = c_s3.slider("Plazo (Años)", 5, 30, 25)
    
    # Cálculo Dividendo
    tasa = 0.05 / 12
    n = plazo * 12
    div_uf = m_c * (tasa * (1 + tasa)**n) / ((1 + tasa)**n - 1)
    div_clp = (div_uf * uf_hoy) * 1.15
    
    rci = (div_clp / renta_total * 100) if renta_total > 0 else 0
    cft = ((div_clp + total_cmf) / renta_total * 100) if renta_total > 0 else 0
    
    # DASHBOARD FINAL
    st.divider()
    d_col1, d_col2 = st.columns(2)
    with d_col1:
        st.metric("Carga Hipotecaria (RCI)", f"{rci:.1f}%", delta="-25%" if rci <= 25 else "ALTO", delta_color="inverse")
        st.caption("Máximo sugerido: 25%")
    with d_col2:
        st.metric("Carga Financiera Total (CFT)", f"{cft:.1f}%", delta="-45%" if cft <= 45 else "ALTO", delta_color="inverse")
        st.caption("Máximo sugerido: 45%")

    st.subheader("💡 Recomendación Bancaria")
    if rci <= 25 and cft <= 45:
        st.success(f"✅ CLIENTE CALIFICA. Recomendación: Santander, Chile o BCI. Perfil de bajo riesgo.")
    elif cft <= 50:
        st.warning(f"⚠️ PERFIL LIMITADO. Calificaría en Banco Estado o Scotiabank. Evaluar reducir deuda de consumo.")
    else:
        st.error(f"❌ RECHAZADO POR RIESGO. La carga total ({cft:.1f}%) excede las políticas bancarias.")

    if st.button("📄 Descargar Certificado de Pre-Evaluación"):
        st.write("Generando PDF para ", nombre)
        # Aquí se llama a la función FPDF con los datos recolectados
