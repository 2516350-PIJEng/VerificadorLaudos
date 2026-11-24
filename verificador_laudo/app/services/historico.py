"""Histórico de lotes aprovados, com chave única [Nota Fiscal + Local + Material] (SQLite)."""
import os
import sqlite3
from contextlib import closing
from datetime import datetime

_CRIAR_TABELA = """
CREATE TABLE IF NOT EXISTS ensaios (
    nota_fiscal TEXT NOT NULL,
    local TEXT NOT NULL,
    material TEXT NOT NULL,
    valor_medido REAL NOT NULL,
    resultado_contra_prova REAL,
    status TEXT NOT NULL,
    registrado_em TEXT NOT NULL,
    PRIMARY KEY (nota_fiscal, local, material)
)
"""


class HistoricoEnsaios:
    """
    Guarda apenas ensaios APROVADOS. Serve para evitar reanálise de um lote (mesma NF, local e material)
    quando o novo valor medido é menor ou igual ao já aprovado.
    """

    def __init__(self, caminho: str):
        self.caminho = caminho
        pasta = os.path.dirname(os.path.abspath(caminho))
        os.makedirs(pasta, exist_ok=True)
        with closing(self._conectar()) as conexao, conexao:
            conexao.execute(_CRIAR_TABELA)

    def _conectar(self) -> sqlite3.Connection:
        conexao = sqlite3.connect(self.caminho, timeout=10)
        conexao.row_factory = sqlite3.Row
        return conexao

    def buscar(self, nota_fiscal: str, local: str, material: str):
        """Retorna o registro (dict) da chave NF+local+material, ou None se não existir."""
        with closing(self._conectar()) as conexao:
            linha = conexao.execute(
                "SELECT * FROM ensaios WHERE nota_fiscal = ? AND local = ? AND material = ?",
                (nota_fiscal, local, material),
            ).fetchone()
        return dict(linha) if linha else None

    def registrar(self, nota_fiscal, local, material, valor_medido, resultado_contra_prova, status) -> None:
        """Insere ou substitui o ensaio aprovado dessa chave."""
        with closing(self._conectar()) as conexao, conexao:
            conexao.execute(
                "INSERT OR REPLACE INTO ensaios VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    nota_fiscal, local, material, valor_medido, resultado_contra_prova, status,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

    def listar_recentes(self, limite: int = 10) -> list:
        """Últimos ensaios aprovados (mais recentes primeiro)."""
        with closing(self._conectar()) as conexao:
            linhas = conexao.execute(
                "SELECT * FROM ensaios ORDER BY registrado_em DESC, rowid DESC LIMIT ?", (limite,)
            ).fetchall()
        return [dict(linha) for linha in linhas]
