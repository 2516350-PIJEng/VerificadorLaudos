# Verificador de Laudos — Controle de Qualidade (Flask)

Sistema web em **Flask** que verifica a resistência medida de materiais (concreto e aço) contra a resistência mínima de projeto, aplicando as regras de desvio do programa original "Verificador de Laudos".

## Regras de decisão

| Situação | Ação do sistema |
|---|---|
| Valor medido ≥ mínimo de projeto | **APROVADO** |
| Desvio de até 10% (**Nível 1**) | Envia alerta por e-mail e exige **contra-prova**: atende o mínimo → *Aprovado após contra-prova*; não atende → *Reprovado* |
| Desvio entre 10% e 30% (**Nível 2**) | Exige **contra-prova** (veja o fluxo abaixo) |
| Desvio acima de 30% (**Nível 3**) | **REPROVADO IMEDIATAMENTE** (sem direito a contra-prova) |

**Fluxo do Nível 2:**

1. Contra-prova atende o mínimo → *Aprovado após contra-prova*.
2. Contra-prova com desvio **maior que 10%** → *Reprovado* (lote condenado).
3. Contra-prova com desvio **de até 10%** → e-mail ao projetista, que dá o parecer:
   - **Aprova** → *Aprovado sob restrição*.
   - **Rejeita** → exige **ensaio complementar** de campo: atende o mínimo → *Aprovado após ensaio complementar*; não atende → *Reprovado definitivamente*.

**Nota Fiscal (NF) e histórico de lotes:** cada lote é identificado pela combinação **Nota Fiscal + Local + Material**. Somente lotes **aprovados** (qualquer das quatro formas de aprovação) entram no histórico. Se a mesma combinação for enviada de novo com valor medido **menor ou igual** ao já aprovado, o sistema não reanalisa e exibe uma mensagem informativa. Com valor **maior**, o lote é analisado novamente. O histórico fica em um arquivo SQLite (`instance/historico.db`) e os últimos lotes aprovados aparecem na tela.

Desvio percentual = `(mínimo − medido) / mínimo × 100`.

Biblioteca de projeto (em `app/biblioteca.py`):

| Local | Material | Mínimo (MPa) |
|---|---|---|
| Fundação | Concreto C30 / Aço CA-50 | 30 / 500 |
| Pilares | Concreto C40 / Aço CA-50 | 40 / 500 |
| Vigas | Concreto C35 / Aço CA-50 | 35 / 500 |
| Lajes | Concreto C25 / Aço CA-60 | 25 / 600 |

## Estrutura do projeto

```
verificador_laudo/
├── app/
│   ├── __init__.py            # fábrica da aplicação (create_app)
│   ├── biblioteca.py          # locais, materiais e resistências mínimas
│   ├── config.py              # leitura de variáveis de ambiente (.env)
│   ├── routes.py              # tela web + API JSON
│   ├── services/
│   │   ├── analise.py         # regras de decisão (níveis 1, 2 e 3)
│   │   ├── historico.py       # histórico de lotes aprovados (SQLite)
│   │   └── email_service.py   # e-mail de alerta (simulado ou SMTP real)
│   ├── static/css/style.css
│   └── templates/             # base.html e index.html
├── instance/                  # criada automaticamente: banco historico.db (não vai ao Git)
├── tests/                     # testes automatizados (unittest)
├── run.py                     # ponto de entrada
├── run_tests_html.py          # roda os testes e gera relatório HTML em reports/
├── requirements.txt
├── .env.example
└── README.md
```

## Requisitos

- **Python 3.10 ou superior** (verifique com `python --version`; no Linux/macOS use `python3`)
- Bibliotecas (instaladas pelo `requirements.txt`): **Flask** e **python-dotenv**

## 1. Criar o ambiente Python chamado `laudo`

Abra o terminal **dentro da pasta do projeto** (`verificador_laudo`) e crie o ambiente:

```bash
python -m venv laudo
```

> Linux/macOS: se `python` não existir, use `python3 -m venv laudo`.

### Ativar o ambiente

