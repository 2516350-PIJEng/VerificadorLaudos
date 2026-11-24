"""Biblioteca de dados de projeto: locais de aplicação, materiais e resistências mínimas."""

BIBLIOTECA_PROJETO = {
    "Fundação": {
        "Concreto": {"tipo": "C30", "resistencia_minima_mpa": 30.0},
        "Aço CA-50": {"tipo": "Armadura de Reforço", "resistencia_minima_mpa": 500.0},
    },
    "Pilares": {
        "Concreto": {"tipo": "C40", "resistencia_minima_mpa": 40.0},
        "Aço CA-50": {"tipo": "Armadura Transversal e Longitudinal", "resistencia_minima_mpa": 500.0},
    },
    "Vigas": {
        "Concreto": {"tipo": "C35", "resistencia_minima_mpa": 35.0},
        "Aço CA-50": {"tipo": "Armadura de Flexão", "resistencia_minima_mpa": 500.0},
    },
    "Lajes": {
        "Concreto": {"tipo": "C25", "resistencia_minima_mpa": 25.0},
        "Aço CA-60": {"tipo": "Tela Eletrosoldada", "resistencia_minima_mpa": 600.0},
    },
}


def listar_locais() -> list:
    """Retorna os locais de aplicação cadastrados."""
    return list(BIBLIOTECA_PROJETO.keys())


def listar_materiais(local: str) -> list:
    """Retorna os materiais disponíveis para um local (lista vazia se o local não existir)."""
    return list(BIBLIOTECA_PROJETO.get(local, {}).keys())


def obter_especificacao(local: str, material: str):
    """Retorna o dicionário de especificação ou None se local/material não existirem."""
    return BIBLIOTECA_PROJETO.get(local, {}).get(material)
