import re
import unicodedata
from typing import Iterable


class AnalisadorEdital:
    """Extrai sinais objetivos do edital sem escolher datas por posição no PDF."""

    _PADRAO_DATA = re.compile(
        r"\b(\d{1,2})\s+de\s+(janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+(?:de\s+)?(\d{4})\b"
        r"|\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b"
    )
    _PADRAO_HORA = re.compile(
        r"\b(\d{1,2})\s*(?::|h)\s*(\d{2})\s*(?:min(?:utos)?|hs?|horas?)?\b",
        re.IGNORECASE,
    )

    def analisar(self, paginas: list[dict], nome_arquivo: str) -> dict:
        texto_completo = "\n".join(pagina["texto"] for pagina in paginas)
        normalizado = self._normalizar(texto_completo)
        data, horario = self._encontrar_sessao(normalizado)
        return {
            "arquivo": nome_arquivo,
            "paginas": len(paginas),
            "informacoes": {
                "data": data,
                "horario": horario,
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
    def _formatar_data(dia: str, mes: str, ano: str) -> str | None:
        try:
            if mes.isdigit():
                mes_numero = int(mes)
            else:
                meses = {
                    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4,
                    "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
                    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
                }
                mes_numero = meses[mes]
            if not 1 <= int(dia) <= 31 or not 1900 <= int(ano) <= 2200 or not 1 <= mes_numero <= 12:
                return None
            return f"{int(dia):02d}/{mes_numero:02d}/{int(ano):04d}"
        except (ValueError, KeyError):
            return None

    @classmethod
    def _datas_encontradas(cls, texto: str) -> list[tuple[int, str]]:
        resultados = []
        for encontrado in cls._PADRAO_DATA.finditer(texto):
            grupos = encontrado.groups()
            if grupos[0] is not None:
                data = cls._formatar_data(grupos[0], grupos[1], grupos[2])
            else:
                data = cls._formatar_data(grupos[3], grupos[4], grupos[5])
            if data:
                resultados.append((encontrado.start(), data))
        return resultados

    @classmethod
    def _extrair_primeira_data(cls, trecho: str) -> str | None:
        datas = cls._datas_encontradas(trecho)
        return datas[0][1] if datas else None

    @classmethod
    def _extrair_primeiro_horario(cls, trecho: str) -> str | None:
        encontrado = cls._PADRAO_HORA.search(trecho)
        if not encontrado:
            return None
        return f"{int(encontrado.group(1)):02d}:{encontrado.group(2)}"

    @classmethod
    def _encontrar_sessao(cls, texto: str) -> tuple[str, str]:
        """Procura a data/horário do evento da sessão antes de considerar datas genéricas."""
        # 1. Rótulos explícitos são a fonte mais confiável.
        data = cls._extrair_rotulo(texto, r"data\s+da\s+sessao")
        horario = cls._extrair_horario_rotulo(texto, r"horario\s+da\s+sessao")
        if data or horario:
            return data or "Não identificado", horario or cls._extrair_horario_proximo(texto, data)

        # 2. Eventos de abertura/disputa/início da sessão.
        marcadores = [
            r"inicio\s+da\s+sessao",
            r"sessao\s+publica",
            r"abertura\s+das\s+propostas",
            r"inicio\s+da\s+disputa",
            r"sessao\s+de\s+disputa",
        ]
        for marcador in marcadores:
            for encontrado in re.finditer(marcador, texto):
                bloco = texto[encontrado.end():encontrado.end() + 350]
                data_bloco = cls._extrair_primeira_data(bloco)
                horario_bloco = cls._extrair_primeiro_horario(bloco)
                if data_bloco or horario_bloco:
                    return data_bloco or "Não identificado", horario_bloco or "Não identificado"

        # 3. Frases comuns como “sessão em 25/08/2026 às 09:30”.
        padrao_frase = re.compile(
            r"(?:sessao|abertura|disputa)[^.;]{0,120}?"
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{1,2}\s+de\s+[a-z]+\s+(?:de\s+)?\d{4})"
            r"[^.;]{0,80}?"
            r"(?:as|a|horario)?\s*(\d{1,2}\s*(?::|h)\s*\d{2})",
        )
        encontrado = padrao_frase.search(texto)
        if encontrado:
            data = cls._extrair_primeira_data(encontrado.group(0))
            horario = cls._extrair_primeiro_horario(encontrado.group(0))
            if data or horario:
                return data or "Não identificado", horario or "Não identificado"

        return "Não identificado", "Não identificado"

    @classmethod
    def _extrair_rotulo(cls, texto: str, rotulo: str) -> str | None:
        padrao = re.compile(rf"{rotulo}\s*[:\-]?\s*(.{{0,90}})", re.IGNORECASE)
        for encontrado in padrao.finditer(texto):
            data = cls._extrair_primeira_data(encontrado.group(1))
            if data:
                return data
        return None

    @classmethod
    def _extrair_horario_rotulo(cls, texto: str, rotulo: str) -> str | None:
        padrao = re.compile(rf"{rotulo}\s*[:\-]?\s*(.{{0,90}})", re.IGNORECASE)
        for encontrado in padrao.finditer(texto):
            horario = cls._extrair_primeiro_horario(encontrado.group(1))
            if horario:
                return horario
        return None

    @classmethod
    def _extrair_horario_proximo(cls, texto: str, data: str | None) -> str | None:
        if not data:
            return None
        posicao = texto.find(data.lower())
        if posicao < 0:
            return None
        return cls._extrair_primeiro_horario(texto[posicao:posicao + 180])

    @staticmethod
    def _encontrar_plataforma(texto: str) -> str:
        plataformas = {
            "bll": "BLL", "bnc": "BNC Compras", "compras.gov": "Compras.gov.br",
            "comprasnet": "ComprasNet", "licitanet": "LicitaNet",
            "portal de compras publicas": "Portal de Compras Públicas",
        }
        for termo, nome in plataformas.items():
            if termo in texto:
                return nome
        return "Não identificada"

    @staticmethod
    def _encontrar_modalidade(texto: str) -> str:
        for termo, nome in [
            ("pregao eletronico", "Pregão Eletrônico"),
            ("pregao presencial", "Pregão Presencial"),
            ("concorrencia eletronica", "Concorrência Eletrônica"),
            ("concorrencia presencial", "Concorrência Presencial"),
        ]:
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
        if "menor preco" in texto and not encontrados:
            encontrados.append("Menor preço")
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
        termos = ["termo de referencia", "habilitacao", "proposta", "amostra", "garantia", "anvisa", "inicio da sessao", "abertura das propostas", "data da sessao"]
        fontes = []
        for pagina in paginas:
            texto_normalizado = self._normalizar(pagina["texto"])
            if any(self._normalizar(termo) in texto_normalizado for termo in termos):
                fontes.append({"pagina": pagina["pagina"], "motivo": "Contém termos relevantes para a análise"})
        return fontes[:20]
