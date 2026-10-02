"""Measure the token tax of every FLORES+ language on every tokenizer -> docs/tax.json (the site) and src/tokentax/tax.json (shipped with the CLI).

    uv run --group data scripts/build_data.py

FLORES+ is gated: accept its terms on Hugging Face and log in (`hf auth login`) first.
Only token and character counts are written out, never the FLORES+ text itself.
"""
import json
import os
import sys

import pycountry

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from tokentax.cli import FLORES, REF, SPLIT, TOKENIZERS, counter, flores, tax  # noqa: E402

def label(rows):
    r = rows[0]
    lang = pycountry.languages.get(alpha_3=r["iso_639_3"])
    script = pycountry.scripts.get(alpha_4=r["iso_15924"])
    name = getattr(lang, "name", r["iso_639_3"])
    extra = r.get("variant") or ""
    return name + (f" ({extra})" if extra else ""), getattr(script, "name", r["iso_15924"])


def main():
    revision, langs = flores()
    measured = {lab: tax(counter(*spec), langs) for lab, spec in TOKENIZERS.items()}
    ref_ids = {r["id"] for r in langs[REF]}
    out = []
    for code, rows in langs.items():
        rows = [r for r in rows if r["id"] in ref_ids]
        name, script = label(rows)
        out.append({"code": code, "name": name, "script": script, "sentences": len(rows),
                    "chars": sum(len(r["text"]) for r in rows),
                    "tax": {lab: round(t[code], 4) for lab, (t, _) in measured.items()},
                    "tokens": {lab: n[code] for lab, (_, n) in measured.items()}})
    data = {"source": f"{FLORES} ({SPLIT}, revision {revision[:12]})", "license": "CC BY-SA 4.0",
            "reference": REF, "tokenizers": {l: list(s) for l, s in TOKENIZERS.items()}, "languages": out}
    for path in ("docs/tax.json", "src/tokentax/tax.json"):  # the site's copy and the one `tokentax eval` ships with
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"wrote docs/tax.json and src/tokentax/tax.json: {len(out)} languages x {len(measured)} tokenizers")


if __name__ == "__main__":
    main()
