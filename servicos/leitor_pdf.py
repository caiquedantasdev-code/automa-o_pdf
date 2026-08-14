from pathlib import Path

import fitz


class LeitorPDF:
    """Responsável por extrair texto de editais em PDF."""

    def extrair(self, caminho: str | Path) -> list[dict]:
        caminho = Path(caminho)
        paginas = []

        with fitz.open(caminho) as documento:
            for numero, pagina in enumerate(documento, start=1):
                texto = pagina.get_text("text").strip()
                paginas.append({
                    "pagina": numero,
                    "texto": texto,
                })

        return paginas
