# app.py

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from scanner import horizon_scan
from html import escape
from datetime import datetime


app = FastAPI()


# =========================================================
# TEMPLATE HTML
# =========================================================

def render_page(
    results=None,
    radar=None,
    query="",
    theme="",
    terms_text="",
    source="both",
    start_date="",
    end_date="",
    error=""
):

    results = results or []

    radar = radar or {}

    rows = ""

    for i, item in enumerate(results, start=1):

        matched_terms = ", ".join(
            item.get(
                "matched_terms",
                []
            )
        )

        rows += f"""
        <tr>

            <td>{i}</td>

            <td>
                {escape(item.get("type", "—"))}
            </td>

            <td>
                {escape(item.get("title", "—"))}
            </td>

            <td>
                {escape(item.get("source", "—"))}
            </td>

            <td>
                {escape(item.get("authors", "—"))}
            </td>

            <td>
                {escape(item.get("published", "—"))}
            </td>

            <td>
                {item.get("score", 0)}
            </td>

            <td>
                {escape(matched_terms)}
            </td>

            <td>

                <a
                    href="{escape(item.get('link', '#'), quote=True)}"
                    target="_blank"
                    rel="noopener"
                >
                    Abrir
                </a>

            </td>

        </tr>
        """

    radar_html = ""

    if radar:

        radar_html = f"""

        <div class="radar-box">

            <h2>
                Radar de Sinais Fracos
            </h2>

            <div class="radar-grid">

                <div>
                    <strong>Classificação:</strong>
                    {radar.get("classification", "—")}
                </div>

                <div>
                    <strong>Índice:</strong>
                    {radar.get("weak_signal_index", 0)}
                </div>

                <div>
                    <strong>Resultados:</strong>
                    {radar.get("results_count", 0)}
                </div>

                <div>
                    <strong>Crescimento 7→30 dias:</strong>
                    {radar.get("growth_7_30", 0)}%
                </div>

                <div>
                    <strong>Crescimento 30→90 dias:</strong>
                    {radar.get("growth_30_90", 0)}%
                </div>

                <div>
                    <strong>Diversidade de Fontes:</strong>
                    {radar.get("source_diversity", 0)}
                </div>

                <div>
                    <strong>Score Médio:</strong>
                    {radar.get("average_score", 0)}
                </div>

            </div>

        </div>
        """

    table_html = ""

    if results:

        table_html = f"""

        <div class="table-wrap">

            <table>

                <thead>

                    <tr>

                        <th>#</th>

                        <th>Tipo</th>

                        <th>Título</th>

                        <th>Fonte</th>

                        <th>Autores</th>

                        <th>Publicado</th>

                        <th>Score</th>

                        <th>Termos encontrados</th>

                        <th>Link</th>

                    </tr>

                </thead>

                <tbody>

                    {rows}

                </tbody>

            </table>

        </div>
        """

    error_html = ""

    if error:

        error_html = f"""

        <div class="error">

            {escape(error)}

        </div>
        """

    query_html = ""

    if query:

        query_html = f"""

        <div class="query-box">

            <strong>Consulta:</strong>

            {escape(query)}

        </div>
        """

    return f"""
    <!DOCTYPE html>

    <html lang="pt-br">

    <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>
            Horizon Scanning Bot
        </title>

        <style>

            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                background: #0f172a;
                color: #e2e8f0;
                font-family: Arial, sans-serif;
            }}

            .container {{
                width: 95%;
                max-width: 1500px;
                margin: auto;
                padding: 30px 0 60px;
            }}

            h1 {{
                text-align: center;
                color: white;
                margin-bottom: 30px;
            }}

            .search-form {{

                display: grid;

                grid-template-columns:
                    2fr
                    2fr
                    1fr
                    1fr
                    1fr
                    auto;

                gap: 14px;

                align-items: end;

                margin-bottom: 24px;
            }}

            .field {{
                display: flex;
                flex-direction: column;
                gap: 6px;
            }}

            .field label {{
                font-size: 14px;
            }}

            .field input,
            .field select {{

                padding: 14px;

                border-radius: 10px;

                border: 1px solid #334155;

                outline: none;
            }}

            button {{

                padding: 14px 22px;

                border: none;

                border-radius: 10px;

                background: #2563eb;

                color: white;

                cursor: pointer;

                font-weight: bold;
            }}

            button:hover {{
                background: #1d4ed8;
            }}

            .table-wrap {{

                overflow-x: auto;

                border-radius: 12px;

                border: 1px solid #1f2937;

                background: #111827;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                min-width: 1200px;
            }}

            th,
            td {{

                padding: 14px 12px;

                border-bottom: 1px solid #1f2937;

                text-align: left;

                vertical-align: top;
            }}

            th {{
                background: #1f2937;
                color: white;
            }}

            tr:hover {{
                background: #172033;
            }}

            a {{
                color: #60a5fa;
                text-decoration: none;
            }}

            a:hover {{
                text-decoration: underline;
            }}

            .query-box {{
                margin-bottom: 18px;
            }}

            .error {{

                background: #7f1d1d;

                color: #fecaca;

                padding: 14px;

                border-radius: 10px;

                margin-bottom: 20px;
            }}

            .radar-box {{

                background: #111827;

                border: 1px solid #1f2937;

                border-radius: 12px;

                padding: 20px;

                margin-bottom: 24px;
            }}

            .radar-grid {{

                display: grid;

                grid-template-columns:
                    repeat(auto-fit, minmax(220px, 1fr));

                gap: 12px;

                margin-top: 16px;
            }}

            @media (max-width: 1200px) {{

                .search-form {{
                    grid-template-columns: 1fr 1fr;
                }}

                button {{
                    grid-column: 1 / -1;
                }}
            }}

        </style>

    </head>

    <body>

        <div class="container">

            <h1>
                Horizon Scanning Bot
            </h1>

            <form
                action="/"
                method="POST"
                class="search-form"
            >

                <div class="field">

                    <label>
                        Tema
                    </label>

                    <input
                        type="text"
                        name="theme"
                        placeholder="Ex.: inteligência artificial"
                        value="{escape(theme)}"
                        required
                    >

                </div>

                <div class="field">

                    <label>
                        Termos complementares
                    </label>

                    <input
                        type="text"
                        name="terms"
                        placeholder="Ex.: crianças, brinquedos"
                        value="{escape(terms_text)}"
                    >

                </div>

                <div class="field">

                    <label>
                        Fonte
                    </label>

                    <select name="source">

                        <option
                            value="both"
                            {"selected" if source == "both" else ""}
                        >
                            Ambos
                        </option>

                        <option
                            value="google"
                            {"selected" if source == "google" else ""}
                        >
                            Google News
                        </option>

                        <option
                            value="scholar"
                            {"selected" if source == "scholar" else ""}
                        >
                            Google Scholar
                        </option>

                    </select>

                </div>

                <div class="field">

                    <label>
                        Data inicial
                    </label>

                    <input
                        type="date"
                        name="start_date"
                        value="{escape(start_date)}"
                    >

                </div>

                <div class="field">

                    <label>
                        Data final
                    </label>

                    <input
                        type="date"
                        name="end_date"
                        value="{escape(end_date)}"
                    >

                </div>

                <button type="submit">
                    Escanear
                </button>

            </form>

            {error_html}

            {query_html}

            {radar_html}

            {table_html}

        </div>

    </body>

    </html>
    """


