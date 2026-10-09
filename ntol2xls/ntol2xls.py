# ntOL2XLS.py - Ollama Library 2 XLS (versione robusta con retry)

import requests
import pandas as pd
from bs4 import BeautifulSoup
from time import sleep
import re
import json
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://ollama.com"

# File di checkpoint per riprendere in caso di interruzione
CHECKPOINT_FILE = "ollama_checkpoint.json"
OUTPUT_FILE = "ollama_models.xlsx"

headers_normal = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

headers_htmx = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "HX-Request": "true",
    "HX-Trigger": "revealed",
}


def create_robust_session():
    """
    Crea una sessione HTTP con retry automatico e connection pooling.
    Questo riutilizza la stessa connessione TCP invece di aprirne una nuova ogni volta.
    """
    session = requests.Session()
    session.headers.update(headers_normal)

    # Configura retry con backoff esponenziale
    retry_strategy = Retry(
        total=5,  # 5 tentativi totali
        backoff_factor=2,  # Aspetta 2, 4, 8, 16, 32 secondi tra i retry
        status_forcelist=[429, 500, 502, 503, 504],  # Retry su questi errori HTTP
        allowed_methods=["GET"],
    )

    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


def parse_pulls(text):
    """Converte stringhe come '14.5M', '22.2K', '4,551' in numeri interi."""
    if not text:
        return 0
    text = text.strip().replace(",", "")
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    for suffix, mult in multipliers.items():
        if text.upper().endswith(suffix):
            try:
                return int(float(text[:-1]) * mult)
            except ValueError:
                return 0
    try:
        return int(text)
    except ValueError:
        return 0


def get_all_models_from_search(session):
    """Estrae tutti i modelli dalla search page con paginazione HTMX."""
    all_models = []
    page = 1

    print("Caricamento modelli dalla search page...")

    while True:
        url = f"{BASE_URL}/search?page={page}"
        h = headers_normal if page == 1 else headers_htmx

        try:
            response = session.get(url, headers=h, timeout=30)
            if response.status_code != 200:
                print(f"  Pagina {page}: errore HTTP {response.status_code}")
                break
        except Exception as e:
            print(f"  Pagina {page}: errore {e}")
            # Retry con backoff
            sleep(5 * page)
            try:
                response = session.get(url, headers=h, timeout=60)
                if response.status_code != 200:
                    break
            except Exception as e2:
                print(f"  Pagina {page}: errore dopo retry: {e2}")
                break

        soup = BeautifulSoup(response.text, "html.parser")
        model_cards = soup.find_all("a", href=True)
        model_cards = [a for a in model_cards if a.get("href", "").startswith("/library/")]

        if not model_cards:
            print(f"  Pagina {page}: nessun modello trovato, fine.")
            break

        for card in model_cards:
            model_data = extract_model_from_card(card)
            if model_data:
                all_models.append(model_data)

        print(f"  Pagina {page}: {len(model_cards)} modelli (totale: {len(all_models)})")

        # Controlla se c'è una pagina successiva
        next_page_found = False
        for tag in soup.find_all(attrs={"hx-get": True}):
            if "page=" in tag.get("hx-get", ""):
                next_page_found = True
                break

        if not next_page_found:
            break

        page += 1
        sleep(0.5)

    return all_models


def extract_model_from_card(card):
    """Estrae i dati da una card modello nella search page."""
    href = card.get("href", "")
    model_name = href.replace("/library/", "")
    if not model_name:
        return None

    name_span = card.find(attrs={"x-test-search-response-title": True})
    name = name_span.get_text(strip=True) if name_span else model_name

    desc_p = card.find("p", class_=re.compile(r"max-w-lg|break-words"))
    description = desc_p.get_text(strip=True) if desc_p else ""

    capabilities = set()
    for cap_span in card.find_all(attrs={"x-test-capability": True}):
        cap = cap_span.get_text(strip=True).lower()
        if cap:
            capabilities.add(cap)

    pull_span = card.find(attrs={"x-test-pull-count": True})
    pulls_text = pull_span.get_text(strip=True) if pull_span else ""
    pulls = parse_pulls(pulls_text)

    tag_span = card.find(attrs={"x-test-tag-count": True})
    tag_count = tag_span.get_text(strip=True) if tag_span else ""

    updated_span = card.find(attrs={"x-test-updated": True})
    updated_relative = updated_span.get_text(strip=True) if updated_span else ""

    updated_absolute = ""
    if updated_span:
        parent = updated_span.parent
        if parent and parent.get("title"):
            updated_absolute = parent["title"]

    return {
        "name": name,
        "description": description,
        "pulls": pulls,
        "pulls_text": pulls_text,
        "tags_count": tag_count,
        "updated_relative": updated_relative,
        "updated_absolute": updated_absolute,
        "vision": "vision" in capabilities,
        "tools": "tools" in capabilities,
        "thinking": "thinking" in capabilities,
        "cloud": "cloud" in capabilities,
        "audio": "audio" in capabilities,
        "embedding": "embedding" in capabilities,
        "capabilities": ", ".join(sorted(capabilities)) if capabilities else "",
        "url": f"{BASE_URL}/library/{model_name}",
    }


