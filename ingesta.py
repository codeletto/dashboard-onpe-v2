from datetime import datetime, timezone, timedelta

import requests
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

# ===== Configuración =====
PROYECTO = "dashboard-onpe"
UBICACION = "US"
TABLA = "dashboard-onpe.ONPE_SEGUNDA_VUELTA.VOTOS"

URL = "https://resultadosegundavuelta.onpe.gob.pe/presentacion-backend/eleccion-presidencial/participantes-ubicacion-geografica-nombre?idEleccion=10&tipoFiltro=eleccion"

HEADERS = {
    "accept": "*/*",
    "accept-language": "es-ES,es;q=0.9,en;q=0.8",
    "content-type": "application/json",
    "priority": "u=1, i",
    "referer": "https://resultadosegundavuelta.onpe.gob.pe/main/presidenciales",
    "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
}


# ===== 1. Traer datos en vivo de la ONPE =====
def traer_datos():
    respuesta = requests.get(URL, headers=HEADERS, timeout=10)
    registros = respuesta.json()["data"]
    df = pd.DataFrame(registros)

    peru = timezone(timedelta(hours=-5))
    ahora = datetime.now(peru)

    salida = pd.DataFrame({
        "fecha": ahora,
        "agrupacion": df["nombreAgrupacionPolitica"],
        "candidato": df["nombreCandidato"],
        "votos": df["totalVotosValidos"],
        "pct_validos": df.get("porcentajeVotosValidos"),
        "pct_emitidos": df.get("porcentajeVotosEmitidos"),
    })

    salida["fecha"] = pd.to_datetime(salida["fecha"])
    salida["votos"] = salida["votos"].astype("Int64")
    return salida


# ===== 2. Escribir en BigQuery (load job, modo APPEND) =====
def escribir_en_bigquery(cliente, df):
    config = bigquery.LoadJobConfig(write_disposition="WRITE_APPEND")
    job = cliente.load_table_from_dataframe(df, TABLA, job_config=config)
    job.result()
    print(f"Cargadas {len(df)} filas en {TABLA}")


# ===== 3. Verificar si los votos cambiaron desde la última carga =====
def votos_cambiaron(cliente, df_nuevo):
    consulta = f"""
        SELECT agrupacion, votos
        FROM `{TABLA}`
        WHERE fecha = (SELECT MAX(fecha) FROM `{TABLA}`)
    """
    try:
        ultima = cliente.query(consulta).result().to_dataframe()
    except Exception:
        return True

    if ultima.empty:
        return True

    prev = dict(zip(ultima["agrupacion"], ultima["votos"]))
    cur = dict(zip(df_nuevo["agrupacion"], df_nuevo["votos"]))
    return prev != cur


# ===== Ejecución =====
if __name__ == "__main__":
    datos = traer_datos()
    print("Datos traídos de la ONPE:")
    print(datos)

    credenciales = service_account.Credentials.from_service_account_file("credenciales.json")
    cliente = bigquery.Client(credentials=credenciales, project=PROYECTO, location=UBICACION)

    if votos_cambiaron(cliente, datos):
        escribir_en_bigquery(cliente, datos)
        print("Listo: datos nuevos cargados.")
    else:
        print("Sin cambios desde la última carga. No se registró nada.")