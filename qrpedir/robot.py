import time

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from qrpedir.config import HEADLESS, URL_LOGIN, URL_CARDAPIO, USER_AGENT
from core.logger import add_log
from core.matching import buscar_codigo, detectar_colunas
from core.progress import salvar_progresso, esta_pausado


# ──────────────────────────────────────────
# Ponto de entrada
# ──────────────────────────────────────────

def executar_robo(
    email: str,
    senha: str,
    df: pd.DataFrame,
    grupos_ignorar: list[str],
    similaridade_minima: float,
    itens_salvos: set,
) -> dict:
    stats = {"ok": 0, "nao_encontrado": 0, "erro": 0}

    col_id, col_desc = detectar_colunas(df)
    add_log(f"Coluna de ID detectada: '{col_id}'", "info")
    add_log(f"Coluna de descrição detectada: '{col_desc}'", "info")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        page = browser.new_page(user_agent=USER_AGENT)

        if not _fazer_login(page, email, senha):
            browser.close()
            return stats

        page.goto(URL_CARDAPIO, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        grupos_nomes = _pegar_nomes_grupos(page)
        add_log(f"{len(grupos_nomes)} grupos encontrados.", "info")

        for nome_grupo in grupos_nomes:
            while esta_pausado():
                time.sleep(1)

            if any(ign.lower() in nome_grupo.lower() for ign in grupos_ignorar):
                add_log(f"Pulando grupo: {nome_grupo}", "warn")
                continue

            add_log(f"--- Grupo: {nome_grupo} ---", "info")
            _processar_grupo(page, nome_grupo, df, col_id, col_desc, similaridade_minima, itens_salvos, stats)

        browser.close()

    return stats


# ──────────────────────────────────────────
# Login
# ──────────────────────────────────────────

def _fazer_login(page, email: str, senha: str) -> bool:
    try:
        add_log("Acessando página de login...", "info")
        page.goto(URL_LOGIN, wait_until="domcontentloaded", timeout=20_000)
        page.wait_for_timeout(2000)
        page.fill('input[name="username"]', email)
        page.fill('input[name="password"]', senha)
        page.click('button:has-text("ENTRAR")')
        page.wait_for_url(lambda url: "login" not in url, timeout=15_000)
        add_log("Login realizado com sucesso!", "ok")
        return True
    except PlaywrightTimeout:
        add_log("Timeout no login — verifique e-mail, senha e conexão.", "erro")
        return False
    except Exception as e:
        add_log(f"Erro inesperado no login: {e}", "erro")
        return False


# ──────────────────────────────────────────
# Grupos
# ──────────────────────────────────────────

def _pegar_nomes_grupos(page) -> list[str]:
    nomes = []
    for g in page.query_selector_all(".MuiAccordionSummary-root"):
        try:
            nome = g.query_selector("h6").inner_text().strip()
        except Exception:
            nome = g.inner_text().split("\n")[0].strip()
        if nome:
            nomes.append(nome)
    return nomes


def _pegar_elemento_grupo(page, nome_grupo: str):
    for g in page.query_selector_all(".MuiAccordionSummary-root"):
        try:
            nome = g.query_selector("h6").inner_text().strip()
        except Exception:
            nome = g.inner_text().split("\n")[0].strip()
        if nome == nome_grupo:
            return g
    return None


def _pegar_lapises(page) -> list[dict]:
    js = """
    () => {
        const path = 'M3 17.25V21h3.75L17.81 9.94l-3.75-3.75';
        return Array.from(document.querySelectorAll('li button, [class*=MuiListItem] button'))
            .map((btn) => {
                const hasPencil = Array.from(btn.querySelectorAll('path'))
                    .some(p => (p.getAttribute('d') || '').startsWith(path));
                if (!hasPencil) return null;
                const linha = btn.closest('li') || btn.closest('[class*=MuiListItem]');
                if (!linha) return null;
                if (!(linha.innerText || '').includes('R$')) return null;
                const nome = (linha.querySelector('[class*=MuiTypography]') || {}).innerText || '';
                return { nome: nome.trim() };
            })
            .filter(x => x !== null && x.nome.length > 2);
    }
    """
    return page.evaluate(js)


def _clicar_lapis_por_nome(page, nome_item: str) -> bool:
    js = """
    (nomeAlvo) => {
        const path = 'M3 17.25V21h3.75L17.81 9.94l-3.75-3.75';
        const btns = Array.from(document.querySelectorAll('li button, [class*=MuiListItem] button'));
        for (const btn of btns) {
            const hasPencil = Array.from(btn.querySelectorAll('path'))
                .some(p => (p.getAttribute('d') || '').startsWith(path));
            if (!hasPencil) continue;
            const linha = btn.closest('li') || btn.closest('[class*=MuiListItem]');
            if (!linha || !(linha.innerText || '').includes('R$')) continue;
            const nome = ((linha.querySelector('[class*=MuiTypography]') || {}).innerText || '').trim();
            if (nome === nomeAlvo) {
                btn.scrollIntoView({ block: 'center' });
                btn.click();
                return true;
            }
        }
        return false;
    }
    """
    return page.evaluate(js, nome_item)


# ──────────────────────────────────────────
# Processamento de grupo e itens
# ──────────────────────────────────────────

def _processar_grupo(page, nome_grupo, df, col_id, col_desc, similaridade_minima, itens_salvos, stats):
    grupo_el = _pegar_elemento_grupo(page, nome_grupo)
    if not grupo_el:
        add_log("  Grupo não encontrado no DOM.", "erro")
        return

    try:
        if grupo_el.get_attribute("aria-expanded") != "true":
            grupo_el.click()
            page.wait_for_timeout(1500)
        grupo_el.scroll_into_view_if_needed()
    except Exception:
        pass
    page.wait_for_timeout(500)

    lapises = _pegar_lapises(page)
    add_log(f"  {len(lapises)} itens no grupo.", "info")

    for item_info in lapises:
        while esta_pausado():
            time.sleep(1)

        nome_item = item_info["nome"]
        chave = f"{nome_grupo}|{nome_item}"

        if chave in itens_salvos:
            add_log(f"  Já processado: {nome_item}", "warn")
            continue

        _processar_item(page, nome_item, chave, df, col_id, col_desc, similaridade_minima, itens_salvos, stats)


def _processar_item(page, nome_item, chave, df, col_id, col_desc, similaridade_minima, itens_salvos, stats):
    add_log(f"  Item: {nome_item}", "info")

    codigo, score, nome_plan = buscar_codigo(nome_item, df, similaridade_minima, col_id, col_desc)

    if not codigo:
        add_log(f"  Não encontrado (melhor match: {score:.0%})", "warn")
        stats["nao_encontrado"] += 1
        itens_salvos.add(chave)
        salvar_progresso(itens_salvos, robo="qrpedir")
        return

    add_log(f"  Match: '{nome_plan}' ({score:.0%}) → {codigo}", "ok")

    try:
        clicou = _clicar_lapis_por_nome(page, nome_item)
        if not clicou:
            add_log(f"  Botão de edição não encontrado para: {nome_item}", "erro")
            stats["erro"] += 1
            return

        page.wait_for_timeout(2000)
        modal = page.query_selector("[role='dialog']")
        if not modal:
            add_log("  Modal não abriu.", "erro")
            stats["erro"] += 1
            return

        campo_id = modal.query_selector('input[name="codigoExterno"]')
        if campo_id:
            campo_id.click()
            page.keyboard.press("Control+a")
            page.wait_for_timeout(200)
            campo_id.fill(str(codigo))
            page.wait_for_timeout(500)

            salvar_btn = modal.query_selector("button:has-text('SALVAR')")
            if salvar_btn:
                salvar_btn.click()
                page.wait_for_timeout(2000)
                add_log("  Id Exterior salvo!", "ok")
                stats["ok"] += 1
            else:
                add_log("  Botão SALVAR não encontrado.", "erro")
                stats["erro"] += 1
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
                itens_salvos.add(chave)
                salvar_progresso(itens_salvos, robo="qrpedir")
                return
        else:
            add_log("  Campo codigoExterno não encontrado.", "erro")
            stats["erro"] += 1
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
            itens_salvos.add(chave)
            salvar_progresso(itens_salvos, robo="qrpedir")
            return

        # Reabre para processar complementos
        page.wait_for_timeout(500)
        clicou2 = _clicar_lapis_por_nome(page, nome_item)
        if clicou2:
            page.wait_for_timeout(2000)
            modal = page.query_selector("[role='dialog']")
            if modal:
                _processar_complementos(page, modal, df, col_id, col_desc, similaridade_minima, stats)
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)

        itens_salvos.add(chave)
        salvar_progresso(itens_salvos, robo="qrpedir")
        page.wait_for_timeout(800)

    except Exception as e:
        add_log(f"  Erro inesperado: {e}", "erro")
        stats["erro"] += 1
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
        except Exception:
            pass


