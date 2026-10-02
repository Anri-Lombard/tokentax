"""Measure the token tax of every FLORES+ language on every tokenizer -> data/tax.json.

    uv run --group data scripts/build_data.py

FLORES+ is gated: accept its terms on Hugging Face and log in (`hf auth login`) first.
Only token and character counts are written out, never the FLORES+ text itself.
"""
import json
import os
import sys

import pycountry
from huggingface_hub import snapshot_download

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from tokentax.cli import TOKENIZERS, counter  # noqa: E402

REPO, SPLIT, REF = "openlanguagedata/flores_plus", "devtest", "eng_Latn"


def load():
    path = snapshot_download(REPO, repo_type="dataset", allow_patterns=[f"{SPLIT}/*"])
    revision = os.path.basename(path)
    langs = {}
    for name in sorted(os.listdir(os.path.join(path, SPLIT))):
        rows = [json.loads(l) for l in open(os.path.join(path, SPLIT, name), encoding="utf-8")]
        langs[name.removesuffix(".jsonl")] = rows
    return revision, langs


def label(rows):
    r = rows[0]
    lang = pycountry.languages.get(alpha_3=r["iso_639_3"])
    script = pycountry.scripts.get(alpha_4=r["iso_15924"])
    name = getattr(lang, "name", r["iso_639_3"])
    extra = r.get("variant") or ""
    return name + (f" ({extra})" if extra else ""), getattr(script, "name", r["iso_15924"])


def main():
    revision, langs = load()
    ref = {r["id"]: r["text"] for r in langs[REF]}
    counters = {lab: counter(*spec) for lab, spec in TOKENIZERS.items()}
    out = []
    for code, rows in langs.items():
        rows = [r for r in rows if r["id"] in ref]  # compare only sentences both sides have
        name, script = label(rows)
        entry = {"code": code, "name": name, "script": script, "sentences": len(rows),
                 "chars": sum(len(r["text"]) for r in rows), "tokens": {}, "tax": {}}
        for lab, count in counters.items():
            n = sum(count(r["text"]) for r in rows)
            n_ref = sum(count(ref[r["id"]]) for r in rows)
            entry["tokens"][lab] = n
            entry["tax"][lab] = round(n / n_ref, 4)
        out.append(entry)
        print(f"{code:22} {name[:28]:28} " + "  ".join(f"{entry['tax'][l]:5.2f}" for l in counters), flush=True)

    os.makedirs("data", exist_ok=True)
    with open("data/tax.json", "w", encoding="utf-8") as f:
        json.dump({"source": f"{REPO} ({SPLIT}, revision {revision[:12]})", "license": "CC BY-SA 4.0",
                   "reference": REF, "tokenizers": {l: list(s) for l, s in TOKENIZERS.items()},
                   "languages": out}, f, ensure_ascii=False, indent=1)
    print(f"wrote data/tax.json: {len(out)} languages x {len(counters)} tokenizers")


if __name__ == "__main__":
    main()
