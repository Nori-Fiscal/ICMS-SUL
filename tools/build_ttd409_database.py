import csv
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import requests
from lxml import html


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_CSV = DATA_DIR / "ttd409_exclusions.csv"
OUT_SUMMARY = DATA_DIR / "ttd409_summary.json"

DEC_2128_URL = "https://legislacao.sef.sc.gov.br/html/decretos/2009/dec_09_2128.htm"
DEC_1453_URL = "https://legislacao.sef.sc.gov.br/html/decretos/2026/dec_26_1453.htm"


CSV_COLUMNS = [
    "item",
    "ncm",
    "ncm_formatado",
    "match_tipo",
    "prefix_len",
    "descricao_legal",
    "observacao",
    "fonte_url",
    "fonte_atualizacao",
]


def clean(text: str) -> str:
    text = "" if text is None else str(text)
    text = text.replace("\xa0", " ").replace("\n", " ").strip()
    return re.sub(r"\s+", " ", text)


def ascii_key(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").upper()


def format_ncm(code: str) -> str:
    if len(code) == 8:
        return f"{code[:4]}.{code[4:6]}.{code[6:]}"
    if len(code) == 6:
        return f"{code[:4]}.{code[4:]}"
    return code


def expand_range(start: str, end: str) -> list[str]:
    if len(start) != len(end) or not start.isdigit() or not end.isdigit():
        return []
    a, b = int(start), int(end)
    if b < a or b - a > 100:
        return []
    width = len(start)
    return [str(n).zfill(width) for n in range(a, b + 1)]


def extract_ncms(text: str) -> list[str]:
    body = re.sub(r"^\d+(?:\.\d+)?\.\s*", "", clean(text))
    codes: set[str] = set()

    for start, end in re.findall(r"(?<!\d)(\d{4})\s+a\s+(\d{4})(?!\d)", body):
        codes.update(expand_range(start, end))

    for raw in re.findall(r"(?<!\d)(\d{2,4}(?:\.\d{1,2}){1,3})(?!\d)|(?<!\d)(\d{4,8})(?!\d)", body):
        value = raw[0] or raw[1]
        digits = re.sub(r"\D", "", value)
        if 4 <= len(digits) <= 8:
            codes.add(digits)

    return sorted(codes, key=lambda c: (len(c), c))


def current_anexo_items() -> list[tuple[str, str]]:
    response = requests.get(DEC_2128_URL, timeout=60)
    response.raise_for_status()
    doc = html.fromstring(response.content.decode("windows-1252", errors="replace"))

    started = False
    items = []
    for p in doc.xpath("//p"):
        cls = clean(p.get("class", ""))
        text = clean(p.text_content())
        if not text:
            continue
        if ascii_key(text).startswith("ANEXO UNICO"):
            started = True
        if not started or "passada" in cls.lower():
            continue

        match = re.match(r"(\d+(?:\.\d+)?)\.\s*(.*)", text)
        if match and extract_ncms(text):
            items.append((match.group(1), text))
    return items


def build_rows() -> list[dict[str, str]]:
    rows = []
    seen = set()
    for item, description in current_anexo_items():
        observation = (
            "Itens 62 a 76: vedacao condicionada a mercadorias destinadas ao uso na agricultura ou pecuaria, conforme Decreto SC 1.453/2026."
            if item.isdigit() and 62 <= int(item) <= 76
            else "Mercadoria relacionada no Anexo Unico do Decreto SC 2.128/2009: risco de nao aplicacao do TTD409."
        )
        for ncm in extract_ncms(description):
            key = (item, ncm)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "item": item,
                    "ncm": ncm,
                    "ncm_formatado": format_ncm(ncm),
                    "match_tipo": "exato" if len(ncm) == 8 else "prefixo",
                    "prefix_len": str(len(ncm)),
                    "descricao_legal": description,
                    "observacao": observation,
                    "fonte_url": DEC_2128_URL,
                    "fonte_atualizacao": "2026-06-09",
                }
            )
    return rows


def write_outputs(rows: list[dict[str, str]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rows": len(rows),
        "items": len({r["item"] for r in rows}),
        "prefixes": len({r["ncm"] for r in rows if r["match_tipo"] == "prefixo"}),
        "exact": len({r["ncm"] for r in rows if r["match_tipo"] == "exato"}),
        "sources": [DEC_2128_URL, DEC_1453_URL],
        "notes": [
            "A verificacao automatica cruza NCM/prefixo. A confirmacao final depende da descricao legal e da mercadoria importada.",
            "Itens 62 a 76 possuem regra condicionada ao uso na agricultura ou pecuaria pelo Decreto SC 1.453/2026.",
        ],
    }
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    rows = build_rows()
    write_outputs(rows)
    print(f"CSV: {OUT_CSV}")
    print(f"Linhas: {len(rows)}")
    print(f"Itens legais: {len({r['item'] for r in rows})}")


if __name__ == "__main__":
    main()
