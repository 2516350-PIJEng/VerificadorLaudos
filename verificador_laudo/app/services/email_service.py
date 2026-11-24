"""Envio (ou simulação) de e-mails de alerta ao projetista estrutural."""
import html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import obter_config_email

MENSAGEM_SIMULADO = "Alerta simulado com sucesso (modo de desenvolvimento)."

_TITULOS = {
    1: "Desvio leve [NÍVEL 1] — solicitada contra-prova",
    2: "Contra-prova com desvio leve [NÍVEL 2] — requer parecer do projetista",
}


def montar_corpo_html(local, material, valor_medido, limite_requerido, desvio_percentual, nivel=None) -> str:
    """Monta o corpo HTML do e-mail (valores são escapados para evitar injeção de HTML)."""
    titulo = html.escape(_TITULOS.get(nivel, "Desvio de resistência"))
    linhas = [
        ("Local de Aplicação", html.escape(str(local))),
        ("Material", html.escape(str(material))),
        ("Resistência Requerida", f"{limite_requerido:.2f} MPa"),
        # No Nível 2 o valor enviado é o da contra-prova
        ("Resistência da Contra-prova" if nivel == 2 else "Resistência Medida", f"{valor_medido:.2f} MPa"),
        ("Desvio Percentual", f"{desvio_percentual:.2f}%"),
    ]
    tabela = "".join(
        f'<tr><td style="border:1px solid #ddd;padding:8px;"><strong>{campo}</strong></td>'
        f'<td style="border:1px solid #ddd;padding:8px;">{valor}</td></tr>'
        for campo, valor in linhas
    )
    cabecalho = (
        '<tr style="background-color:#f2f2f2;">'
        '<th style="border:1px solid #ddd;padding:8px;text-align:left;">Campo</th>'
        '<th style="border:1px solid #ddd;padding:8px;text-align:left;">Detalhes</th></tr>'
    )
    return (
        '<html><body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;">'
        f'<h2 style="color:#ca7d00;">Aviso de Controle de Qualidade: {titulo}</h2>'
        "<p>Prezado(a) Projetista Estrutural,</p>"
        "<p>Identificamos um desvio técnico no elemento do projeto que requer sua análise técnica imediata.</p>"
        f'<table style="border-collapse:collapse;width:100%;max-width:500px;">{cabecalho}{tabela}</table>'
        "<p>Acesse o portal para registrar formalmente seu parecer técnico.</p>"
        "<p>Atenciosamente,<br>Equipe de Controle de Qualidade</p>"
        "</body></html>"
    )


def enviar_email_alerta(
    destinatario,
    assunto,
    local,
    material,
    valor_medido,
    limite_requerido,
    desvio_percentual,
    nivel=None,
    mock=None,
) -> dict:
    """
    Envia (ou simula) o e-mail de alerta.

    Retorna sempre um dicionário {"sucesso": bool, "mensagem": str} e nunca lança exceção,
    para que uma falha de e-mail não derrube a análise do laudo.
    """
    config = obter_config_email()
    if mock is None:
        mock = config["mock"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = config["remetente"]
    msg["To"] = destinatario
    msg.attach(
        MIMEText(
            montar_corpo_html(local, material, valor_medido, limite_requerido, desvio_percentual, nivel),
            "html",
            "utf-8",
        )
    )

    if mock:
        print(f"[SIMULAÇÃO DE E-MAIL] Para: {destinatario} | Assunto: {assunto}")
        return {"sucesso": True, "mensagem": MENSAGEM_SIMULADO}

    if not config["smtp_usuario"] or not config["smtp_senha"]:
        return {
            "sucesso": False,
            "mensagem": "SMTP não configurado: defina SMTP_USUARIO e SMTP_SENHA no arquivo .env.",
        }

    try:
        with smtplib.SMTP(config["smtp_host"], config["smtp_porta"], timeout=10) as servidor:
            servidor.starttls()
            servidor.login(config["smtp_usuario"], config["smtp_senha"])
            servidor.sendmail(config["remetente"], [destinatario], msg.as_string())
        return {"sucesso": True, "mensagem": "E-mail enviado com sucesso via SMTP."}
    except Exception as erro:  # noqa: BLE001 - qualquer falha de rede/autenticação deve ser reportada
        return {"sucesso": False, "mensagem": f"Falha ao enviar e-mail via SMTP: {erro}"}
