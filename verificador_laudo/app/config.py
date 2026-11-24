"""Configurações do sistema, lidas de variáveis de ambiente (ou do arquivo .env)."""
import os

try:  # python-dotenv é opcional: se não estiver instalado, apenas ignora o .env
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

# E-mail do projetista que já vem preenchido na tela (pode ser trocado no .env)
EMAIL_PADRAO_PROJETISTA = os.environ.get("EMAIL_PROJETISTA_PADRAO") or "projetista@estruturas.com.br"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _como_bool(valor: str, padrao: bool) -> bool:
    """Converte textos como 'true', '1', 'sim' em booleano."""
    if valor is None or valor == "":
        return padrao
    return valor.strip().lower() in {"1", "true", "yes", "sim", "on"}


def obter_config_email() -> dict:
    """Lê a configuração de e-mail no momento da chamada (facilita testes)."""
    return {
        "mock": _como_bool(os.environ.get("MOCK_EMAIL"), True),  # seguro por padrão
        "remetente": os.environ.get("EMAIL_REMETENTE", "noreply@controlequalidade.com.br"),
        "smtp_host": os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        "smtp_porta": int(os.environ.get("SMTP_PORT", "587")),
        "smtp_usuario": os.environ.get("SMTP_USUARIO", ""),
        "smtp_senha": os.environ.get("SMTP_SENHA", ""),
    }


class Config:
    """Configurações do Flask."""

    JSON_SORT_KEYS = False
    # Arquivo SQLite do histórico de ensaios aprovados (por Nota Fiscal + Local + Material)
    DATABASE_PATH = os.environ.get("DATABASE_PATH") or os.path.join(BASE_DIR, "instance", "historico.db")
