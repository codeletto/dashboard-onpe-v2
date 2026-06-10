import pandas as pd
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

st.set_page_config(page_title="Resultados Segunda Vuelta 2026", layout="centered")

PROYECTO = "dashboard-onpe"
UBICACION = "US"
TABLA = "dashboard-onpe.ONPE_SEGUNDA_VUELTA.VOTOS"


# --- Conexión a BigQuery ---
# En local lee el archivo credenciales.json; en la nube leerá los "secrets".
@st.cache_resource
def get_cliente():
    # En la nube: lee credenciales desde los secrets de Streamlit.
    # En local: usa el archivo credenciales.json.
    if "gcp_service_account" in st.secrets:
        credenciales = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"]
        )
    else:
        credenciales = service_account.Credentials.from_service_account_file("credenciales.json")
    return bigquery.Client(credentials=credenciales, project=PROYECTO, location=UBICACION)

# --- Traer la ÚLTIMA foto de votos (la más reciente) ---
@st.cache_data(ttl=60)
def cargar_ultima():
    cliente = get_cliente()
    consulta = f"""
        SELECT *
        FROM `{TABLA}`
        WHERE fecha = (SELECT MAX(fecha) FROM `{TABLA}`)
    """
    return cliente.query(consulta).result().to_dataframe()


# --- Traer TODO el histórico (para la línea de tiempo) ---
@st.cache_data(ttl=60)
def cargar_historico():
    cliente = get_cliente()
    consulta = f"""
        SELECT fecha, agrupacion, votos
        FROM `{TABLA}`
        WHERE candidato != ''
        ORDER BY fecha
    """
    return cliente.query(consulta).result().to_dataframe()


st.title("🗳️ Segunda Vuelta Presidencial 2026")
st.caption("Datos desde la ONPE, almacenados en BigQuery")

if st.button("🔄 Actualizar datos"):
    st.cache_data.clear()

df = cargar_ultima()
candidatos = df[df["candidato"] != ""].sort_values("votos", ascending=False)

# --- Tarjetas de cada candidato ---
col1, col2 = st.columns(2)
for col, (_, fila) in zip([col1, col2], candidatos.iterrows()):
    col.metric(
        label=fila["agrupacion"],
        value=f"{fila['pct_validos']:.3f} %",
        delta=f"{int(fila['votos']):,} votos",
    )

# --- Diferencia de votos ---
lider = candidatos.iloc[0]
segundo = candidatos.iloc[1]
diferencia = int(lider["votos"]) - int(segundo["votos"])
st.metric(
    label=f"Diferencia a favor de {lider['agrupacion']}",
    value=f"{diferencia:,} votos",
)

# --- Gráfico de barras ---
st.subheader("Votos válidos por candidato")
st.bar_chart(candidatos, x="agrupacion", y="votos")

# --- Detalle ---
st.subheader("Detalle")
st.dataframe(df, hide_index=True)

# --- Histórico desde BigQuery ---
st.subheader("📈 Histórico de votos")
historico = cargar_historico()
if len(historico) > 0:
    pivote = historico.pivot_table(
        index="fecha", columns="agrupacion", values="votos", aggfunc="last"
    )
    st.line_chart(pivote)
    st.dataframe(historico.sort_values("fecha", ascending=False), hide_index=True)
else:
    st.info("Aún no hay suficientes registros para el histórico.")