"""Regras de decisão do Verificador de Laudos (sem dependência do Flask)."""
import math
import re

from app.biblioteca import obter_especificacao
from app.config import EMAIL_PADRAO_PROJETISTA
from app.services.email_service import enviar_email_alerta

LIMITE_NIVEL_1 = 10.0  # desvio até 10%  -> exige contra-prova
LIMITE_NIVEL_2 = 30.0  # desvio até 30%  -> contra-prova + possível parecer do projetista
# acima de 30% -> reprovação imediata (nível 3)

NAO_ENVIADO = "Não enviado"

_REGEX_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def email_valido(email) -> bool:
    """Validação simples de formato de e-mail."""
    return bool(email) and bool(_REGEX_EMAIL.match(str(email).strip()))


def calcular_desvio(valor_medido: float, limite_minimo: float) -> float:
    """Desvio percentual abaixo do limite (0 se o valor atende o limite)."""
    if valor_medido >= limite_minimo:
        return 0.0
    # round evita ruídos de ponto flutuante nas fronteiras (ex.: 10.000000000000002)
    return round((limite_minimo - valor_medido) / limite_minimo * 100, 6)


def classificar_nivel(desvio_percentual: float) -> int:
    """0 = aprovado direto, 1 = leve (até 10%), 2 = moderado (até 30%), 3 = grave."""
    if desvio_percentual <= 0:
        return 0
    if desvio_percentual <= LIMITE_NIVEL_1:
        return 1
    if desvio_percentual <= LIMITE_NIVEL_2:
        return 2
    return 3


def _resultado(status, categoria, mensagem, **extras) -> dict:
    """
    Padroniza o retorno.
    categoria: aprovado | restricao | pendente | decisao | reprovado | erro (usada para colorir a tela).
    """
    resultado = {"status": status, "categoria": categoria, "mensagem": mensagem}
    resultado.update(extras)
    return resultado


def foi_aprovado(resultado: dict) -> bool:
    """True para APROVADO, APROVADO APÓS CONTRA-PROVA/ENSAIO COMPLEMENTAR e APROVADO SOB RESTRIÇÃO."""
    return resultado.get("categoria") in ("aprovado", "restricao")


def _numero_valido(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor) and valor >= 0


def _enviar_alerta(enviador, email_projetista, assunto, local, material, valor, limite, desvio, nivel) -> str:
    """Dispara o e-mail (se o endereço for válido) e devolve o texto de status para a tela."""
    if not email_valido(email_projetista):
        return "E-mail do projetista inválido: alerta não enviado."
    retorno = enviador(
        destinatario=email_projetista.strip(),
        assunto=assunto,
        local=local,
        material=material,
        valor_medido=valor,
        limite_requerido=limite,
        desvio_percentual=desvio,
        nivel=nivel,
    )
    return retorno["mensagem"]


