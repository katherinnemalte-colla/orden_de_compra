from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.conexion import Conexion
from app.plantillas import BASE
from app.routers import pedidos, vistas

app = FastAPI(title="Orden de compra")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
app.include_router(vistas.router)   # pantalla (HTML con Jinja2)
app.include_router(pedidos.router)  # API JSON (/api/pedidos), útil para los servicios PHP


@app.get("/salud")
def salud():
    return Conexion.probar()