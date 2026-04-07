import streamlit as st
import requests

# 1. FUNCIÓN PARA OBTENER UF AUTOMÁTICA
@st.cache_data(ttl=3600)
def obtener_uf():
    try:
        # Consulta a la API de mindicador.cl
        data = requests.get("https://mindicador.cl/api/uf").json()
        return data['serie'][0]['valor']
    except:
        return 38000.0  # Valor de respaldo si falla la conexión

uf_valor = obtener_uf()

# CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Analista Bancario Pro", layout="wide")
st.title("🏦 Evaluador de Crédito Hipotecario")
st.sidebar.metric("UF Hoy", f"${uf_valor:,.2f}")

# 2. FUNCIÓN DE DEPURACIÓN DE RENTA (Según tu requerimiento)
def depurar_ingresos(persona):
    st.subheader(f"Ingresos {persona}")
    tipo = st.radio(f"Tipo de trabajador ({persona})", ["Dependiente", "Independiente"], key=f"tipo_{persona}")
    
    if tipo == "Dependiente":
        col1, col2, col3 = st.columns(3)
        with col1:
            fijo = st.number_input(f"Sueldo Base + Gratificación ({persona})", min_value=0, key=f"f_{persona}")
        with col2:
            variable = st.number_input(f"Bonos + Comisiones ({persona})", min_value=0, key=f"v_{persona}")
        with col3:
            no_imp = st.number_input(f"Colación + Movilización ({persona})", min_value=0, key=f"n_{persona}")
        
        # Lógica: Fijos y No imponibles al 100%, Variables al 80%
        return fijo + no_imp + (variable * 0.8)
    else:
        st.info("Cargar DAI (Declaración Anual de Impuestos)")
        renta_anual = st.number_input(f"Promedio Renta Líquida Anual ({persona})", min_value=0, key=f"dai_{persona}")
        # Los bancos castigan la renta de independientes (usualmente 30%)
        return (renta_anual / 12) * 0.7

# 3. ENTRADA DE DATOS
col_tit, col_cod = st.columns(2)
with col_tit:
    renta_t1 = depurar_ingresos("Titular 1")

with col_cod:
    hay_codeudor = st.checkbox("¿Agregar Codeudor?")
    renta_t2 = depurar_ingresos("Codeudor") if hay_codeudor else 0

renta_total_neta = renta_t1 + renta_t2

st.divider()

# 4. DEUDA CMF (Lo que pediste)
st.header("💳 Deuda CMF (Carga Mensual)")
c1, c2, c3, c4 = st.columns(4)
d_consumo = c1.number_input("Cuota Consumo/Tarjeta", value=0)
d_hipo = c2.number_input("Dividendo Actual", value=0)
d_comercial = c3.number_input("Crédito Comercial", value=0)
d_otros = c4.number_input("Otros/Línea", value=0)

deuda_previa = d_consumo + d_hipo + d_comercial + d_otros

# 5. SIMULACIÓN NUEVO CRÉDITO
st.divider()
st.header("🏠 Datos de la Propiedad")
p1, p2, p3 = st.columns(3)
v_prop = p1.number_input("Valor Propiedad (UF)", value=2500)
c_solicitado = p2.number_input("Crédito Solicitado (UF)", value=2000)
plazo = p3.slider("Plazo (Años)", 5, 30, 20)

# Cálculo matemático del dividendo (Tasa 5% estimada + seguros)
tasa_mes = (0.05 / 12)
n = plazo * 12
dividendo_uf = c_solicitado * (tasa_mes * (1 + tasa_mes)**n) / ((1 + tasa_mes)**n - 1)
dividendo_clp = (dividendo_uf * uf_valor) * 1.12 # Incluye 12% aprox de seguros desgravamen/incendio

# 6. RATIOS Y RESULTADOS
rci = (dividendo_clp / renta_total_neta * 100) if renta_total_neta > 0 else 0
cft = ((dividendo_clp + deuda_previa) / renta_total_neta * 100) if renta_total_neta > 0 else 0

st.sidebar.divider()
st.sidebar.header("📊 Resultado Final")
st.sidebar.metric("Dividendo Est. (con seguros)", f"${dividendo_clp:,.0f}")
st.sidebar.metric("RCI (Hipotecario / Renta)", f"{rci:.1f}%")
st.sidebar.metric("CFT (Carga Total)", f"{cft:.1f}%")

if rci <= 25 and cft <= 45:
    st.sidebar.success("✅ EVALUACIÓN: VIABLE")
else:
    st.sidebar.error("❌ EVALUACIÓN: RECHAZADA")
    if rci > 25: st.sidebar.write("Motivo: Dividendo supera 25% de la renta.")
    if cft > 45: st.sidebar.write("Motivo: Carga financiera total supera 45%.")
