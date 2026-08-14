import re
import unicodedata
from typing import Iterable


class AnalisadorEdital:
    """Extrai sinais objetivos do edital sem inventar exigências ausentes."""

    def analisar(self, paginas: list[dict], nome_arquivo: str) -> dict:
        texto_completo = "\n".join(pagina["texto"] for pagina in paginas)
        normalizado = self._normalizar(texto_completo)

        return {
            "arquivo": nome_arquivo,
            "paginas": len(paginas),
            "informacoes": {
                "data": self._encontrar_data(normalizado),
                "horario": self._encontrar_horario(normalizado),
                "plataforma": self._encontrar_plataforma(normalizado),
                "modalidade": self._encontrar_modalidade(normalizado),
                "criterio": self._encontrar_criterio(normalizado),
                "registro_precos": self._sim_ou_nao(normalizado, ["registro de precos", "sistema de registro de precos"]),
                "validade_proposta": self._encontrar_validade(normalizado),
            },
            "exigencias": self._mapear_exigencias(normalizado),
            "fontes": self._fontes_relevantes(paginas),
        }

    @staticmethod
    def _normalizar(texto: str) -> str:
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(c for c in texto if not unicodedata.combining(c))
        return re.sub(r"\s+", " ", texto).strip().lower()

    @staticmethod
    def _trecho(texto: str, termos: Iterable[str], janela: int = 180) -> str | None:
        for termo in termos:
            termo_normalizado = AnalisadorEdital._normalizar(termo)
            posicao = texto.find(termo_normalizado)
            if posicao >= 0:
                inicio = max(0, posicao - janela)
                fim = min(len(texto), posicao + len(termo_normalizado) + janela)
                return texto[inicio:fim].strip()
        return None

    def _encontrar_data(self, texto: str) -> str:
        padroes = [r"\b(\d{1,2}/\d{1,2}/\d{4})\b", r"\b(\d{1,2}[.-]\d{1,2}[.-]\d{4})\b"]
        for padrao in padroes:
            encontrado = re.search(padrao, texto)
            if encontrado:
                return encontrado.group(1)
        return "Não identificado"

    @staticmethod
    def _encontrar_horario(texto: str) -> str:
        encontrado = re.search(r"\b(\d{1,2}:\d{2})\s*(?:h|hs|horas)?\b", texto)
        return encontrado.group(1) if encontrado else "Não identificado"

    @staticmethod
    def _encontrar_plataforma(texto: str) -> str:
        plataformas = {"bll": "BLL", "bnc": "BNC Compras", "compras.gov": "Compras.gov.br", "comprasnet": "ComprasNet", "licitanet": "LicitaNet", "portal de compras publicas": "Portal de Compras Públicas"}
        for termo, nome in plataformas.items():
            if termo in texto:
                return nome
        return "Não identificada"

    @staticmethod
    def _encontrar_modalidade(texto: str) -> str:
        for termo, nome in [("pregao eletronico", "Pregão Eletrônico"), ("pregao presencial", "Pregão Presencial"), ("concorrencia eletronica", "Concorrência Eletrônica"), ("concorrencia presencial", "Concorrência Presencial")]:
            if termo in texto:
                return nome
        return "Não identificada"

    @staticmethod
    def _encontrar_criterio(texto: str) -> str:
        encontrados = []
        if "menor preco por lote" in texto:
            encontrados.append("Menor preço por lote")
        if "menor preco global" in texto:
            encontrados.append("Menor preço global")
        if "menor preco por item" in texto:
            encontrados.append("Menor preço por item")
        return " / ".join(encontrados) if encontrados else "Não identificado"

    @staticmethod
    def _encontrar_validade(texto: str) -> str:
        encontrado = re.search(r"validade.{0,100}?(\d{2,3})\s*dias", texto)
        return f"{encontrado.group(1)} dias" if encontrado else "Não identificada"

    @staticmethod
    def _sim_ou_nao(texto: str, termos: list[str]) -> str:
        return "Sim" if any(AnalisadorEdital._normalizar(termo) in texto for termo in termos) else "Não identificado"

    def _mapear_exigencias(self, texto: str) -> list[dict]:
        regras = [
            ("Registro ANVISA", ["registro anvisa", "registro na anvisa", "registro sanitário", "registro sanitario"]),
            ("AFE ANVISA", ["autorização de funcionamento", "afe anvisa", "afe da anvisa"]),
            ("Alvará/Licença Sanitária", ["alvará sanitário", "licença sanitária", "licenca sanitaria"]),
            ("Autorização Especial", ["autorização especial"]),
            ("Amostra", ["apresentação de amostra", "exigência de amostra"]),
            ("Seguro-garantia", ["seguro-garantia", "seguro garantia"]),
            ("Garantia contratual", ["garantia contratual", "garantia de execução"]),
            ("Atestado de capacidade técnica", ["atestado de capacidade técnica"]),
            ("Balanço patrimonial", ["balanço patrimonial"]),
        ]

        resultado = []
        for nome, termos in regras:
            trecho = self._trecho(texto, termos)
            resultado.append({"nome": nome, "status": "Identificado" if trecho else "Não identificado", "trecho": trecho})
        return resultado

    def _fontes_relevantes(self, paginas: list[dict]) -> list[dict]:
        termos = ["termo de referência", "habilitação", "proposta", "amostra", "garantia", "anvisa"]
        fontes = []
        for pagina in paginas:
            texto_normalizado = self._normalizar(pagina["texto"])
            if any(self._normalizar(termo) in texto_normalizado for termo in termos):
                fontes.append({"pagina": pagina["pagina"], "motivo": "Contém termos relevantes para a análise"})
        return fontes[:20]