def analisar_material(
    local,
    material,
    valor_medido,
    resultado_contra_prova=None,
    projetista_aprovou=None,
    resultado_complementar=None,
    email_projetista=EMAIL_PADRAO_PROJETISTA,
    enviador_email=enviar_email_alerta,
) -> dict:
    """
    Analisa um valor medido contra a resistência mínima da biblioteca de projeto.

    Nível 0 (valor >= mínimo) ........ APROVADO
    Nível 1 (desvio até 10%) ......... e-mail + contra-prova: atende -> aprovado; falha -> REPROVADO
    Nível 2 (desvio de 10% a 30%) .... contra-prova obrigatória:
        - atende o mínimo ............ APROVADO APÓS CONTRA-PROVA
        - desvio da contra-prova > 10% REPROVADO (lote condenado)
        - desvio da contra-prova <=10% e-mail ao projetista, que decide:
            aprova ................... APROVADO SOB RESTRIÇÃO
            rejeita .................. exige ensaio complementar:
                atende o mínimo ...... APROVADO APÓS ENSAIO COMPLEMENTAR
                não atende ........... REPROVADO DEFINITIVAMENTE
    Nível 3 (desvio acima de 30%) .... REPROVADO IMEDIATAMENTE (sem contra-prova)
    """
    especificacao = obter_especificacao(local, material)
    if especificacao is None:
        return _resultado(
            "ERRO", "erro", f"Local '{local}' ou material '{material}' não encontrado na biblioteca de projeto."
        )

    if not _numero_valido(valor_medido):
        return _resultado("ERRO", "erro", "O valor medido deve ser um número maior ou igual a zero.")
    for nome, valor in (("contra-prova", resultado_contra_prova), ("ensaio complementar", resultado_complementar)):
        if valor is not None and not _numero_valido(valor):
            return _resultado("ERRO", "erro", f"O resultado do {nome} deve ser um número maior ou igual a zero.")

    limite = especificacao["resistencia_minima_mpa"]
    desvio = calcular_desvio(valor_medido, limite)
    nivel = classificar_nivel(desvio)
    base = {"limite_minimo": limite, "valor_medido": valor_medido, "desvio_percentual": desvio, "nivel": nivel}

    # ---- Nível 0: aprovação direta ----
    if nivel == 0:
        return _resultado(
            "APROVADO", "aprovado",
            f"Lote Aprovado Diretamente! O valor de {valor_medido} MPa atende aos requisitos do projeto.", **base,
        )

    # ---- Nível 3: reprovação imediata (sem e-mail, sem contra-prova) ----
    if nivel == 3:
        return _resultado(
            "REPROVADO IMEDIATAMENTE", "reprovado",
            f"NÍVEL 3: Desvio grave ({desvio:.2f}%). Lote condenado sumariamente, "
            "sem direito a ensaios adicionais.", **base,
        )

    # ---- Nível 1: desvio leve ----
    if nivel == 1:
        base["status_email"] = _enviar_alerta(
            enviador_email, email_projetista,
            f"ALERTA NÍVEL 1 - {local}",
            local, material, valor_medido, limite, desvio, 1,
        )
        mensagem = f"NÍVEL 1: Desvio leve ({desvio:.2f}%). Exige laudo técnico de contra-prova."
        if resultado_contra_prova is None:
            return _resultado("AGUARDANDO CONTRA-PROVA", "pendente", mensagem, **base)
        if resultado_contra_prova >= limite:
            return _resultado(
                "APROVADO APÓS CONTRA-PROVA", "aprovado",
                f"Contra-prova atendeu o requisito mínimo com {resultado_contra_prova} MPa!", **base,
            )
        return _resultado(
            "REPROVADO", "reprovado",
            f"Lote Reprovado. A contra-prova de {resultado_contra_prova} MPa também não atendeu ao projeto.", **base,
        )

    # ---- Nível 2: desvio moderado ----
    base["status_email"] = NAO_ENVIADO

    if resultado_contra_prova is None:
        return _resultado(
            "AGUARDANDO CONTRA-PROVA", "pendente",
            f"NÍVEL 2: Desvio moderado ({desvio:.2f}%). Requer contra-prova estrutural. "
            "Por favor, submeta o resultado da contra-prova técnica.", **base,
        )

    if resultado_contra_prova >= limite:
        return _resultado(
            "APROVADO APÓS CONTRA-PROVA", "aprovado",
            f"Contra-prova aprovada com sucesso com {resultado_contra_prova} MPa!", **base,
        )

    desvio_contra = calcular_desvio(resultado_contra_prova, limite)
    if classificar_nivel(desvio_contra) != 1:  # desvio da contra-prova acima de 10%
        return _resultado(
            "REPROVADO", "reprovado",
            f"Contra-prova de {resultado_contra_prova} MPa falhou com desvio crítico de "
            f"{desvio_contra:.2f}% (acima de 10%).", **base,
        )

    # Contra-prova com desvio leve (<= 10%): o projetista precisa opinar
    base["status_email"] = _enviar_alerta(
        enviador_email, email_projetista,
        f"ALERTA NÍVEL 2 - {local}",
        local, material, resultado_contra_prova, limite, desvio_contra, 2,
    )

    if projetista_aprovou is None:
        return _resultado(
            "AGUARDANDO DECISÃO DO PROJETISTA", "decisao",
            f"Contra-prova com desvio leve de {desvio_contra:.2f}%. Aguardando parecer técnico do projetista.",
            **base,
        )

    if projetista_aprovou is True:
        return _resultado(
            "APROVADO SOB RESTRIÇÃO", "restricao",
            "Lote aprovado sob restrição técnica após parecer favorável do projetista estrutural.", **base,
        )

    # Projetista rejeitou: exige ensaio complementar de campo
    if resultado_complementar is None:
        return _resultado(
            "AGUARDANDO ENSAIO COMPLEMENTAR", "pendente",
            "Projetista rejeitou a contra-prova. Solicitado ensaio complementar físico de campo.", **base,
        )
    if resultado_complementar >= limite:
        return _resultado(
            "APROVADO APÓS ENSAIO COMPLEMENTAR", "aprovado",
            f"Aprovado sob ensaio complementar secundário de {resultado_complementar} MPa.", **base,
        )
    return _resultado(
        "REPROVADO DEFINITIVAMENTE", "reprovado",
        f"Lote condenado. Ensaio complementar de {resultado_complementar} MPa falhou.", **base,
    )