# =========================================================
# ROTAS
# =========================================================

@app.get("/", response_class=HTMLResponse)
async def home():

    return HTMLResponse(
        render_page()
    )


@app.post("/", response_class=HTMLResponse)
async def scan(request: Request):

    form = await request.form()

    theme = str(
        form.get("theme", "")
    ).strip()

    terms_text = str(
        form.get("terms", "")
    ).strip()

    source = str(
        form.get("source", "both")
    ).strip()

    start_date_raw = str(
        form.get("start_date", "")
    ).strip()

    end_date_raw = str(
        form.get("end_date", "")
    ).strip()

    start_date = None
    end_date = None

    try:

        if start_date_raw:

            start_date = datetime.strptime(
                start_date_raw,
                "%Y-%m-%d"
            )

        if end_date_raw:

            end_date = datetime.strptime(
                end_date_raw,
                "%Y-%m-%d"
            )

    except Exception:

        return HTMLResponse(

            render_page(
                error="Datas inválidas."
            )

        )

    if not theme:

        return HTMLResponse(

            render_page(
                error="O campo Tema é obrigatório."
            )

        )

    try:

        scan_data = horizon_scan(

            theme=theme,

            extra_terms=terms_text,

            source=source,

            start_date=start_date,

            end_date=end_date

        )

    except Exception as e:

        return HTMLResponse(

            render_page(
                error=f"Erro ao buscar dados: {e}"
            )

        )

    query = " ".join(
        [theme, terms_text]
    )

    return HTMLResponse(

        render_page(

            results=scan_data["results"],

            radar=scan_data["radar"],

            query=query,

            theme=theme,

            terms_text=terms_text,

            source=source,

            start_date=start_date_raw,

            end_date=end_date_raw

        )

    )