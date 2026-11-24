"""Testes do histórico de ensaios aprovados (SQLite)."""
import os
import shutil
import tempfile
import unittest

from app.services.analise import foi_aprovado
from app.services.historico import HistoricoEnsaios


class TestHistorico(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.mkdtemp()
        self.historico = HistoricoEnsaios(os.path.join(self.pasta, "sub", "h.db"))  # cria a subpasta

    def tearDown(self):
        shutil.rmtree(self.pasta, ignore_errors=True)

    def test_buscar_inexistente(self):
        self.assertIsNone(self.historico.buscar("1", "Vigas", "Concreto"))

    def test_registrar_e_buscar(self):
        self.historico.registrar("1", "Vigas", "Concreto", 36.5, None, "APROVADO")
        registro = self.historico.buscar("1", "Vigas", "Concreto")
        self.assertEqual(registro["valor_medido"], 36.5)
        self.assertEqual(registro["status"], "APROVADO")
        self.assertIsNone(registro["resultado_contra_prova"])

    def test_chave_e_nf_local_material(self):
        self.historico.registrar("1", "Vigas", "Concreto", 36.5, None, "APROVADO")
        self.assertIsNone(self.historico.buscar("1", "Pilares", "Concreto"))
        self.assertIsNone(self.historico.buscar("2", "Vigas", "Concreto"))
        self.assertIsNone(self.historico.buscar("1", "Vigas", "Aço CA-50"))

    def test_registrar_substitui_a_mesma_chave(self):
        self.historico.registrar("1", "Vigas", "Concreto", 36.0, None, "APROVADO")
        self.historico.registrar("1", "Vigas", "Concreto", 38.0, 37.0, "APROVADO APÓS CONTRA-PROVA")
        self.assertEqual(self.historico.buscar("1", "Vigas", "Concreto")["valor_medido"], 38.0)
        self.assertEqual(len(self.historico.listar_recentes()), 1)

    def test_listar_recentes_ordem_e_limite(self):
        for i in range(5):
            self.historico.registrar(str(i), "Vigas", "Concreto", 36.0, None, "APROVADO")
        recentes = self.historico.listar_recentes(3)
        self.assertEqual([r["nota_fiscal"] for r in recentes], ["4", "3", "2"])

    def test_sql_injection_e_tratado_como_texto(self):
        nf = "1'; DROP TABLE ensaios; --"
        self.historico.registrar(nf, "Vigas", "Concreto", 36.0, None, "APROVADO")
        self.assertEqual(self.historico.buscar(nf, "Vigas", "Concreto")["nota_fiscal"], nf)

    def test_foi_aprovado(self):
        self.assertTrue(foi_aprovado({"categoria": "aprovado"}))
        self.assertTrue(foi_aprovado({"categoria": "restricao"}))
        self.assertFalse(foi_aprovado({"categoria": "pendente"}))
        self.assertFalse(foi_aprovado({"categoria": "reprovado"}))


if __name__ == "__main__":
    unittest.main()
