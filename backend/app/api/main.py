
from fastapi import FastAPI

from app.api.health import router as health_router

app = FastAPI(
    title="Inventra API",
    description="AI-powered Inventory Tracking and Demand Forecasting Platform",
    version="0.1.0",
)

app.include_router(health_router)


@app.get("/")
def root():
    return {
        "message": "Welcome to Inventra API",
        "status": "running",
    }
