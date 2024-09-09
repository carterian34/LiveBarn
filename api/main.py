from fastapi import FastAPI, Body, Depends
from fastapi.responses import JSONResponse
from api.routers.v1 import auth, livebarn
import uvicorn
import requests
import json
from dependencies import has_credentials
from typing import Annotated

app = FastAPI()
app.include_router(auth.router, prefix="/api/v1")
app.include_router(livebarn.router, prefix="/api/v1")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
