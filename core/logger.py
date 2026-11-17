import os
import time

LOG_FILE = "robo_logs.txt"


def add_log(msg: str, tipo: str = "info") -> None:
    """Adiciona uma linha ao arquivo de log."""
    hora = time.strftime("%H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{tipo}|[{hora}] {msg}\n")


def limpar_logs() -> None:
    """Remove o arquivo de log."""
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)


def ler_logs(ultimas: int = 200) -> list[dict]:
    """Lê as últimas N linhas do log e retorna lista de dicts."""
    logs = []
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                linhas = f.readlines()[-ultimas:]
            for linha in linhas:
                partes = linha.strip().split("|", 1)
                if len(partes) == 2:
                    logs.append({"tipo": partes[0], "msg": partes[1]})
    except Exception:
        pass
    return logs
