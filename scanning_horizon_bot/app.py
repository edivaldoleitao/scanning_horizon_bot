from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from scanner import horizon_scan

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "results": None
        }
    )


@app.post("/", response_class=HTMLResponse)
async def run_scan(request: Request, keyword: str = Form(...)):
    results = horizon_scan(keyword)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "results": results,
            "keyword": keyword
        }
    )