def get_model_details(session, model_name):
    """Visita la pagina del modello per estrarre dati aggiuntivi."""
    url = f"{BASE_URL}/library/{model_name}"

    try:
        response = session.get(url, timeout=30)
        if response.status_code != 200:
            return {}

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text()

        details = {
            "context_window": "",
            "parameter_size": "",
            "variants_count": 0,
            "variants": [],
        }

        # Context window
        context_matches = re.findall(r'(\d+[kKmM]?)\s*context\s*window', text, re.IGNORECASE)
        if context_matches:
            def context_to_num(c):
                c = c.strip().upper()
                if c.endswith("K"):
                    return int(c[:-1]) * 1000
                elif c.endswith("M"):
                    return int(c[:-1]) * 1000000
                try:
                    return int(c)
                except:
                    return 0

            max_context = max(context_matches, key=context_to_num)
            details["context_window"] = max_context

        # Parameter size
        param_matches = re.findall(r'(\d+(?:\.\d+)?)\s*[Bb](?:\s*(?:parameter|active|total))?', text)
        if param_matches:
            try:
                max_param = max(float(p) for p in param_matches)
                details["parameter_size"] = f"{max_param}B"
            except:
                pass

        # Varianti
        variant_divs = soup.find_all("div", class_=re.compile(r"overflow-hidden.*rounded-lg.*border"))

        for div in variant_divs:
            p_tag = div.find("p")
            if not p_tag:
                continue

            p_text = p_tag.get_text(strip=True)
            tag_link = div.find("a", href=re.compile(rf"/library/{re.escape(model_name)}:"))
            tag_name = ""
            if tag_link:
                tag_name = tag_link.get_text(strip=True).split("\n")[0].strip()

            if not tag_name and "·" in p_text:
                continue

            parts = [p.strip() for p in p_text.split("·")]
            variant = {
                "tag": tag_name,
                "size": parts[0] if len(parts) > 0 else "",
                "context": "",
                "input_types": "",
                "updated": parts[-1] if len(parts) > 3 else "",
            }

            for part in parts:
                if "context" in part.lower():
                    variant["context"] = part
                elif any(t in part.lower() for t in ["text", "image", "audio", "video"]):
                    variant["input_types"] = part

            if variant["tag"] or variant["size"]:
                details["variants"].append(variant)

        details["variants_count"] = len(details["variants"])
        return details

    except Exception as e:
        print(f"  ⚠️  Errore dettagli {model_name}: {e}")
        return {}


def save_checkpoint(models, completed_names):
    """Salva lo stato corrente per poter riprendere in caso di errore."""
    checkpoint = {
        "completed": completed_names,
        "models": models,
    }
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)