def _processar_complementos(page, modal, df, col_id, col_desc, similaridade_minima, stats):
    try:
        abas = modal.query_selector_all("[role='tab']")
        aba_comp = next((a for a in abas if "COMPL" in a.inner_text().upper()), None)
        if not aba_comp:
            return
        aba_comp.click()
        page.wait_for_timeout(1500)
    except Exception as e:
        add_log(f"    Erro ao abrir aba COMPLEMENTOS: {e}", "warn")
        return

    editar_btns = modal.query_selector_all("button.MuiButton-root:has-text('EDITAR')")
    if not editar_btns:
        add_log("    Sem complementos.", "info")
        return

    add_log(f"    {len(editar_btns)} complemento(s).", "info")

    for i in range(len(editar_btns)):
        editar_btns_atual = modal.query_selector_all("button.MuiButton-root:has-text('EDITAR')")
        if i >= len(editar_btns_atual):
            break

        try:
            acordeoes = modal.query_selector_all(".MuiAccordionSummary-root")
            nome_comp = acordeoes[i].inner_text().split("\n")[0].strip() if i < len(acordeoes) else f"Complemento {i+1}"
        except Exception:
            nome_comp = f"Complemento {i+1}"

        add_log(f"    Complemento: {nome_comp}", "info")
        editar_btns_atual[i].click()
        page.wait_for_timeout(1500)

        _preencher_itens_complemento(page, modal, df, col_id, col_desc, similaridade_minima, stats)

        salvar_comp = modal.query_selector("button:has-text('SALVAR COMPLEMENTO')")
        if salvar_comp:
            salvar_comp.click()
            page.wait_for_timeout(1500)
            add_log("    Complemento salvo!", "ok")
        else:
            add_log("    Botão SALVAR COMPLEMENTO não encontrado.", "warn")


