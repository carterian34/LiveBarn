from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from api.routers.v1 import auth, livebarn
import uvicorn
import webbrowser

templates = Jinja2Templates(directory="templates")
app = FastAPI()
app.include_router(auth.router, prefix="/api/v1")
app.include_router(livebarn.router, prefix="/api/v1")

@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/main.js", response_class=HTMLResponse)
async def main_js():
    return FileResponse('./static/main.js')

if __name__ == "__main__":
    webbrowser.open("http://127.0.0.1:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
