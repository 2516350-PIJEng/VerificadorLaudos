"""Rotas web (formulário) e API JSON do Verificador de Laudos."""
from flask import Blueprint, current_app, jsonify, render_template, request

from app.biblioteca import BIBLIOTECA_PROJETO, listar_materiais, obter_especificacao
from app.config import EMAIL_PADRAO_PROJETISTA
from app.services.analise import analisar_material, calcular_desvio, classificar_nivel, foi_aprovado

bp = Blueprint("main", __name__)

_DECISOES = {"True": True, "False": False}
TAMANHO_MAXIMO_NF = 40


def _historico():
    return current_app.extensions["historico"]


def _normalizar_nf(texto) -> str:
    """Remove espaços das pontas e limita o tamanho da Nota Fiscal."""
    return str(texto or "").strip()[:TAMANHO_MAXIMO_NF]


def _resultado_duplicado(nota_fiscal, local, material, registro) -> dict:
    """Mensagem informativa quando já existe ensaio aprovado de valor maior ou igual para a mesma chave."""
    return {
        "status": "INFO",
        "categoria": "info",
        "mensagem": (
            f"A combinação de Nota Fiscal {nota_fiscal}, Local {local} e Material {material} "
            f"já possui um ensaio de maior ou igual valor ({registro['valor_medido']} MPa) registrado."
        ),
    }


def _para_float(texto):
    """Converte texto em float aceitando vírgula decimal. Retorna None se vazio; ValueError se inválido."""
    if texto is None:
        return None
    texto = str(texto).strip().replace(",", ".")
    if texto == "":
        return None
    return float(texto)


@bp.route("/", methods=["GET", "POST"])
def index():
    """Tela principal: campos dinâmicos de local, material, contra-prova e parecer do projetista."""
    form = request.form
    email = form.get("email_projetista", EMAIL_PADRAO_PROJETISTA).strip()

    # Sanitiza as seleções: só aceita valores existentes na biblioteca
    local = form.get("local", "")
    if local not in BIBLIOTECA_PROJETO:
        local = ""
    material = form.get("material", "")
    if material not in listar_materiais(local):
        material = ""

    nota_fiscal = _normalizar_nf(form.get("nota_fiscal"))
    valor_texto = form.get("valor", "").strip() if material else ""
    contra_texto = form.get("resultado_contra_prova", "")
    decisao = form.get("projetista_aprovou", "")
    complementar_texto = form.get("resultado_complementar", "")

    mostrar_contra_prova = False
    mostrar_projetista = False
    mostrar_complementar = False
    resultado = None
    historico = _historico()

    if material and valor_texto:
        try:
            valor = _para_float(valor_texto)
            limite = obter_especificacao(local, material)["resistencia_minima_mpa"]

            # Chave de unicidade: [Nota Fiscal + Local + Material]
            registro = historico.buscar(nota_fiscal, local, material) if nota_fiscal else None
            if registro and valor <= registro["valor_medido"]:
                resultado = _resultado_duplicado(nota_fiscal, local, material, registro)
            else:
                nivel = classificar_nivel(calcular_desvio(valor, limite))

                # Contra-prova: níveis 1 e 2 (desvio até 30%)
                mostrar_contra_prova = nivel in (1, 2)
                contra = _para_float(contra_texto) if mostrar_contra_prova else None

                # Parecer do projetista: só no nível 2, quando a contra-prova falha com desvio leve (<= 10%)
                if nivel == 2 and contra is not None and contra < limite:
                    mostrar_projetista = classificar_nivel(calcular_desvio(contra, limite)) == 1
                decisao_projetista = _DECISOES.get(decisao) if mostrar_projetista else None

                # Ensaio complementar: quando o projetista rejeita o lote
                mostrar_complementar = decisao_projetista is False
                complementar = _para_float(complementar_texto) if mostrar_complementar else None

                if form.get("analisar") == "1":
                    if not nota_fiscal:
                        resultado = {
                            "status": "ERRO",
                            "categoria": "erro",
                            "mensagem": "Informe a Nota Fiscal (NF) do lote.",
                        }
                    else:
                        resultado = analisar_material(
                            local,
                            material,
                            valor,
                            resultado_contra_prova=contra,
                            projetista_aprovou=decisao_projetista,
                            resultado_complementar=complementar,
                            email_projetista=email,
                        )
                        if foi_aprovado(resultado):
                            historico.registrar(nota_fiscal, local, material, valor, contra, resultado["status"])
        except ValueError:
            resultado = {
                "status": "ERRO",
                "categoria": "erro",
                "mensagem": "Valores de entrada inválidos.",
            }

    return render_template(
        "index.html",
        biblioteca=BIBLIOTECA_PROJETO,
        email_projetista=email,
        nota_fiscal=nota_fiscal,
        local=local,
        material=material,
        valor=valor_texto,
        resultado_contra_prova=contra_texto if mostrar_contra_prova else "",
        projetista_aprovou=decisao if mostrar_projetista else "",
        resultado_complementar=complementar_texto if mostrar_complementar else "",
        mostrar_contra_prova=mostrar_contra_prova,
        mostrar_projetista=mostrar_projetista,
        mostrar_complementar=mostrar_complementar,
        resultado=resultado,
        historico_recente=historico.listar_recentes(10),
    )


