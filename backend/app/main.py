
from fastapi import FastAPI
from app.api.purchase_orders import router as purchase_orders_router
from app.api.health import router as health_router
from app.api.inventory import router as inventory_router
from app.api.consumption import router as consumption_router
from app.api.assistant import router as assistant_router
from app.api.forecasting import router as forecasting_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Inventra API",
    description="AI-powered Inventory Tracking and Demand Forecasting Platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(inventory_router)
app.include_router(consumption_router)
app.include_router(forecasting_router)
app.include_router(assistant_router)
app.include_router(purchase_orders_router)

@app.get("/")
def root():
    return {
        "message": "Welcome to Inventra API",
        "status": "running",
    }
