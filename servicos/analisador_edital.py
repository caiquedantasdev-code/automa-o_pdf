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

    @staticmethod
    def _formatar_data_extensa(dia: str, mes: str, ano: str) -> str:
        meses = {"janeiro":"01", "fevereiro":"02", "marco":"03", "abril":"04", "maio":"05", "junho":"06", "julho":"07", "agosto":"08", "setembro":"09", "outubro":"10", "novembro":"11", "dezembro":"12"}
        return f"{int(dia):02d}/{meses[mes]}/{ano}"

    @classmethod
    def _datas_encontradas(cls, texto: str) -> list[tuple[int, str]]:
        resultados = []
        padroes = [
            r"\b(\d{1,2})\s+de\s+(janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+(?:de\s+)?(\d{4})\b",
            r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b",
            r"\b(\d{1,2})[.-](\d{1,2})[.-](\d{4})\b",
        ]
        for indice, padrao in enumerate(padroes):
            for encontrado in re.finditer(padrao, texto):
                if indice == 0:
                    data = cls._formatar_data_extensa(*encontrado.groups())
                else:
                    dia, mes, ano = encontrado.groups()
                    data = f"{int(dia):02d}/{int(mes):02d}/{ano}"
                resultados.append((encontrado.start(), data))
        return resultados

    @classmethod
    def _encontrar_data(cls, texto: str) -> str:
        candidatos = cls._datas_encontradas(texto)
        if not candidatos:
            return "Não identificado"

        marcadores = [
            "inicio da sessao", "sessao publica", "abertura da sessao",
            "abertura das propostas", "data e horario para recebimento das propostas",
        ]
        melhor = None
        for posicao, data in candidatos:
            contexto = texto[max(0, posicao - 350):posicao + 180]
            pontuacao = sum(10 for marcador in marcadores if marcador in contexto)
            if "assinatura" in contexto or "publicado" in contexto:
                pontuacao -= 4
            candidato = (pontuacao, -posicao, data)
            if melhor is None or candidato > melhor:
                melhor = candidato
        return melhor[2]

    @classmethod
    def _encontrar_horario(cls, texto: str) -> str:
        # Aceita 08:30, 08h30, 08h30min, 08h30minutos e 08 horas.
        padrao = re.compile(r"\b(\d{1,2})\s*(?::|h)(\d{2})\s*(?:min(?:utos)?|hs?|horas?)?\b")
        candidatos = [(m.start(), f"{int(m.group(1)):02d}:{m.group(2)}") for m in padrao.finditer(texto)]
        if not candidatos:
            return "Não identificado"

        marcadores = ["inicio da sessao", "sessao publica", "abertura da sessao"]
        melhor = None
        for posicao, horario in candidatos:
            contexto = texto[max(0, posicao - 300):posicao + 140]
            pontuacao = sum(10 for marcador in marcadores if marcador in contexto)
            if "abertura das propostas" in contexto:
                pontuacao += 4
            if "recebimento das propostas" in contexto:
                pontuacao -= 2
            candidato = (pontuacao, -posicao, horario)
            if melhor is None or candidato > melhor:
                melhor = candidato
        return melhor[2]

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
        if "menor preco por lote" in texto: encontrados.append("Menor preço por lote")
        if "menor preco global" in texto: encontrados.append("Menor preço global")
        if "menor preco por item" in texto: encontrados.append("Menor preço por item")
        if "menor preco" in texto and not encontrados: encontrados.append("Menor preço")
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
            ("Registro ANVISA", ["registro anvisa", "registro na anvisa", "registro sanitario"]),
            ("AFE ANVISA", ["autorizacao de funcionamento", "afe anvisa", "afe da anvisa"]),
            ("Alvará/Licença Sanitária", ["alvara sanitario", "licenca sanitaria"]),
            ("Autorização Especial", ["autorizacao especial"]),
            ("Amostra", ["apresentacao de amostra", "exigencia de amostra"]),
            ("Seguro-garantia", ["seguro-garantia", "seguro garantia"]),
            ("Garantia contratual", ["garantia contratual", "garantia de execucao"]),
            ("Atestado de capacidade técnica", ["atestado de capacidade tecnica"]),
            ("Balanço patrimonial", ["balanco patrimonial"]),
        ]
        resultado = []
        for nome, termos in regras:
            trecho = self._trecho(texto, termos)
            resultado.append({"nome": nome, "status": "Identificado" if trecho else "Não identificado", "trecho": trecho})
        return resultado

    def _fontes_relevantes(self, paginas: list[dict]) -> list[dict]:
        termos = ["termo de referencia", "habilitacao", "proposta", "amostra", "garantia", "anvisa", "inicio da sessao", "abertura das propostas"]
        fontes = []
        for pagina in paginas:
            texto_normalizado = self._normalizar(pagina["texto"])
            if any(self._normalizar(termo) in texto_normalizado for termo in termos):
                fontes.append({"pagina": pagina["pagina"], "motivo": "Contém termos relevantes para a análise"})
        return fontes[:20]
