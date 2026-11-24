"""Fábrica da aplicação Flask do Verificador de Laudos."""
from flask import Flask

from app.config import Config
from app.services.historico import HistoricoEnsaios


def create_app(config_extra: dict = None) -> Flask:
    """Cria e configura a aplicação (padrão application factory). `config_extra` é usado nos testes."""
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_extra:
        app.config.update(config_extra)
    app.json.ensure_ascii = False  # mantém acentos nas respostas JSON (Flask 3)

    # Histórico de ensaios aprovados (SQLite, apenas biblioteca padrão)
    app.extensions["historico"] = HistoricoEnsaios(app.config["DATABASE_PATH"])

    from app.routes import bp  # importado aqui para evitar import circular

    app.register_blueprint(bp)
    return app
