import asyncio
import sys
import time
import threading

import streamlit as st

from core.logger import add_log, limpar_logs, ler_logs
from core.matching import carregar_planilha, detectar_colunas
from core.progress import (
    esta_rodando, esta_pausado, set_rodando,
    pausar, retomar, tem_progresso, contar_progresso,
    limpar_progresso, carregar_progresso,
)
import qrpedir.robot as robo_qrpedir

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

# ──────────────────────────────────────────
# Configuração da página
# ──────────────────────────────────────────

st.set_page_config(page_title="Robô QRPedir", page_icon="🤖", layout="wide")

st.markdown("""
<style>
.log-box {
    background: #0f1117;
    border-radius: 8px;
    padding: 1rem;
    height: 420px;
    overflow-y: auto;
    font-family: monospace;
    font-size: 13px;
}
.log-ok   { color: #00e676; }
.log-erro { color: #ff5252; }
.log-info { color: #64b5f6; }
.log-warn { color: #ffca28; }
</style>
""", unsafe_allow_html=True)

st.title("🍽️ Robô QRPedir — Preencher Id Exterior")
st.divider()

# ──────────────────────────────────────────
# Thread do robô
# ──────────────────────────────────────────

def thread_qrpedir(email, senha, arquivo_bytes, nome_arquivo, grupos_ignorar, similaridade_minima):
    set_rodando(True)
    limpar_logs()
    try:
        df = carregar_planilha(arquivo_bytes, nome_arquivo)
        add_log(f"Planilha carregada: {len(df)} itens", "ok")
    except Exception as e:
        add_log(f"Erro ao ler planilha: {e}", "erro")
        set_rodando(False)
        return

    itens_salvos = carregar_progresso(robo="qrpedir")
    try:
        stats = robo_qrpedir.executar_robo(email, senha, df, grupos_ignorar, similaridade_minima, itens_salvos)
        add_log("=" * 40, "info")
        add_log(
            f"✅ Concluído! Salvos: {stats['ok']} | "
            f"Não encontrados: {stats['nao_encontrado']} | "
            f"Erros: {stats['erro']}",
            "ok",
        )
        limpar_progresso(robo="qrpedir")
    except Exception as e:
        add_log(f"ERRO CRÍTICO: {e}", "erro")
    set_rodando(False)


# ──────────────────────────────────────────
# Interface
# ──────────────────────────────────────────

rodando = esta_rodando()
pausado = esta_pausado()

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("⚙️ Configuração")
    email = st.text_input("E-mail do QRPedir:")
    senha = st.text_input("Senha:", type="password")
    arquivo = st.file_uploader("Planilha com os códigos:", type=["xlsx", "xls", "csv"])
    grupos_ignorar_input = st.text_input(
        "Grupos para ignorar (separados por vírgula):",
        value="EM PROMOÇÃO, PROMOÇÃO",
    )
    grupos_ignorar = [g.strip() for g in grupos_ignorar_input.split(",") if g.strip()]
    similaridade_minima = st.slider(
        "Similaridade mínima:", min_value=0.5, max_value=1.0, value=0.80, step=0.05,
        help="0.80 = 80% parecido. Recomendado para evitar associações erradas.",
    )

    if tem_progresso(robo="qrpedir"):
        st.info(f"📌 Progresso salvo: {contar_progresso(robo='qrpedir')} itens. Vai continuar de onde parou.")
        if st.button("🗑️ Limpar progresso e recomeçar", key="limpar_qr"):
            limpar_progresso(robo="qrpedir")
            st.success("Progresso limpo!")
            st.rerun()

    arquivo_bytes = None
    nome_arquivo  = ""
    if arquivo:
        try:
            arquivo_bytes = arquivo.read()
            nome_arquivo  = arquivo.name
            df_prev = carregar_planilha(arquivo_bytes, nome_arquivo)
            col_id, col_desc = detectar_colunas(df_prev)
            st.success(f"Planilha carregada: {len(df_prev)} itens")
            st.info(f"🔎 ID: **{col_id}** | Descrição: **{col_desc}**")
            with st.expander("Ver prévia"):
                st.dataframe(df_prev.head(5))
        except Exception as e:
            st.error(f"Erro ao ler planilha: {e}")

with col2:
    st.subheader("📊 Status")
    if rodando and not pausado:
        st.success("🟢 Robô rodando...")
    elif pausado:
        st.warning("⏸ Pausado")
    else:
        st.info("⚪ Aguardando")

st.divider()
cb1, cb2, cb3 = st.columns(3)

with cb1:
    iniciar_qr = st.button(
        "▶️ INICIAR ROBÔ",
        disabled=rodando or arquivo_bytes is None or not senha or not email,
        use_container_width=True,
        type="primary",
        key="iniciar_qr",
    )
with cb2:
    if rodando and not pausado:
        if st.button("⏸ PAUSAR", use_container_width=True, key="pausar_qr"):
            pausar()
            st.rerun()
    elif pausado:
        if st.button("▶️ CONTINUAR", use_container_width=True, key="continuar_qr"):
            retomar()
            st.rerun()
with cb3:
    if st.button("🗑️ LIMPAR LOGS", use_container_width=True, key="logs_qr"):
        limpar_logs()
        st.rerun()

if iniciar_qr and arquivo_bytes and senha and email:
    t = threading.Thread(
        target=thread_qrpedir,
        args=(email, senha, arquivo_bytes, nome_arquivo, grupos_ignorar, similaridade_minima),
        daemon=True,
    )
    t.start()
    time.sleep(0.5)
    st.rerun()


# ──────────────────────────────────────────
# Logs em tempo real
# ──────────────────────────────────────────

st.subheader("📋 Logs em tempo real")

logs = ler_logs()
if logs:
    linhas_html = ""
    for log in logs:
        classe = f"log-{log['tipo']}"
        msg = log["msg"].replace("<", "&lt;").replace(">", "&gt;")
        linhas_html += f'<div class="{classe}">{msg}</div>'
    st.markdown(f'<div class="log-box">{linhas_html}</div>', unsafe_allow_html=True)
else:
    st.info("Logs aparecerão aqui quando o robô iniciar.")

if rodando:
    time.sleep(1)
    st.rerun()
