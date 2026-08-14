import hmac
import os
import secrets
import uuid
from pathlib import Path

import fitz
from flask import Flask, render_template, request, session
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from servicos.analisador_edital import AnalisadorEdital
from servicos.leitor_pdf import LeitorPDF


app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    MAX_CONTENT_LENGTH=25 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SEGURO", "0") == "1",
)

PASTA_UPLOADS = Path("uploads")
PASTA_UPLOADS.mkdir(exist_ok=True)
TAMANHO_MAXIMO = 25 * 1024 * 1024
PAGINAS_MAXIMAS = 300

leitor = LeitorPDF(limite_paginas=PAGINAS_MAXIMAS)
analisador = AnalisadorEdital()


def _token_csrf() -> str:
    token = session.get("token_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["token_csrf"] = token
    return token


def _csrf_valido(token_recebido: str | None) -> bool:
    token_salvo = session.get("token_csrf", "")
    return bool(token_recebido) and hmac.compare_digest(token_recebido, token_salvo)


def _arquivo_pdf_valido(caminho: Path) -> bool:
    """Valida assinatura, estrutura e estado do PDF antes da análise."""
    with caminho.open("rb") as arquivo:
        assinatura = arquivo.read(5)
    if assinatura != b"%PDF-":
        return False

    try:
        with fitz.open(caminho) as documento:
            if documento.is_encrypted or documento.page_count < 1:
                return False
            if documento.page_count > PAGINAS_MAXIMAS:
                return False
    except (fitz.FileDataError, RuntimeError, ValueError):
        return False
    return True


@app.after_request
def aplicar_cabecalhos_seguranca(resposta):
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["X-Frame-Options"] = "DENY"
    resposta.headers["Referrer-Policy"] = "no-referrer"
    resposta.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    resposta.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


@app.get("/")
def inicio():
    return render_template("inicio.html", token_csrf=_token_csrf())


@app.errorhandler(RequestEntityTooLarge)
def arquivo_grande(_erro):
    return render_template(
        "inicio.html",
        erro="O arquivo excede o limite de 25 MB.",
        token_csrf=_token_csrf(),
    ), 413


@app.post("/analisar")
def analisar():
    if not _csrf_valido(request.form.get("token_csrf")):
        return render_template(
            "inicio.html",
            erro="Não foi possível validar a solicitação. Atualize a página e tente novamente.",
            token_csrf=_token_csrf(),
        ), 400

    arquivo = request.files.get("edital")
    if not arquivo or not arquivo.filename:
        return render_template("inicio.html", erro="Selecione um arquivo PDF para iniciar a análise.", token_csrf=_token_csrf()), 400

    nome_original = secure_filename(arquivo.filename)
    if not nome_original or not nome_original.lower().endswith(".pdf"):
        return render_template("inicio.html", erro="Envie um arquivo com extensão PDF.", token_csrf=_token_csrf()), 400

    nome_interno = f"{uuid.uuid4().hex}.pdf"
    caminho = PASTA_UPLOADS / nome_interno

    try:
        arquivo.save(caminho)
        if caminho.stat().st_size > TAMANHO_MAXIMO or not _arquivo_pdf_valido(caminho):
            return render_template(
                "inicio.html",
                erro="O arquivo não é um PDF válido, está protegido ou excede os limites de análise.",
                token_csrf=_token_csrf(),
            ), 400

        paginas = leitor.extrair(caminho)
        resultado = analisador.analisar(paginas, nome_original)
        return render_template("resultado.html", resultado=resultado)
    except (OSError, fitz.FileDataError, RuntimeError):
        return render_template(
            "inicio.html",
            erro="Não foi possível processar este PDF. Tente outro arquivo.",
            token_csrf=_token_csrf(),
        ), 400
    finally:
        try:
            caminho.unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
