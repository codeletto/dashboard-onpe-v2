from google.cloud import bigquery
from google.oauth2 import service_account

credenciales = service_account.Credentials.from_service_account_file("credenciales.json")

# Agregamos location= con la ubicación real de tu dataset
cliente = bigquery.Client(
    credentials=credenciales,
    project="dashboard-onpe",
    location="US", 
)

consulta = "SELECT COUNT(*) AS total_filas FROM `dashboard-onpe.ONPE_SEGUNDA_VUELTA.VOTOS`"
resultado = cliente.query(consulta).result()

for fila in resultado:
    print("Conexión exitosa. Filas en la tabla votos:", fila.total_filas)