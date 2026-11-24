"""Testes das rotas Flask (formulário e API JSON)."""
import os
import shutil
import tempfile
import unittest

os.environ["MOCK_EMAIL"] = "true"

from app import create_app  # noqa: E402


class TestRotas(unittest.TestCase):
    def setUp(self):
        # Banco SQLite temporário e isolado para cada teste
        self.pasta_temp = tempfile.mkdtemp()
        self.app = create_app({"TESTING": True, "DATABASE_PATH": os.path.join(self.pasta_temp, "teste.db")})
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.pasta_temp, ignore_errors=True)

    def test_pagina_inicial(self):
        resposta = self.client.get("/")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Controle Tecnológico de Qualidade", resposta.get_data(as_text=True))

    def test_saude(self):
        self.assertEqual(self.client.get("/saude").get_json(), {"status": "ok"})

    def test_selecao_de_local_mostra_materiais(self):
        resposta = self.client.post("/", data={"local": "Vigas", "email_projetista": "a@b.com"})
        html = resposta.get_data(as_text=True)
        self.assertIn("Aço CA-50", html)
        self.assertIn("Requerido: 35.0 MPa", html)

    def test_material_de_outro_local_e_descartado(self):
        # "Aço CA-60" só existe em Lajes; em Vigas o campo de material deve ser limpo
        resposta = self.client.post("/", data={"local": "Vigas", "material": "Aço CA-60", "valor": "10"})
        self.assertNotIn('name="valor"', resposta.get_data(as_text=True))

    def test_formulario_nivel_1_mostra_contra_prova(self):
        dados = {"nota_fiscal": "NF1", "local": "Vigas", "material": "Concreto", "valor": "33", "email_projetista": "a@b.com", "analisar": "1"}
        html = self.client.post("/", data=dados).get_data(as_text=True)
        self.assertIn("AGUARDANDO CONTRA-PROVA", html)
        self.assertIn("contra-prova", html)

    def _post(self, **campos):
        dados = {
            "nota_fiscal": "NF1", "local": "Pilares", "material": "Concreto",
            "email_projetista": "a@b.com", "analisar": "1",
        }
        dados.update(campos)
        return self.client.post("/", data=dados).get_data(as_text=True)

    def test_formulario_nivel_2_pede_contra_prova(self):
        html = self._post(valor="32")
        self.assertIn("AGUARDANDO CONTRA-PROVA", html)
        self.assertIn('name="resultado_contra_prova"', html)
        self.assertNotIn('name="projetista_aprovou"', html)

    def test_formulario_nivel_2_mostra_projetista(self):
        html = self._post(valor="32", resultado_contra_prova="37")
        self.assertIn("AGUARDANDO DECISÃO DO PROJETISTA", html)
        self.assertIn('name="projetista_aprovou"', html)

    def test_formulario_nivel_2_rejeicao_mostra_complementar(self):
        html = self._post(valor="32", resultado_contra_prova="37", projetista_aprovou="False")
        self.assertIn("AGUARDANDO ENSAIO COMPLEMENTAR", html)
        self.assertIn('name="resultado_complementar"', html)

    def test_formulario_fluxo_completo_complementar_aprova(self):
        html = self._post(
            valor="32", resultado_contra_prova="37", projetista_aprovou="False", resultado_complementar="41"
        )
        self.assertIn("APROVADO APÓS ENSAIO COMPLEMENTAR", html)

    def test_formulario_campos_obsoletos_sao_descartados(self):
        # Valor aprovado direto: contra-prova e decisão antigas não devem influenciar o resultado
        html = self._post(valor="45", resultado_contra_prova="37", projetista_aprovou="False")
        self.assertIn("APROVADO", html)
        self.assertNotIn('name="resultado_contra_prova"', html)

    def test_formulario_aceita_virgula_decimal(self):
        dados = {"nota_fiscal": "NF1", "local": "Vigas", "material": "Concreto", "valor": "33,0", "email_projetista": "a@b.com", "analisar": "1"}
        html = self.client.post("/", data=dados).get_data(as_text=True)
        self.assertIn("AGUARDANDO CONTRA-PROVA", html)

    def test_formulario_valor_invalido(self):
        dados = {"nota_fiscal": "NF1", "local": "Vigas", "material": "Concreto", "valor": "abc", "analisar": "1"}
        html = self.client.post("/", data=dados).get_data(as_text=True)
        self.assertIn("Valores de entrada inválidos", html)

    def test_api_analisar_ok(self):
        resposta = self.client.post(
            "/api/analisar",
            json={
                "nota_fiscal": "NF1", "local": "Pilares", "material": "Concreto", "valor_medido": 32.0,
                "resultado_contra_prova": 37.0, "projetista_aprovou": True,
            },
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json()["status"], "APROVADO SOB RESTRIÇÃO")

    def test_api_analisar_fluxo_complementar(self):
        resposta = self.client.post(
            "/api/analisar",
            json={
                "nota_fiscal": "NF1", "local": "Pilares", "material": "Concreto", "valor_medido": 32.0,
                "resultado_contra_prova": 37.0, "projetista_aprovou": False, "resultado_complementar": 38.0,
            },
        )
        self.assertEqual(resposta.get_json()["status"], "REPROVADO DEFINITIVAMENTE")

    def test_api_analisar_erros(self):
        self.assertEqual(self.client.post("/api/analisar", data="nao-json").status_code, 400)
        self.assertEqual(self.client.post("/api/analisar", json={"nota_fiscal": "NF1", "local": "Vigas"}).status_code, 400)
        r = self.client.post("/api/analisar", json={"nota_fiscal": "NF1", "local": "X", "material": "Y", "valor_medido": 1})
        self.assertEqual(r.status_code, 400)
        r = self.client.post(
            "/api/analisar",
            json={
                "nota_fiscal": "NF1", "local": "Vigas", "material": "Concreto",
                "valor_medido": 33, "projetista_aprovou": "sim",
            },
        )
        self.assertEqual(r.status_code, 400)

    # ---- Nota Fiscal e histórico ----
    def test_formulario_exige_nota_fiscal_ao_analisar(self):
        html = self._post(nota_fiscal="", valor="45")
        self.assertIn("Informe a Nota Fiscal", html)

    def test_lote_aprovado_entra_no_historico_da_tela(self):
        html = self._post(nota_fiscal="NF-777", valor="45")
        self.assertIn("Últimos lotes aprovados", html)
        self.assertIn("NF-777", html)

    def test_lote_pendente_nao_entra_no_historico(self):
        html = self._post(nota_fiscal="NF-888", valor="32")  # aguardando contra-prova
        self.assertNotIn("Últimos lotes aprovados", html)

    def test_reenvio_com_valor_menor_ou_igual_e_bloqueado(self):
        self._post(nota_fiscal="NF-9", valor="45")
        html = self._post(nota_fiscal="NF-9", valor="40.5")
        self.assertIn("já possui um ensaio de maior ou igual valor (45.0 MPa)", html)
        self.assertNotIn("Status: APROVADO", html)

    def test_reenvio_com_valor_maior_e_reanalisado(self):
        self._post(nota_fiscal="NF-9", valor="40")
        html = self._post(nota_fiscal="NF-9", valor="45")
        self.assertIn("Status: APROVADO", html)

    def test_mesma_nf_em_outro_material_nao_conflita(self):
        self._post(nota_fiscal="NF-9", valor="45")
        html = self._post(nota_fiscal="NF-9", material="Aço CA-50", valor="520")
        self.assertIn("Status: APROVADO", html)

    def test_api_exige_nota_fiscal(self):
        r = self.client.post("/api/analisar", json={"local": "Vigas", "material": "Concreto", "valor_medido": 40})
        self.assertEqual(r.status_code, 400)

    def test_api_duplicidade_retorna_409_e_historico(self):
        corpo = {"nota_fiscal": "NF-API", "local": "Vigas", "material": "Concreto", "valor_medido": 40}
        self.assertEqual(self.client.post("/api/analisar", json=corpo).status_code, 200)
        corpo["valor_medido"] = 38
        r = self.client.post("/api/analisar", json=corpo)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.get_json()["status"], "INFO")
        historico = self.client.get("/api/historico").get_json()
        self.assertEqual(len(historico), 1)
        self.assertEqual(historico[0]["nota_fiscal"], "NF-API")

    def test_valor_so_com_espacos_nao_quebra(self):
        resposta = self.client.post(
            "/", data={"nota_fiscal": "NF1", "local": "Vigas", "material": "Concreto", "valor": "   "}
        )
        self.assertEqual(resposta.status_code, 200)

    def test_api_biblioteca(self):
        self.assertIn("Fundação", self.client.get("/api/biblioteca").get_json())


if __name__ == "__main__":
    unittest.main()
