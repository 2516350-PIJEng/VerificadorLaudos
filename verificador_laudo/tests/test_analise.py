"""Testes das regras de decisão (sem Flask)."""
import os
import unittest

os.environ["MOCK_EMAIL"] = "true"  # garante que nenhum teste envie e-mail real

from app.services.analise import analisar_material, calcular_desvio, classificar_nivel  # noqa: E402
from app.services.email_service import MENSAGEM_SIMULADO, montar_corpo_html  # noqa: E402


class TestDesvioENivel(unittest.TestCase):
    def test_desvio_zero_quando_atende(self):
        self.assertEqual(calcular_desvio(40.0, 40.0), 0.0)
        self.assertEqual(calcular_desvio(45.0, 40.0), 0.0)

    def test_fronteiras_de_nivel(self):
        self.assertEqual(classificar_nivel(calcular_desvio(31.5, 35.0)), 1)  # exatamente 10%
        self.assertEqual(classificar_nivel(calcular_desvio(31.4, 35.0)), 2)  # um pouco acima de 10%
        self.assertEqual(classificar_nivel(calcular_desvio(28.0, 40.0)), 2)  # exatamente 30%
        self.assertEqual(classificar_nivel(calcular_desvio(27.9, 40.0)), 3)  # acima de 30%


class TestAnaliseMaterial(unittest.TestCase):
    # ---- Nível 0 e 3 ----
    def test_aprovacao_direta(self):
        res = analisar_material("Fundação", "Concreto", 32.0)
        self.assertEqual(res["status"], "APROVADO")
        self.assertIn("atende aos requisitos do projeto", res["mensagem"])
        self.assertNotIn("status_email", res)

    def test_nivel_3_reprovado_imediatamente_sem_email(self):
        chamadas = []
        res = analisar_material("Lajes", "Concreto", 15.0, enviador_email=lambda **kw: chamadas.append(kw))
        self.assertEqual(res["status"], "REPROVADO IMEDIATAMENTE")
        self.assertEqual(chamadas, [])

    # ---- Nível 1 ----
    def test_nivel_1_aguardando_contra_prova(self):
        res = analisar_material("Vigas", "Concreto", 33.0)
        self.assertEqual(res["status"], "AGUARDANDO CONTRA-PROVA")
        self.assertEqual(res["status_email"], MENSAGEM_SIMULADO)

    def test_nivel_1_contra_prova_aprovada(self):
        res = analisar_material("Vigas", "Concreto", 33.0, resultado_contra_prova=35.5)
        self.assertEqual(res["status"], "APROVADO APÓS CONTRA-PROVA")

    def test_nivel_1_contra_prova_reprovada(self):
        res = analisar_material("Vigas", "Concreto", 33.0, resultado_contra_prova=34.0)
        self.assertEqual(res["status"], "REPROVADO")

    # ---- Nível 2 (fluxo atualizado) ----
    def test_nivel_2_aguardando_contra_prova_sem_email(self):
        res = analisar_material("Pilares", "Concreto", 32.0)  # desvio de 20%
        self.assertEqual(res["status"], "AGUARDANDO CONTRA-PROVA")
        self.assertEqual(res["status_email"], "Não enviado")

    def test_nivel_2_contra_prova_atende_projeto(self):
        res = analisar_material("Pilares", "Concreto", 32.0, resultado_contra_prova=41.0)
        self.assertEqual(res["status"], "APROVADO APÓS CONTRA-PROVA")

    def test_nivel_2_contra_prova_desvio_grave_reprova(self):
        res = analisar_material("Pilares", "Concreto", 32.0, resultado_contra_prova=30.0)  # desvio de 25%
        self.assertEqual(res["status"], "REPROVADO")
        self.assertEqual(res["status_email"], "Não enviado")

    def test_nivel_2_contra_prova_leve_aguarda_projetista(self):
        res = analisar_material("Pilares", "Concreto", 32.0, resultado_contra_prova=37.0)  # desvio de 7,5%
        self.assertEqual(res["status"], "AGUARDANDO DECISÃO DO PROJETISTA")
        self.assertEqual(res["status_email"], MENSAGEM_SIMULADO)

    def test_nivel_2_projetista_aprova(self):
        res = analisar_material("Pilares", "Concreto", 32.0, resultado_contra_prova=37.0, projetista_aprovou=True)
        self.assertEqual(res["status"], "APROVADO SOB RESTRIÇÃO")

    def test_nivel_2_projetista_rejeita_aguarda_complementar(self):
        res = analisar_material("Pilares", "Concreto", 32.0, resultado_contra_prova=37.0, projetista_aprovou=False)
        self.assertEqual(res["status"], "AGUARDANDO ENSAIO COMPLEMENTAR")

    def test_nivel_2_complementar_aprova(self):
        res = analisar_material(
            "Pilares", "Concreto", 32.0, resultado_contra_prova=37.0,
            projetista_aprovou=False, resultado_complementar=40.5,
        )
        self.assertEqual(res["status"], "APROVADO APÓS ENSAIO COMPLEMENTAR")

    def test_nivel_2_complementar_reprova_definitivamente(self):
        res = analisar_material(
            "Pilares", "Concreto", 32.0, resultado_contra_prova=37.0,
            projetista_aprovou=False, resultado_complementar=38.0,
        )
        self.assertEqual(res["status"], "REPROVADO DEFINITIVAMENTE")

    # ---- Validações e e-mail ----
    def test_local_ou_material_inexistente(self):
        self.assertEqual(analisar_material("Telhado", "Concreto", 30.0)["status"], "ERRO")
        self.assertEqual(analisar_material("Vigas", "Madeira", 30.0)["status"], "ERRO")

    def test_valores_invalidos(self):
        self.assertEqual(analisar_material("Vigas", "Concreto", -5.0)["status"], "ERRO")
        self.assertEqual(analisar_material("Vigas", "Concreto", float("nan"))["status"], "ERRO")
        self.assertEqual(analisar_material("Vigas", "Concreto", 33.0, resultado_contra_prova=-1)["status"], "ERRO")
        self.assertEqual(analisar_material("Vigas", "Concreto", 33.0, resultado_complementar=-1)["status"], "ERRO")

    def test_email_nivel_1_chamado_com_dados_corretos(self):
        chamadas = []

        def falso_enviador(**kwargs):
            chamadas.append(kwargs)
            return {"sucesso": True, "mensagem": "ok"}

        analisar_material("Vigas", "Concreto", 33.0, email_projetista="a@b.com", enviador_email=falso_enviador)
        self.assertEqual(len(chamadas), 1)
        self.assertEqual(chamadas[0]["nivel"], 1)
        self.assertEqual(chamadas[0]["destinatario"], "a@b.com")

    def test_email_nivel_2_envia_valor_da_contra_prova(self):
        chamadas = []

        def falso_enviador(**kwargs):
            chamadas.append(kwargs)
            return {"sucesso": True, "mensagem": "ok"}

        analisar_material(
            "Pilares", "Concreto", 32.0, resultado_contra_prova=37.0, enviador_email=falso_enviador
        )
        self.assertEqual(len(chamadas), 1)
        self.assertEqual(chamadas[0]["nivel"], 2)
        self.assertEqual(chamadas[0]["valor_medido"], 37.0)

    def test_email_invalido_nao_bloqueia_analise(self):
        res = analisar_material("Vigas", "Concreto", 33.0, email_projetista="invalido")
        self.assertEqual(res["status"], "AGUARDANDO CONTRA-PROVA")
        self.assertIn("inválido", res["status_email"])


class TestCorpoEmail(unittest.TestCase):
    def test_escapa_html(self):
        corpo = montar_corpo_html("<script>x</script>", "Concreto", 30.0, 40.0, 25.0, nivel=2)
        self.assertNotIn("<script>", corpo)
        self.assertIn("&lt;script&gt;", corpo)


if __name__ == "__main__":
    unittest.main()
