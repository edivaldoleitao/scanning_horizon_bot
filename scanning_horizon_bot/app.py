# app.py
from html import escape

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from scanner import horizon_scan

app = FastAPI()


def render_page(results=None, query="", theme="", term="", limit=10, error=""):
    results = results or []

    rows = ""
    for i, item in enumerate(results, start=1):
        rows += f"""
        <tr>
            <td>{i}</td>
            <td>{escape(item.get("title", "—"))}</td>
            <td>{escape(item.get("source", "—"))}</td>
            <td>{escape(item.get("published", "—"))}</td>
            <td>{escape(item.get("summary", "—"))}</td>
            <td>
                <a href="{escape(item.get("link", "#"), quote=True)}" target="_blank" rel="noopener">
                    Abrir
                </a>
            </td>
        </tr>
        """

    query_html = f"""
        <p class="query-line">Consulta: <strong>{escape(query)}</strong></p>
    """ if query else ""

    error_html = f"""
        <p class="error">{escape(error)}</p>
    """ if error else ""

    table_html = f"""
    <div class="table-wrap">
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Título</th>
                    <th>Fonte</th>
                    <th>Publicado</th>
                    <th>Resumo</th>
                    <th>Link</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
    </div>
    """ if results else ""

    return f"""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Horizon Scanning Bot</title>
        <style>
            body {{
                margin: 0;
                font-family: Arial, sans-serif;
                background: #0f172a;
                color: #e5e7eb;
            }}
            .container {{
                width: 92%;
                max-width: 1300px;
                margin: 0 auto;
                padding: 32px 0 60px;
            }}
            h1 {{
                text-align: center;
                margin-bottom: 28px;
                color: #ffffff;
            }}
            .search-form {{
                display: grid;
                grid-template-columns: 2fr 2fr 120px auto;
                gap: 12px;
                align-items: end;
                margin-bottom: 18px;
            }}
            .field {{
                display: flex;
                flex-direction: column;
                gap: 6px;
            }}
            .field label {{
                font-size: 14px;
                color: #cbd5e1;
            }}
            .field input {{
                padding: 14px 12px;
                border: 1px solid #334155;
                border-radius: 10px;
                background: #ffffff;
                color: #111827;
                outline: none;
            }}
            .field.small input {{
                text-align: center;
            }}
            button {{
                padding: 14px 18px;
                border: none;
                border-radius: 10px;
                background: #2563eb;
                color: white;
                cursor: pointer;
                font-weight: 600;
            }}
            button:hover {{
                background: #1d4ed8;
            }}
            .query-line {{
                margin: 16px 0 18px;
                color: #cbd5e1;
            }}
            .error {{
                margin: 12px 0;
                color: #fca5a5;
                font-weight: 700;
            }}
            .table-wrap {{
                overflow-x: auto;
                background: #111827;
                border: 1px solid #1f2937;
                border-radius: 14px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                min-width: 1100px;
            }}
            th, td {{
                padding: 14px 12px;
                border-bottom: 1px solid #1f2937;
                vertical-align: top;
                text-align: left;
            }}
            th {{
                background: #1f2937;
                color: #fff;
                position: sticky;
                top: 0;
            }}
            td {{
                color: #e5e7eb;
            }}
            a {{
                color: #60a5fa;
                text-decoration: none;
            }}
            a:hover {{
                text-decoration: underline;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Horizon Scanning Bot</h1>

            <form action="/" method="POST" class="search-form">
                <div class="field">
                    <label for="theme">Tema</label>
                    <input id="theme" name="theme" type="text" placeholder="Ex.: internet das coisas" value="{escape(theme)}" required>
                </div>

                <div class="field">
                    <label for="term">Termo complementar</label>
                    <input id="term" name="term" type="text" placeholder="Ex.: crianças" value="{escape(term)}">
                </div>

                <div class="field small">
                    <label for="limit">Limite</label>
                    <input id="limit" name="limit" type="number" min="1" max="50" value="{int(limit)}">
                </div>

                <button type="submit">Escanear</button>
            </form>

            {error_html}
            {query_html}
            {table_html}
        </div>
    </body>
    </html>
    """


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return HTMLResponse(
        render_page(
            results=[],
            query="",
            theme="",
            term="",
            limit=10,
            error=""
        )
    )


@app.post("/", response_class=HTMLResponse)
async def run_scan(request: Request):
    form = await request.form()

    theme = str(form.get("theme", "")).strip()
    term = str(form.get("term", "")).strip()
    limit_raw = str(form.get("limit", "10")).strip()

    try:
        limit = int(limit_raw)
        if limit < 1:
            limit = 10
        if limit > 50:
            limit = 50
    except ValueError:
        limit = 10

    if not theme:
        return HTMLResponse(
            render_page(
                results=[],
                query="",
                theme=theme,
                term=term,
                limit=limit,
                error="O campo Tema é obrigatório."
            )
        )

    try:
        results = horizon_scan(theme=theme, term=term, limit=limit)
    except Exception as e:
        return HTMLResponse(
            render_page(
                results=[],
                query="",
                theme=theme,
                term=term,
                limit=limit,
                error=f"Erro ao buscar dados: {e}"
            )
        )

    query = " ".join(part for part in [theme, term] if part)

    return HTMLResponse(
        render_page(
            results=results,
            query=query,
            theme=theme,
            term=term,
            limit=limit,
            error=""
        )
    )