from fastapi import FastAPI
from app.api.routes import router as api_router
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(
    title="FreightFlow Tariff API",
    description="AI-powered backend for ingesting and parsing Freight Tariff PDFs.",
    version="0.1.0"
)

app.include_router(api_router, prefix="/api/v1")

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def root():
    return FileResponse('app/static/index.html')
