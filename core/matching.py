import io
import re
import unicodedata
from difflib import SequenceMatcher

import pandas as pd


# ──────────────────────────────────────────
# Normalização de texto
# ──────────────────────────────────────────

def normalizar(texto: str) -> str:
    """
    Remove acentos, converte para minúsculas, elimina espaços duplicados
    e caracteres especiais. Ex: "X-Burguer Duplo" → "x burguer duplo"
    """
    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ASCII", "ignore").decode("utf-8")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return texto.strip()


# ──────────────────────────────────────────
# Similaridade e busca
# ──────────────────────────────────────────

def similaridade(a: str, b: str) -> float:
    """Retorna a similaridade entre duas strings normalizadas (0 a 1)."""
    return SequenceMatcher(None, normalizar(a), normalizar(b)).ratio()


def detectar_colunas(df: pd.DataFrame) -> tuple[str, str]:
    """Detecta automaticamente qual coluna é o ID e qual é a descrição."""
    col_desc = next(
        (c for c in df.columns if "desc" in normalizar(c)),
        df.columns[1] if len(df.columns) > 1 else df.columns[0],
    )
    col_id = next(
        (c for c in df.columns if normalizar(c) in ["id", "codigo", "code", "cod"]),
        df.columns[0],
    )
    return col_id, col_desc


def buscar_codigo(
    nome_item: str,
    df: pd.DataFrame,
    limite: float,
    col_id: str,
    col_desc: str,
) -> tuple[str | None, float, str | None]:
    """Busca o código mais similar ao nome do item na planilha."""
    melhor_score = 0.0
    melhor_linha = None

    for _, row in df.iterrows():
        nome_plan = str(row.get(col_desc, "") or "").strip()
        if not nome_plan:
            continue
        score = similaridade(nome_item, nome_plan)
        if score > melhor_score:
            melhor_score = score
            melhor_linha = row

    if melhor_score >= limite and melhor_linha is not None:
        codigo    = str(melhor_linha.get(col_id, "")).strip()
        nome_plan = str(melhor_linha.get(col_desc, "")).strip()
        return codigo, melhor_score, nome_plan

    return None, melhor_score, None


# ──────────────────────────────────────────
# Carregamento de planilha
# ──────────────────────────────────────────

def carregar_planilha(arquivo_bytes: bytes, nome_arquivo: str) -> pd.DataFrame:
    """Carrega Excel ou CSV e normaliza os nomes das colunas."""
    nome_lower = nome_arquivo.lower()
    if nome_lower.endswith(".xls"):
        df = pd.read_excel(io.BytesIO(arquivo_bytes), engine="xlrd")
    elif nome_lower.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(arquivo_bytes))
    else:
        df = pd.read_excel(io.BytesIO(arquivo_bytes), engine="openpyxl")

    df.columns = [c.strip().replace("/", "").strip() for c in df.columns]
    return df
