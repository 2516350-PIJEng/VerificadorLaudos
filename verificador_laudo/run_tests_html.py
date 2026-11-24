"""
Executa a suíte de testes e gera um relatório HTML em reports/ (apenas biblioteca padrão).

Uso:  python run_tests_html.py
"""
import html
import os
import sys
import time
import unittest
from datetime import datetime

os.environ["MOCK_EMAIL"] = "true"  # nenhum e-mail real durante os testes


class ResultadoDetalhado(unittest.TextTestResult):
    """Guarda o resultado de cada teste para montar o relatório."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.registros = []  # (nome, status, detalhe)

    def addSuccess(self, test):
        super().addSuccess(test)
        self.registros.append((test.id(), "OK", ""))

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.registros.append((test.id(), "FALHA", self._exc_info_to_string(err, test)))

    def addError(self, test, err):
        super().addError(test, err)
        self.registros.append((test.id(), "ERRO", self._exc_info_to_string(err, test)))


def gerar_html(resultado, duracao) -> str:
    total = resultado.testsRun
    ok = sum(1 for _, status, _ in resultado.registros if status == "OK")
    cor_geral = "#28a745" if resultado.wasSuccessful() else "#dc3545"
    linhas = []
    for nome, status, detalhe in resultado.registros:
        cor = "#d4edda" if status == "OK" else "#f8d7da"
        extra = f"<pre>{html.escape(detalhe)}</pre>" if detalhe else ""
        linhas.append(
            f'<tr style="background:{cor}"><td>{html.escape(nome)}</td><td>{status}</td><td>{extra}</td></tr>'
        )
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8">
<title>Relatório de Testes - Verificador de Laudos</title>
<style>
 body {{ font-family: Arial, sans-serif; margin: 30px; color: #333; }}
 table {{ border-collapse: collapse; width: 100%; }}
 th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; vertical-align: top; }}
 th {{ background: #f2f2f2; }}
 .resumo {{ padding: 12px; border-radius: 6px; color: #fff; background: {cor_geral}; margin-bottom: 20px; }}
 pre {{ white-space: pre-wrap; margin: 0; }}
</style></head><body>
<h1>Relatório de Testes de Controle de Qualidade</h1>
<div class="resumo"><strong>{ok} de {total} testes aprovados</strong> —
 {len(resultado.failures)} falha(s), {len(resultado.errors)} erro(s) — {duracao:.2f}s —
 gerado em {datetime.now():%d/%m/%Y %H:%M:%S}</div>
<table><tr><th>Teste</th><th>Resultado</th><th>Detalhes</th></tr>{''.join(linhas)}</table>
</body></html>"""


def main() -> int:
    raiz = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, raiz)
    suite = unittest.TestLoader().discover(os.path.join(raiz, "tests"))

    inicio = time.time()
    runner = unittest.TextTestRunner(resultclass=ResultadoDetalhado, verbosity=1)
    resultado = runner.run(suite)
    duracao = time.time() - inicio

    pasta = os.path.join(raiz, "reports")
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f"relatorio_testes_{datetime.now():%Y-%m-%d_%H-%M-%S}.html")
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(gerar_html(resultado, duracao))
    print(f"\nRelatório HTML gerado em: {caminho}")
    return 0 if resultado.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
