import io
import unittest
from pathlib import Path

import fitz

from app import PASTA_UPLOADS, app


class TesteSegurancaAplicacao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(TESTING=True, SECRET_KEY="chave-de-teste")
        cls.cliente = app.test_client()

    def tearDown(self):
        for arquivo in PASTA_UPLOADS.glob("*.pdf"):
            arquivo.unlink(missing_ok=True)

    def _token(self):
        resposta = self.cliente.get("/")
        self.assertEqual(resposta.status_code, 200)
        with self.cliente.session_transaction() as sessao:
            return sessao["token_csrf"]

    def _pdf_valido(self):
        documento = fitz.open()
        pagina = documento.new_page()
        pagina.insert_text((72, 72), "Pregão Eletrônico. Início da sessão 17 de agosto 2026 às 08h30min.")
        dados = documento.tobytes()
        documento.close()
        return dados

    def test_exige_token_csrf(self):
        resposta = self.cliente.post(
            "/analisar",
            data={"edital": (io.BytesIO(self._pdf_valido()), "edital.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertIn(b"validar a solicita", resposta.data)

    def test_rejeita_arquivo_com_extensao_pdf_que_nao_e_pdf(self):
        token = self._token()
        resposta = self.cliente.post(
            "/analisar",
            data={
                "token_csrf": token,
                "edital": (io.BytesIO(b"nao sou um pdf"), "arquivo.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertIn(b"PDF valido", resposta.data)
        self.assertEqual(list(PASTA_UPLOADS.glob("*.pdf")), [])

    def test_upload_valido_e_removido_ao_final(self):
        token = self._token()
        resposta = self.cliente.post(
            "/analisar",
            data={
                "token_csrf": token,
                "edital": (io.BytesIO(self._pdf_valido()), "edital_teste.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertIn(b"Mapa de", resposta.data)
        self.assertEqual(list(PASTA_UPLOADS.glob("*.pdf")), [])

    def test_resposta_possui_cabecalhos_de_seguranca(self):
        resposta = self.cliente.get("/")
        self.assertEqual(resposta.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(resposta.headers["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", resposta.headers["Content-Security-Policy"])
        self.assertEqual(resposta.headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