def _preencher_itens_complemento(page, modal, df, col_id, col_desc, similaridade_minima, stats):
    inputs = modal.query_selector_all("input")
    itens_comp = []

    for i, inp in enumerate(inputs):
        name        = inp.get_attribute("name") or ""
        placeholder = inp.get_attribute("placeholder") or ""
        if name == "descricao" and "MARGHERITA" in placeholder.upper():
            nome_val = inp.evaluate("el => el.value").strip()
            for j in range(i + 1, min(i + 5, len(inputs))):
                if inputs[j].get_attribute("name") == "codigoExterno":
                    itens_comp.append({"nome": nome_val, "campo": inputs[j]})
                    break

    if not itens_comp:
        add_log("      Nenhum item no complemento.", "info")
        return

    add_log(f"      {len(itens_comp)} item(ns).", "info")

    for item in itens_comp:
        nome_item = item["nome"]
        campo     = item["campo"]
        codigo, score, nome_plan = buscar_codigo(nome_item, df, similaridade_minima, col_id, col_desc)

        if not codigo:
            add_log(f"      Não encontrado: {nome_item} ({score:.0%})", "warn")
            stats["nao_encontrado"] += 1
            continue

        add_log(f"      {nome_item} → {nome_plan} ({score:.0%}) → {codigo}", "ok")
        try:
            campo.click()
            page.keyboard.press("Control+a")
            page.wait_for_timeout(100)
            campo.fill(str(codigo))
            page.wait_for_timeout(300)
            stats["ok"] += 1
        except Exception as e:
            add_log(f"      Erro ao preencher: {e}", "erro")
            stats["erro"] += 1
