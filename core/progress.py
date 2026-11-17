import os
import json
from core.logger import add_log

STATUS_FILE  = "robo_status.txt"
PAUSE_FILE   = "robo_pause.txt"


def _arquivo_progresso(robo: str) -> str:
    return f"progresso_{robo}.json"


# ──────────────────────────────────────────
# Progresso
# ──────────────────────────────────────────

def salvar_progresso(itens_salvos: set, robo: str = "default") -> None:
    with open(_arquivo_progresso(robo), "w", encoding="utf-8") as f:
        json.dump(list(itens_salvos), f, ensure_ascii=False)


def carregar_progresso(robo: str = "default") -> set:
    arq = _arquivo_progresso(robo)
    if os.path.exists(arq):
        try:
            with open(arq, "r", encoding="utf-8") as f:
                dados = json.load(f)
            add_log(f"Progresso anterior: {len(dados)} itens já processados. Continuando...", "warn")
            return set(dados)
        except Exception:
            pass
    return set()


def limpar_progresso(robo: str = "default") -> None:
    arq = _arquivo_progresso(robo)
    if os.path.exists(arq):
        os.remove(arq)


def tem_progresso(robo: str = "default") -> bool:
    return os.path.exists(_arquivo_progresso(robo))


def contar_progresso(robo: str = "default") -> int:
    try:
        with open(_arquivo_progresso(robo), "r", encoding="utf-8") as f:
            return len(json.load(f))
    except Exception:
        return 0


# ──────────────────────────────────────────
# Status do robô (compartilhado entre abas)
# ──────────────────────────────────────────

def set_rodando(valor: bool) -> None:
    if valor:
        with open(STATUS_FILE, "w") as f:
            f.write("1")
    else:
        if os.path.exists(STATUS_FILE):
            os.remove(STATUS_FILE)


def esta_rodando() -> bool:
    return os.path.exists(STATUS_FILE)


def pausar() -> None:
    with open(PAUSE_FILE, "w") as f:
        f.write("1")


def retomar() -> None:
    if os.path.exists(PAUSE_FILE):
        os.remove(PAUSE_FILE)


def esta_pausado() -> bool:
    return os.path.exists(PAUSE_FILE)