@bp.route("/api/biblioteca", methods=["GET"])
def api_biblioteca():
    """Retorna a biblioteca de projeto (locais, materiais e resistências mínimas)."""
    return jsonify(BIBLIOTECA_PROJETO)


@bp.route("/api/analisar", methods=["POST"])
def api_analisar():
    """
    Analisa um laudo via JSON.

    Corpo esperado: {"nota_fiscal": "0001", "local": "Vigas", "material": "Concreto", "valor_medido": 33.0,
                     "resultado_contra_prova": 36.0 (opcional),
                     "projetista_aprovou": true|false (opcional),
                     "resultado_complementar": 36.0 (opcional),
                     "email_projetista": "x@y.com" (opcional)}
    """
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify({"status": "ERRO", "mensagem": "Envie um corpo JSON válido (objeto)."}), 400

    try:
        valor = _para_float(dados.get("valor_medido"))
        contra = _para_float(dados.get("resultado_contra_prova"))
        complementar = _para_float(dados.get("resultado_complementar"))
    except (ValueError, TypeError):
        return jsonify({"status": "ERRO", "mensagem": "Valores numéricos inválidos."}), 400

    if valor is None:
        return jsonify({"status": "ERRO", "mensagem": "O campo 'valor_medido' é obrigatório."}), 400

    decisao = dados.get("projetista_aprovou")
    if decisao is not None and not isinstance(decisao, bool):
        return jsonify({"status": "ERRO", "mensagem": "'projetista_aprovou' deve ser true ou false."}), 400

    nota_fiscal = _normalizar_nf(dados.get("nota_fiscal"))
    if not nota_fiscal:
        return jsonify({"status": "ERRO", "mensagem": "O campo 'nota_fiscal' é obrigatório."}), 400

    local = dados.get("local", "")
    material = dados.get("material", "")
    historico = _historico()

    # Lote já aprovado com valor maior ou igual: não reanalisa
    registro = historico.buscar(nota_fiscal, str(local), str(material))
    if registro and valor <= registro["valor_medido"]:
        return jsonify(_resultado_duplicado(nota_fiscal, local, material, registro)), 409

    resultado = analisar_material(
        local,
        material,
        valor,
        resultado_contra_prova=contra,
        projetista_aprovou=decisao,
        resultado_complementar=complementar,
        email_projetista=dados.get("email_projetista") or EMAIL_PADRAO_PROJETISTA,
    )
    if foi_aprovado(resultado):
        historico.registrar(nota_fiscal, local, material, valor, contra, resultado["status"])
    codigo = 400 if resultado["categoria"] == "erro" else 200
    return jsonify(resultado), codigo


@bp.route("/api/historico", methods=["GET"])
def api_historico():
    """Últimos ensaios aprovados registrados."""
    return jsonify(_historico().listar_recentes(50))


@bp.route("/saude", methods=["GET"])
def saude():
    """Verificação simples de que a aplicação está no ar."""
    return jsonify({"status": "ok"})
