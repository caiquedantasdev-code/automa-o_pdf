from pathlib import Path

import fitz


class LeitorPDF:
    """Extrai texto de editais com limites para reduzir consumo abusivo."""

    def __init__(self, limite_paginas: int = 300):
        self.limite_paginas = limite_paginas

    def extrair(self, caminho: str | Path) -> list[dict]:
        caminho = Path(caminho)
        paginas = []

        with fitz.open(caminho) as documento:
            if documento.is_encrypted:
                raise ValueError("PDF protegido por senha não pode ser analisado.")
            if documento.page_count > self.limite_paginas:
                raise ValueError("PDF excede o limite de páginas para análise.")

            for numero, pagina in enumerate(documento, start=1):
                texto = pagina.get_text("text").strip()
                paginas.append({
                    "pagina": numero,
                    "texto": texto,
                })

        return paginas
