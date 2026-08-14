import unittest

from servicos.analisador_edital import AnalisadorEdital


class TesteAnalisadorEdital(unittest.TestCase):
    def setUp(self):
        self.analisador = AnalisadorEdital()

    def test_identifica_dados_basicos(self):
        paginas = [{
            "pagina": 1,
            "texto": "Pregão Eletrônico. Sessão em 25/08/2026 às 09:30. Plataforma BLL. Menor preço por lote. Sistema de Registro de Preços. Proposta válida por 60 dias."
        }]
        resultado = self.analisador.analisar(paginas, "edital.pdf")
        self.assertEqual(resultado["informacoes"]["data"], "25/08/2026")
        self.assertEqual(resultado["informacoes"]["horario"], "09:30")
        self.assertEqual(resultado["informacoes"]["plataforma"], "BLL")
        self.assertEqual(resultado["informacoes"]["modalidade"], "Pregão Eletrônico")
        self.assertEqual(resultado["informacoes"]["criterio"], "Menor preço por lote")
        self.assertEqual(resultado["informacoes"]["registro_precos"], "Sim")
        self.assertEqual(resultado["informacoes"]["validade_proposta"], "60 dias")

    def test_identifica_data_extensa_e_horario_da_sessao(self):
        paginas = [{
            "pagina": 1,
            "texto": "Macarani, 05 de agosto de 2026. XII. Sites de acesso ao edital, data e horário para recebimento das propostas e início da sessão pública. Recebimento das propostas: A partir: 06 de agosto de 2026 Horário: 08h00min. Abertura das Propostas no dia: 17 de agosto 2026 Horário: 08h00min. XIV. Início da sessão 17 de agosto de 2026 Horário: 08h30min."
        }]
        resultado = self.analisador.analisar(paginas, "Edital80501_Macarani.pdf")
        self.assertEqual(resultado["informacoes"]["data"], "17/08/2026")
        self.assertEqual(resultado["informacoes"]["horario"], "08:30")

    def test_nao_inventa_exigencia(self):
        resultado = self.analisador.analisar([{"pagina": 1, "texto": "Pregão Eletrônico sem exigências sanitárias."}], "edital.pdf")
        exigencias = {item["nome"]: item["status"] for item in resultado["exigencias"]}
        self.assertEqual(exigencias["Registro ANVISA"], "Não identificado")
        self.assertEqual(exigencias["Seguro-garantia"], "Não identificado")


if __name__ == "__main__":
    unittest.main()
