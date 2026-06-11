import pandas as pd
import streamlit as st
import plotly.express as px
from google.cloud import bigquery
from google.oauth2 import service_account

st.set_page_config(page_title="Resultados Segunda Vuelta 2026", layout="centered")

PROYECTO = "dashboard-onpe"
UBICACION = "US"
TABLA = "dashboard-onpe.ONPE_SEGUNDA_VUELTA.VOTOS"

# Mapeo de candidato -> foto. La clave es una palabra que aparece en el nombre.
FOTOS = {
    "SANCHEZ": "img/roberto_sanchez.png",
    "FUJIMORI": "img/keiko_fujimori.png",
}


def foto_de(nombre_candidato):
    for clave, ruta in FOTOS.items():
        if clave in nombre_candidato:
            return ruta
    return None


@st.cache_resource
def get_cliente():
    try:
        info = dict(st.secrets["gcp_service_account"])
        credenciales = service_account.Credentials.from_service_account_info(info)
    except Exception:
        credenciales = service_account.Credentials.from_service_account_file("credenciales.json")
    return bigquery.Client(credentials=credenciales, project=PROYECTO, location=UBICACION)


@st.cache_data(ttl=60)
def cargar_ultima():
    cliente = get_cliente()
    consulta = f"""
        SELECT *
        FROM `{TABLA}`
        WHERE fecha = (SELECT MAX(fecha) FROM `{TABLA}`)
    """
    df = cliente.query(consulta).result().to_dataframe()
    df["fecha"] = pd.to_datetime(df["fecha"], utc=True).dt.tz_convert("America/Lima")
    return df


@st.cache_data(ttl=60)
def cargar_historico():
    cliente = get_cliente()
    consulta = f"""
        SELECT fecha, agrupacion, votos, pct_validos
        FROM `{TABLA}`
        WHERE candidato != ''
        ORDER BY fecha
    """
    df = cliente.query(consulta).result().to_dataframe()
    df["fecha"] = pd.to_datetime(df["fecha"], utc=True).dt.tz_convert("America/Lima")
    return df


st.title("🗳️ Segunda Vuelta Presidencial 2026")
st.caption("Datos desde la ONPE, almacenados en BigQuery")

if st.button("🔄 Actualizar datos"):
    st.cache_data.clear()

df = cargar_ultima()
candidatos = df[df["candidato"] != ""].sort_values("votos", ascending=False)

# --- Tarjetas de cada candidato (con foto) ---
col1, col2 = st.columns(2)
for col, (_, fila) in zip([col1, col2], candidatos.iterrows()):
    ruta = foto_de(fila["candidato"])
    if ruta:
        col.image(ruta, width=130)
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

# --- Gráfico de barras horizontal (eje en 0, honesto) ---
st.subheader("Votos válidos por candidato")
fig = px.bar(
    candidatos.sort_values("votos"),
    x="votos",
    y="agrupacion",
    orientation="h",
    text="votos",
    color="agrupacion",
)
fig.update_traces(texttemplate="%{text:,}", textposition="auto")
fig.update_layout(
    showlegend=False,
    xaxis_title="Votos",
    yaxis_title="",
    margin=dict(l=10, r=10, t=10, b=10),
)
st.plotly_chart(fig, width="stretch")

# --- Detalle ---
st.subheader("Detalle")
df_display = df.copy()
df_display["fecha"] = df_display["fecha"].dt.strftime("%d/%m/%Y %H:%M:%S")
st.dataframe(df_display, hide_index=True, width="stretch")

# --- Histórico: evolución del PORCENTAJE (eje acercado, muestra la tendencia) ---
st.subheader("📈 Evolución del % de votos válidos")
historico = cargar_historico()
if historico["fecha"].nunique() > 1:
    fig_hist = px.line(
        historico,
        x="fecha",
        y="pct_validos",
        color="agrupacion",
        markers=True,
    )
    fig_hist.add_hline(
        y=50, line_dash="dash", line_color="gray",
        annotation_text="50%", annotation_position="top left",
    )
    fig_hist.update_layout(
        yaxis_title="% votos válidos",
        xaxis_title="",
        legend_title="",
        margin=dict(l=10, r=10, t=30, b=10),
    )
    st.plotly_chart(fig_hist, width="stretch")

    hist_display = historico.sort_values("fecha", ascending=False).copy()
    hist_display["fecha"] = hist_display["fecha"].dt.strftime("%d/%m/%Y %H:%M:%S")
    st.dataframe(hist_display, hide_index=True, width="stretch")
else:
    st.info("Aún no hay suficientes tomas para el histórico. Espera a que el "
            "programador de tareas registre más lecturas.")