**Windows (PowerShell):**
```powershell
.\laudo\Scripts\Activate.ps1
```
Se aparecer erro de "execução de scripts desabilitada", rode uma vez:
`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` e tente de novo.

**Windows (Prompt de Comando / cmd):**
```bat
laudo\Scripts\activate.bat
```

**Linux / macOS:**
```bash
source laudo/bin/activate
```

Quando ativado, o terminal mostra `(laudo)` no início da linha. Para sair depois: `deactivate`.

<details>
<summary>Prefere Anaconda/Miniconda?</summary>

```bash
conda create -n laudo python=3.12
conda activate laudo
```
</details>

## 2. Instalar as bibliotecas

Com o ambiente `laudo` ativo:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Conferir a instalação:

```bash
pip list
```
(devem aparecer `Flask` e `python-dotenv`)

## 3. Configuração (opcional) e e-mails reais

Por padrão o sistema roda em **modo seguro**: os e-mails são apenas **simulados** (aparecem no terminal), sem enviar nada real. Para ajustar porta, e-mail do projetista ou SMTP:

```bash
# Windows:   copy .env.example .env
# Linux/Mac: cp .env.example .env
```

Edite o `.env` (no Windows: `notepad .env`).

**Quem recebe os alertas:** é o e-mail digitado no campo "E-mail do Projetista" da tela. Para mudar o endereço que já vem preenchido, edite `EMAIL_PROJETISTA_PADRAO` no `.env`.

**Enviar e-mails de verdade (exemplo com Gmail):**

1. Na conta Google que vai *enviar* os alertas, ative a **verificação em duas etapas** e crie uma **senha de app** (myaccount.google.com/apppasswords). Ela tem 16 letras; use-a sem espaços.
2. No `.env`, defina:

```
MOCK_EMAIL=false
EMAIL_REMETENTE=seu.email@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USUARIO=seu.email@gmail.com
SMTP_SENHA=sua_senha_de_app_de_16_letras
```

3. Reinicie o programa (`python run.py`), analise um lote com desvio (ex.: Vigas / Concreto / 33) e confira a "Notificação" na tela. Verifique também a caixa de spam do destinatário.

Nunca coloque a senha no código nem envie o `.env` ao Git (já está no `.gitignore`).

**Atenção no Render:** o plano gratuito do Render **bloqueia as portas SMTP** (25, 465 e 587), então o envio por Gmail só funciona no seu computador ou em plano pago. Na hospedagem gratuita mantenha `MOCK_EMAIL=true`.

## 4. Executar os testes automatizados

```bash
python -m unittest discover -s tests -v
```

Resultado esperado (53 testes):

```
Ran 53 tests in 0.5s

OK
```

### Relatório visual dos testes (HTML)

```bash
python run_tests_html.py
```

O script executa os testes e salva um relatório em `reports/relatorio_testes_AAAA-MM-DD_HH-MM-SS.html`. Para abrir no navegador pelo PowerShell:

```powershell
ii (Get-ChildItem reports\*.html | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
```

Não é preciso instalar nada além do `requirements.txt`.

## 5. Executar a aplicação (teste manual)

```bash
python run.py
```

Abra no navegador: **http://127.0.0.1:5000**

Roteiro de teste manual (informe qualquer e-mail de projetista e uma Nota Fiscal, por exemplo `0001`; use NFs diferentes nos casos 1 a 13 para evitar o bloqueio de duplicidade):

