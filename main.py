# main.py
import ee
import os
import json
from fastapi import FastAPI, Query, HTTPException
from typing import Optional
from google.oauth2 import service_account

# --- Inicialización ---
app = FastAPI(
    title="API de Patrones de Vegetación 🛰️🌱",
    description="Una API para explorar datos de NDVI (Índice de Vegetación) a lo largo del tiempo usando datos de MODIS de Google Earth Engine.",
    version="1.0.0",
)

# Bloque de conexión con Service Account
try:
    # Intentar obtener credenciales desde variable de entorno
    credentials_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
    
    if credentials_json:
        # Si las credenciales están en formato JSON string
        credentials_dict = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=['https://www.googleapis.com/auth/earthengine']
        )
        ee.Initialize(
            credentials=credentials,
            project='api-vegetacion-datos',
            opt_url='https://earthengine-highvolume.googleapis.com'
        )
    else:
        # Si las credenciales están en un archivo
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '/app/credentials.json')
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/earthengine']
        )
        ee.Initialize(
            credentials=credentials,
            project='api-vegetacion-datos',
            opt_url='https://earthengine-highvolume.googleapis.com'
        )
    
    print("✅ Conexión con Google Earth Engine exitosa.")
except Exception as e:
    print(f"❌ Error al conectar con Google Earth Engine: {e}")
    raise

# --- Definición del Endpoint de la API ---
@app.get("/api/v1/patrones_vegetacion")
async def obtener_patrones_vegetacion(
    lat: float = Query(..., description="Latitud del punto de interés (ej. -12.046374)", ge=-90, le=90),
    lon: float = Query(..., description="Longitud del punto de interés (ej. -77.042793)", ge=-180, le=180),
    fecha_inicio: str = Query(..., description="Fecha de inicio en formato AAAA-MM-DD (ej. 2022-01-01)"),
    fecha_fin: str = Query(..., description="Fecha de fin en formato AAAA-MM-DD (ej. 2022-12-31)")
):
    try:
        punto_de_interes = ee.Geometry.Point(lon, lat)
        coleccion_imagenes = ee.ImageCollection('MODIS/061/MOD13Q1').select('NDVI')
        coleccion_filtrada = coleccion_imagenes.filterDate(ee.Date(fecha_inicio), ee.Date(fecha_fin))
        
        def extraer_valor_ndvi(imagen):
            valor = imagen.reduceRegions(
                collection=punto_de_interes,
                reducer=ee.Reducer.mean(),
                scale=250
            ).first()
            return valor.set('date', imagen.date().format('YYYY-MM-dd'))
        
        serie_temporal = coleccion_filtrada.map(extraer_valor_ndvi)
        lista_resultados = serie_temporal.getInfo()['features']
        
        respuesta_formateada = []
        for feature in lista_resultados:
            valor_ndvi_crudo = feature['properties'].get('mean')
            if valor_ndvi_crudo is not None:
                valor_ndvi_real = round(valor_ndvi_crudo * 0.0001, 4)
                respuesta_formateada.append({
                    "fecha": feature['properties']['date'],
                    "ndvi": valor_ndvi_real
                })
        
        if not respuesta_formateada:
            raise HTTPException(status_code=404, detail="No se encontraron datos de NDVI para la ubicación y fechas especificadas.")
        
        return {
            "ubicacion": {"lat": lat, "lon": lon},
            "rango_fechas": {"inicio": fecha_inicio, "fin": fecha_fin},
            "serie_temporal_ndvi": respuesta_formateada
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ocurrió un error al procesar la solicitud en Google Earth Engine: {str(e)}")

@app.get("/")
def root():
    return {"mensaje": "Bienvenido a la API de Patrones de Vegetación. Usa el endpoint /docs para ver la documentación."}
