from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.vapi_webhook import router as vapi_router
from backend.api.calls import router as calls_router
from backend.api.health import router as health_router

app = FastAPI(title="Observe Insurance VoiceAI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vapi_router, prefix="/webhook")
app.include_router(calls_router, prefix="/api")
app.include_router(health_router)