| # | Local / Material | Entradas | Resultado esperado |
|---|---|---|---|
| 1 | Fundação / Concreto | valor 32 | **APROVADO** |
| 2 | Vigas / Concreto | valor 33 | Nível 1 → *Aguardando contra-prova* (aparece o campo da contra-prova) |
| 3 | Vigas / Concreto | valor 33 + contra-prova 36 | *Aprovado após contra-prova* |
| 4 | Vigas / Concreto | valor 33 + contra-prova 34 | *Reprovado* |
| 5 | Pilares / Concreto | valor 32 | Nível 2 → *Aguardando contra-prova* |
| 6 | Pilares / Concreto | valor 32 + contra-prova 41 | *Aprovado após contra-prova* |
| 7 | Pilares / Concreto | valor 32 + contra-prova 30 | *Reprovado* (desvio da contra-prova de 25%) |
| 8 | Pilares / Concreto | valor 32 + contra-prova 37 | *Aguardando decisão do projetista* (aparece o campo do parecer) |
| 9 | Pilares / Concreto | caso 8 + parecer "Aprovado" | *Aprovado sob restrição* |
| 10 | Pilares / Concreto | caso 8 + parecer "Rejeitado" | *Aguardando ensaio complementar* (aparece o campo do ensaio) |
| 11 | Pilares / Concreto | caso 10 + ensaio complementar 41 | *Aprovado após ensaio complementar* |
| 12 | Pilares / Concreto | caso 10 + ensaio complementar 38 | *Reprovado definitivamente* |
| 13 | Lajes / Concreto | valor 15 | **Reprovado imediatamente** (Nível 3) |
| 14 | Fundação / Concreto | NF `0001` + valor 32 | **APROVADO** (entra em "Últimos lotes aprovados") |
| 15 | Fundação / Concreto | NF `0001` + valor 31 (repetir a mesma NF) | Mensagem **INFO**: já existe ensaio de maior ou igual valor |
| 16 | Fundação / Concreto | NF `0001` + valor 35 | Reanalisado: **APROVADO** (valor maior que o registrado) |
| 17 | Fundação / Aço CA-50 | NF `0001` + valor 520 | **APROVADO** (outro material = outra chave) |

O terminal mostra a linha `[SIMULAÇÃO DE E-MAIL]` quando um alerta é disparado (Nível 1 e contra-prova com desvio leve no Nível 2), e a tela exibe o status da notificação. O parecer do projetista reenvia o formulário automaticamente ao ser escolhido.

Para encerrar o servidor, pressione `Ctrl + C`.

## API JSON (opcional)

```bash
curl -X POST http://127.0.0.1:5000/api/analisar \
  -H "Content-Type: application/json" \
  -d '{"nota_fiscal":"0001","local":"Vigas","material":"Concreto","valor_medido":33.0,"resultado_contra_prova":36.0}'
```

Outras rotas: `GET /api/biblioteca` (dados de projeto), `GET /api/historico` (últimos lotes aprovados) e `GET /saude` (verificação de funcionamento).

Campos de `POST /api/analisar`: `nota_fiscal`, `local`, `material`, `valor_medido` (obrigatórios); `resultado_contra_prova`, `projetista_aprovou` (`true`/`false`), `resultado_complementar` e `email_projetista` (opcionais). Erros de validação retornam HTTP 400 e lote duplicado (mesma NF/local/material com valor menor ou igual ao aprovado) retorna HTTP 409.

## Problemas comuns

| Problema | Solução |
|---|---|
| `python` não é reconhecido | Reinstale o Python marcando "Add Python to PATH" ou use `py -m venv laudo` (Windows) |
| `ModuleNotFoundError: No module named 'flask'` | O ambiente `laudo` não está ativo ou faltou `pip install -r requirements.txt` |
| Porta 5000 ocupada | Defina `PORT=5001` no `.env` (ou na variável de ambiente) e rode de novo |
| E-mail real não é enviado | Confira `MOCK_EMAIL=false`, `SMTP_USUARIO`, `SMTP_SENHA` e a mensagem exibida em "Notificação" |

## Observações para uso em produção

O histórico em SQLite grava em arquivo local: em hospedagens com disco temporário (como o plano gratuito do Render) ele é **apagado a cada novo deploy ou reinício**. Para guardar o histórico de forma permanente use um disco persistente ou um banco gerenciado (PostgreSQL). O servidor do `python run.py` é para **desenvolvimento**. Em produção use um servidor WSGI (ex.: `gunicorn "run:app"` no Linux ou `waitress` no Windows) e mantenha as credenciais SMTP apenas em variáveis de ambiente.
