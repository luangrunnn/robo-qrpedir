#  Robô QRPedir — Associação automática de códigos do PDV

Automação em Python que preenche o **Id Exterior** (código do produto no PDV) de todos os itens e complementos de um cardápio digital no QRPedir, a partir da planilha de exportação de produtos do sistema.

---

## 🎯 O problema

Na implantação de restaurantes que usam o cardápio digital QRPedir, cada item e cada complemento do cardápio precisa receber o código do produto correspondente no PDV. Sem essa associação, o pedido não é identificado no sistema e a baixa de estoque não acontece no produto correto.

Feito à mão, isso exige abrir item por item, procurar o código na planilha e digitar — um processo lento e sujeito a erro, principalmente em cardápios grandes.

## ✅ A solução

O usuário envia a planilha de exportação de produtos e informa o login do QRPedir. O robô então:

1. Acessa o QRPedir e percorre todos os grupos do cardápio (ignorando grupos configurados, como promoções).
2. Abre cada item e busca o produto correspondente na planilha **por similaridade de texto**.
3. Preenche o código no campo Id Exterior e salva.
4. Entra na aba de complementos e repete o processo para cada complemento do item.
5. Ao final, mostra o resumo: salvos, não encontrados e erros.

## 📈 Resultado

Reduz em **cerca de 30%** o tempo dessa etapa da implantação em relação ao processo manual (o ganho varia com o tamanho do cardápio).

---

## ⚙️ Destaques técnicos

- **Busca por similaridade** — os nomes são normalizados (sem acentos, símbolos e espaços extras) e comparados com `difflib.SequenceMatcher`. O limite mínimo (padrão 80%) é ajustável na tela, evitando associações erradas.
- **Detecção automática de colunas** — identifica sozinho as colunas de código e descrição da planilha.
- **Progresso salvo** — se a execução for interrompida, continua de onde parou.
- **Pausa e retomada** durante a execução.
- **Logs em tempo real** na interface, com cores por tipo de mensagem.
- **Execução headless** — o navegador roda em segundo plano, pronto para deploy no Streamlit Community Cloud.

## 🛠️ Tecnologias

Python · Playwright · Streamlit · pandas

## 📁 Estrutura

```
├── app.py              # Interface web (Streamlit)
├── requirements.txt    # Dependências Python
├── packages.txt        # Dependências do sistema (Chromium para a nuvem)
├── core/
│   ├── logger.py       # Logs
│   ├── matching.py     # Normalização, similaridade e leitura da planilha
│   └── progress.py     # Progresso, pausa e status
└── qrpedir/
    ├── config.py       # URLs e configurações
    └── robot.py        # Automação com Playwright
```

## 🖥️ Como rodar localmente

```bash
pip install -r requirements.txt
playwright install chromium
streamlit run app.py
```

Acesse: http://localhost:8501

## 📋 Formato da planilha

| id | descricao |
|---|---|
| 101 | X-Burguer Duplo |
| 102 | Coca-Cola Lata |

A coluna de código deve se chamar `id`, `codigo`, `code` ou `cod`, e a de descrição deve conter `desc` no nome.

## 🔒 Segurança

- Login e senha são digitados na tela a cada execução e **não são salvos** em disco nem no código.
- Planilhas e arquivos gerados pelo robô ficam fora do repositório (`.gitignore`).

---

Desenvolvido por **Luan Grun** · [LinkedIn](https://linkedin.com/in/luan-grun-a60a46208)
