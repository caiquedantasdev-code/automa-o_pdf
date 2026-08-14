from pathlib import Path

from flask import Flask, render_template, request
from werkzeug.utils import secure_filename

from servicos.analisador_edital import AnalisadorEdital
from servicos.leitor_pdf import LeitorPDF


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

PASTA_UPLOADS = Path("uploads")
PASTA_UPLOADS.mkdir(exist_ok=True)

leitor = LeitorPDF()
analisador = AnalisadorEdital()


@app.get("/")
def inicio():
    return render_template("inicio.html")


@app.post("/analisar")
def analisar():
    arquivo = request.files.get("edital")

    if not arquivo or not arquivo.filename:
        return render_template("inicio.html", erro="Selecione um arquivo PDF para iniciar a análise."), 400

    if not arquivo.filename.lower().endswith(".pdf"):
        return render_template("inicio.html", erro="O arquivo precisa estar no formato PDF."), 400

    nome_seguro = secure_filename(arquivo.filename)
    caminho = PASTA_UPLOADS / nome_seguro
    arquivo.save(caminho)

    try:
        paginas = leitor.extrair(caminho)
        resultado = analisador.analisar(paginas, nome_seguro)
        return render_template("resultado.html", resultado=resultado)
    except Exception as exc:
        return render_template("inicio.html", erro=f"Não foi possível analisar o edital: {exc}"), 500


if __name__ == "__main__":
    app.run(debug=True)
