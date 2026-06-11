import pandas as pd
import streamlit as st
import plotly.express as px
from google.cloud import bigquery
from google.oauth2 import service_account

st.set_page_config(page_title="Resultados Segunda Vuelta 2026", layout="centered")

PROYECTO = "dashboard-onpe"
UBICACION = "US"
TABLA = "dashboard-onpe.ONPE_SEGUNDA_VUELTA.VOTOS"

FOTOS = {
    "SANCHEZ": "img/roberto_sanchez.png",
    "FUJIMORI": "img/keiko_fujimori.png",
}

# Colores por partido (naranja FP, verde JPP)
NARANJA = "#F2811D"
VERDE = "#2FA84F"


def foto_de(nombre_candidato):
    for clave, ruta in FOTOS.items():
        if clave in nombre_candidato:
            return ruta
    return None


def color_de(agrupacion):
    if "FUERZA" in agrupacion:
        return NARANJA
    if "JUNTOS" in agrupacion:
        return VERDE
    return "#888888"


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


# ===== Encabezado =====
st.title("🗳️ Segunda Vuelta Presidencial 2026")
st.caption("Datos desde la ONPE, almacenados en BigQuery")

if st.button("🔄 Actualizar datos"):
    st.cache_data.clear()

df = cargar_ultima()
candidatos = df[df["candidato"] != ""].sort_values("votos", ascending=False)

# Mapa de colores construido desde los valores reales de los datos
color_map = {a: color_de(a) for a in candidatos["agrupacion"].unique()}

# ===== Pestañas (NAV) =====
tab_resumen, tab_evolucion, tab_acerca = st.tabs(
    ["📊 Resumen", "📈 Evolución", "ℹ️ Acerca de"]
)

# ---------- PESTAÑA 1: RESUMEN ----------
with tab_resumen:
    col1, col2 = st.columns(2)
    for col, (_, fila) in zip([col1, col2], candidatos.iterrows()):
        with col:
            ruta = foto_de(fila["candidato"])
            if ruta:
                izq, centro, der = st.columns([1, 2, 1])
                with centro:
                    st.image(ruta, width="stretch")
            c = color_de(fila["agrupacion"])
            st.markdown(
                f"<div style='text-align:center'>"
                f"<b>{fila['agrupacion']}</b><br>"
                f"<span style='font-size:2.2em'>{fila['pct_validos']:.3f} %</span><br>"
                f"<span style='color:{c}'>↑ {int(fila['votos']):,} votos</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    lider = candidatos.iloc[0]
    segundo = candidatos.iloc[1]
    diferencia = int(lider["votos"]) - int(segundo["votos"])
    st.markdown(
        f"<div style='text-align:center; margin-top:1em'>"
        f"Diferencia a favor de <b>{lider['agrupacion']}</b><br>"
        f"<span style='font-size:1.8em'>{diferencia:,} votos</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.subheader("Votos válidos por candidato")
    fig = px.bar(
        candidatos.sort_values("votos"),
        x="votos", y="agrupacion", orientation="h",
        text="votos", color="agrupacion",
        color_discrete_map=color_map,
    )
    fig.update_traces(texttemplate="%{text:,}", textposition="auto")
    fig.update_layout(
        showlegend=False, xaxis_title="Votos", yaxis_title="",
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig, width="stretch")

# ---------- PESTAÑA 2: EVOLUCIÓN ----------
with tab_evolucion:
    st.subheader("📈 Evolución del % de votos válidos")
    historico = cargar_historico()
    if historico["fecha"].nunique() > 1:
        fig_hist = px.line(
            historico, x="fecha", y="pct_validos",
            color="agrupacion", markers=True,
            color_discrete_map=color_map,
        )
        fig_hist.add_hline(
            y=50, line_dash="dash", line_color="gray",
            annotation_text="50%", annotation_position="top left",
        )
        fig_hist.update_layout(
            yaxis_title="% votos válidos", xaxis_title="",
            legend_title="", margin=dict(l=10, r=10, t=30, b=10),
        )
        st.plotly_chart(fig_hist, width="stretch")
    else:
        st.info("Aún no hay suficientes tomas para el histórico.")

# ---------- PESTAÑA 3: ACERCA DE ----------
with tab_acerca:
    st.markdown("""
### Acerca de este proyecto

Dashboard que monitorea **en tiempo real** los resultados de la segunda vuelta
presidencial 2026 del Perú, consumiendo la API pública de la ONPE.

#### 🏗️ Arquitectura

El proyecto usa una **arquitectura desacoplada** (separa la ingesta de la presentación):

1. **Ingesta (ETL):** un script en Python, ejecutado localmente y programado con el
   Programador de tareas de Windows, extrae los datos en vivo de la API de la ONPE,
   los transforma y los carga en BigQuery.
2. **Almacenamiento:** Google BigQuery funciona como *data warehouse*, guardando cada
   lectura con su marca de tiempo, lo que permite construir el histórico de la jornada.
3. **Presentación:** esta app en Streamlit lee los datos desde BigQuery y los visualiza.

#### 🧩 El reto técnico

La API de la ONPE solo responde a peticiones **desde Perú** (restricción geográfica).
Como los servidores de Streamlit Cloud están en el extranjero, no pueden consultarla
directamente. La solución fue **desacoplar**: solo la ingesta (que corre desde Perú)
toca la ONPE, mientras que el dashboard lee de BigQuery, accesible globalmente. Así el
bloqueo geográfico queda resuelto, con un manejo de errores que prioriza datos en vivo.

#### 🛠️ Stack técnico

- **Python** (requests, pandas)
- **Google BigQuery** (data warehouse)
- **Streamlit + Plotly** (dashboard y visualización)
- **Git / GitHub** (control de versiones y despliegue)

---

**Autor:** Adrian Aybar Medina
""")

# ===== Pie de página (visible en todas las pestañas) =====
st.divider()
ultima = df["fecha"].iloc[0].strftime("%d/%m/%Y %H:%M:%S")
st.caption(f"🕒 Última actualización de los datos: {ultima} (hora de Perú) · Fuente: ONPE")