def load_checkpoint():
    """Carica lo stato precedente se esiste."""
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def main():
    print("=" * 60)
    print("ntOL2XLS - Ollama Library 2 XLS (versione robusta)")
    print("=" * 60)

    # Crea sessione robusta con retry automatico
    session = create_robust_session()

    # Controlla se c'è un checkpoint precedente
    checkpoint = load_checkpoint()
    if checkpoint:
        print(f"\n⚡ Trovato checkpoint con {len(checkpoint['completed'])} modelli già elaborati.")
        response = input("Vuoi riprendere da dove eri rimasto? (s/n): ").strip().lower()
        if response == 's':
            models = checkpoint["models"]
            completed = set(checkpoint["completed"])
            print(f"Riprendo da {len(completed)} modelli completati.")
        else:
            models = get_all_models_from_search(session)
            completed = set()
            os.remove(CHECKPOINT_FILE)
    else:
        models = get_all_models_from_search(session)
        completed = set()

    print(f"\nTotale modelli trovati: {len(models)}")

    if not models:
        print("Nessun modello trovato. Uscita.")
        return

    # Fase 2: Dettagli aggiuntivi (con delay maggiore e salvataggio progressivo)
    fetch_details = True  # ⚠️ Metti False se non ti servono context/parametri/varianti

    if fetch_details:
        print("\nEstrazione dettagli aggiuntivi...")
        print("⚠️  Se non ti servono context window/parametri/varianti, imposta fetch_details=False")
        print("   (così lo script impiega ~5 secondi invece di ~5 minuti)\n")

        # Delay più lungo per evitare rate limiting
        DELAY_BETWEEN_REQUESTS = 1.5  # secondi
        SAVE_EVERY = 10  # Salva checkpoint ogni N modelli

        for n, model in enumerate(models, start=1):
            model_name = model["url"].split("/library/")[-1]

            # Salta se già elaborato (resume)
            if model_name in completed:
                print(f"  [{n}/{len(models)}] {model_name}... già fatto, salto")
                continue

            print(f"  [{n}/{len(models)}] {model_name}...", end=" ", flush=True)

            details = get_model_details(session, model_name)

            if details:
                model["context_window"] = details.get("context_window", "")
                model["parameter_size"] = details.get("parameter_size", "")
                model["variants_count"] = details.get("variants_count", 0)
                variants = details.get("variants", [])
                if variants:
                    var_strs = []
                    for v in variants[:10]:
                        s = f"{v['tag']}: {v['size']}"
                        if v['context']:
                            s += f" ({v['context']})"
                        var_strs.append(s)
                    model["variants_summary"] = " | ".join(var_strs)
                else:
                    model["variants_summary"] = ""
            else:
                model["context_window"] = ""
                model["parameter_size"] = ""
                model["variants_count"] = 0
                model["variants_summary"] = ""

            completed.add(model_name)
            print("✓")

            # Salva checkpoint periodicamente
            if n % SAVE_EVERY == 0:
                save_checkpoint(models, list(completed))
                print(f"    💾 Checkpoint salvato ({len(completed)}/{len(models)})")

            # Delay tra le richieste per evitare rate limiting
            sleep(DELAY_BETWEEN_REQUESTS)

        # Salva checkpoint finale
        save_checkpoint(models, list(completed))
    else:
        print("\nSalto estrazione dettagli (fetch_details=False)")
        for model in models:
            model["context_window"] = ""
            model["parameter_size"] = ""
            model["variants_count"] = 0
            model["variants_summary"] = ""

    # Fase 3: Crea Excel
    df = pd.DataFrame(models)

    column_order = [
        "name", "description", "pulls", "pulls_text", "tags_count",
        "updated_relative", "updated_absolute", "parameter_size",
        "context_window", "variants_count", "variants_summary",
        "vision", "tools", "thinking", "cloud", "audio", "embedding",
        "capabilities", "url",
    ]

    for col in column_order:
        if col not in df.columns:
            df[col] = ""

    df = df[column_order]
    df = df.sort_values("pulls", ascending=False)

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Modelli")

        worksheet = writer.sheets["Modelli"]

        col_widths = {
            "A": 25, "B": 60, "C": 12, "D": 12, "E": 10,
            "F": 15, "G": 25, "H": 12, "I": 15, "J": 12,
            "K": 60, "L": 8, "M": 8, "N": 8, "O": 8,
            "P": 8, "Q": 10, "R": 30, "S": 40,
        }

        for col_letter, width in col_widths.items():
            worksheet.column_dimensions[col_letter].width = width

        for row in range(2, len(df) + 2):
            for col_idx in range(12, 18):  # Colonne booleane
                cell = worksheet.cell(row=row, column=col_idx)
                cell.value = "Sì" if cell.value else "No"

    # Pulisci il checkpoint
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

    print(f"\n{'=' * 60}")
    print(f"✅ File creato: {OUTPUT_FILE}")
    print(f"   Totale modelli: {len(df)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()