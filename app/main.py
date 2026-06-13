import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="google.auth")
warnings.filterwarnings("ignore", category=FutureWarning, module="google.oauth2")
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

from fastapi import FastAPI, Depends, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
import uuid
import os

from .api import auth_api, user_api, station_api, scan_api, part_api, shift_api, job_card_api, process_api, reason_api, asset_api, kiosk_api, product_api, plant_api, dealer_signup_api, b2b_admin_api, b2b_cart_api, b2b_dealer_api, b2b_order_api, b2b_dashboard_api, coin_api
from . import schemas, auth
from .firebase_client import init_firebase

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_firebase()
    yield

app = FastAPI(
    title="Vega Track API", 
    description="MongoDB Backend for QR-based Product Traceability System", 
    version="1.0.0",
    lifespan=lifespan
)

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "color" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail.get("message"),
                "error_color_code": exc.detail.get("color")
            }
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

from starlette.middleware.sessions import SessionMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "super_secret_vega_track_key_1234")
)

os.makedirs("qrcodes", exist_ok=True)
app.mount("/qrcodes", StaticFiles(directory="qrcodes"), name="qrcodes")
app.include_router(auth_api.router)
app.include_router(user_api.router)
app.include_router(station_api.router)
app.include_router(scan_api.router)
app.include_router(part_api.router)
app.include_router(shift_api.router)
app.include_router(job_card_api.router)
app.include_router(process_api.router)
app.include_router(reason_api.router)
app.include_router(asset_api.router)
app.include_router(kiosk_api.router)
app.include_router(product_api.router)
app.include_router(plant_api.router)
app.include_router(dealer_signup_api.router)
app.include_router(b2b_admin_api.router)
app.include_router(b2b_cart_api.router)
app.include_router(b2b_dealer_api.router)
app.include_router(b2b_order_api.router)
app.include_router(b2b_dashboard_api.router)
app.include_router(coin_api.router)

from .admin import admin
admin.mount_to(app)

@app.get("/")
def read_root():
    return {"message": "Vega test Track MongoDB Backend fvgh is running. mohan 12345 "}
'''source venv/bin/activate
uvicorn app.main:app --reload'''