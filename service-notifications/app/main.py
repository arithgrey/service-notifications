from fastapi import FastAPI
from app.routers.notify import router

app = FastAPI(title="service-notifications")
app.include_router(router)
