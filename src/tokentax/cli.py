"""How many tokens does the same text cost across LLM tokenizers?

    tokentax "Sawubona, unjani?"
    tokentax zulu.txt --vs english.txt     # same text in both languages -> the tax
    tokentax eval my_tokenizer.json        # your tokenizer's tax on 222 languages vs the big ones
"""
import argparse
import json
import os
import statistics
import sys

# label -> (backend, id). Open tokenizers of current flagship models, as of October 2026.
# Claude and Gemini only expose token counts through their APIs (scripts/claude_counts.py adds Claude to the data);
# Llama is gated and Kimi ships no tokenizer.json.
TOKENIZERS = {
    "GPT-5 / GPT-4o": ("tiktoken", "o200k_base"),
    "GPT-4 (2023)": ("tiktoken", "cl100k_base"),
    "Qwen3.8": ("hf", "Qwen/Qwen3.8-27B-FP8"),
    "DeepSeek-V4.1": ("hf", "deepseek-ai/DeepSeek-V4.1-Flash"),
    "GLM-5.3": ("hf", "zai-org/GLM-5.3"),
    "Mistral Medium 3.5": ("hf", "mistralai/Mistral-Medium-3.5-128B"),
    "Gemma 4": ("hf", "google/gemma-4-12b-it"),
}


def counter(backend, name):
    """A function text -> token count."""
    if backend == "file":
        from tokenizers import Tokenizer

        tok = Tokenizer.from_file(name)
        return lambda text: len(tok.encode(text, add_special_tokens=False).ids)
    if backend == "tiktoken":
        import tiktoken

        enc = tiktoken.get_encoding(name)
        return lambda text: len(enc.encode(text, disallowed_special=()))
    from huggingface_hub import hf_hub_download  # uses your HF login, so private repos work

    return counter("file", hf_hub_download(name, "tokenizer.json"))


def read(arg):
    if arg == "-":
        return sys.stdin.read()
    if os.path.isfile(arg):
        with open(arg, encoding="utf-8") as f:
            return f.read()
    return arg


FLORES, SPLIT, REF = "openlanguagedata/flores_plus", "devtest", "eng_Latn"


def flores():
    """(revision, {lang code: [rows]}) for FLORES+ devtest. Gated: accept its terms on HF and log in first."""
    from huggingface_hub import snapshot_download

    path = snapshot_download(FLORES, repo_type="dataset", allow_patterns=[f"{SPLIT}/*"])
    langs = {}
    for name in sorted(os.listdir(os.path.join(path, SPLIT))):
        with open(os.path.join(path, SPLIT, name), encoding="utf-8") as f:
            langs[name.removesuffix(".jsonl")] = [json.loads(line) for line in f]
    return os.path.basename(path), langs


def tax(count, langs):
    """({lang code: tokens / tokens for the same sentences in English}, {lang code: tokens})."""
    ref = {r["id"]: r["text"] for r in langs[REF]}
    taxes, tokens = {}, {}
    for code, rows in langs.items():
        rows = [r for r in rows if r["id"] in ref]  # compare only sentences both sides have
        tokens[code] = sum(count(r["text"]) for r in rows)
        taxes[code] = tokens[code] / sum(count(ref[r["id"]]) for r in rows)
    return taxes, tokens


def spec(arg):
    """'tiktoken:o200k_base', a tokenizer.json path, or a Hugging Face repo id -> (backend, id)."""
    if arg.startswith("tiktoken:"):
        return "tiktoken", arg.split(":", 1)[1]
    return ("file", arg) if os.path.exists(arg) else ("hf", arg)


def evaluate(argv):
    p = argparse.ArgumentParser(prog="tokentax eval", description="Measure a tokenizer's tax on all FLORES+ languages "
                                "and compare it with the tokenizers behind today's models.")
    p.add_argument("tokenizer", help="tokenizer.json path, Hugging Face repo id, or tiktoken:<encoding>")
    p.add_argument("--lang", help="comma-separated FLORES+ codes to list, e.g. zul_Latn,xho_Latn")
    p.add_argument("--json", metavar="PATH", help="also write every language's tax here")
    a = p.parse_args(argv)
    with open(os.path.join(os.path.dirname(__file__), "tax.json"), encoding="utf-8") as f:
        known = json.load(f)
    names = {l["code"]: l["name"] for l in known["languages"]}
    print(f"measuring {a.tokenizer} on {len(names)} languages...", file=sys.stderr)
    mine, mine_tokens = tax(counter(*spec(a.tokenizer)), flores()[1])
    cols = {"yours": mine} | {t: {l["code"]: l["tax"][t] for l in known["languages"]} for t in known["tokenizers"]}
    eng = {"yours": mine_tokens[REF]} | {t: next(l["tokens"][t] for l in known["languages"] if l["code"] == REF)
                                          for t in known["tokenizers"]}

    # a low tax can also mean a tokenizer that is bad at English, so show English's absolute size too
    width = max(map(len, cols))
    print(f"\n{'':{width}}  {'median':>6}  {'<=1.5x':>6}  {'<=2x':>5}  {'English tok':>11}  worst")
    for label, t in cols.items():
        codes = [c for c in mine if c in t and c != REF]
        v = [t[c] for c in codes]
        worst = max(codes, key=t.get)
        print(f"{label:{width}}  {statistics.median(v):>5.2f}x  {sum(x <= 1.5 for x in v) / len(v):>6.0%}  "
              f"{sum(x <= 2 for x in v) / len(v):>5.0%}  {eng[label]:>11,}  {names.get(worst, worst)} {t[worst]:.1f}x")
    if a.lang:
        codes = a.lang.split(",")
        print(f"\n{'':22}" + "".join(f"{l[:12]:>14}" for l in cols))
        for c in codes:
            print(f"{names.get(c, c)[:22]:22}" + "".join(f"{(t[c] if c in t else float('nan')):>13.2f}x" for t in cols.values()))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"tokenizer": a.tokenizer, "reference": REF, "tax": mine, "tokens": mine_tokens}, f, indent=1)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["eval"]:
        return evaluate(argv[1:])
    p = argparse.ArgumentParser(prog="tokentax", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("text", help="text, a file path, or - for stdin")
    p.add_argument("--vs", metavar="TEXT", help="the same text in a reference language (usually English)")
    a = p.parse_args(argv)
    text = read(a.text)
    ref = read(a.vs) if a.vs else None
    if not text.strip():
        p.error("empty text")

    width = max(map(len, TOKENIZERS))
    head = f"{'':{width}}  {'tokens':>8}  {'chars/token':>11}"
    print(head + (f"  {'tax':>6}" if ref else ""))
    for label, (backend, name) in TOKENIZERS.items():
        try:
            count = counter(backend, name)
        except Exception as e:  # offline, renamed repo, ...: report and carry on with the rest
            print(f"{label:{width}}  unavailable ({type(e).__name__})")
            continue
        n = count(text)
        row = f"{label:{width}}  {n:>8,}  {len(text) / max(n, 1):>11.2f}"
        if ref:
            row += f"  {n / max(count(ref), 1):>5.2f}x"
        print(row)


if __name__ == "__main__":
    main()
