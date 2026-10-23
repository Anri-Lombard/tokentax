"""Claude's tokenizers are only reachable through Anthropic's token counting endpoint, so count every FLORES+
sentence there once and cache the raw counts in .cache/claude/<model>.jsonl. Free; needs ANTHROPIC_API_KEY.

    uv run --group data scripts/claude_counts.py

build_data.py reads the cache; rerunning this only counts sentences that are missing from it.
"""
import datetime
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from tokentax.cli import REF, flores  # noqa: E402

# one model per tokenizer: Sonnet 5.5, Haiku 5.5 and Fable 5.1 count like Opus 5.5, and Sonnet 4.6 like Haiku 4.5
CLAUDE = {"Claude Opus 5.5": "claude-opus-5-5", "Claude Haiku 4.5": "claude-haiku-4-5"}
CACHE = os.path.join(os.path.dirname(__file__), "..", ".cache", "claude")
PER_MINUTE = 4500  # stay under the endpoint's 5,000 requests per minute, which retries alone can't keep up with
_slot, _lock = [time.monotonic()], threading.Lock()


def client():
    import anthropic

    return anthropic.Anthropic(max_retries=12)  # the SDK backs off on 429s and honours retry-after


def raw(c, model, text):
    with _lock:
        _slot[0] = max(_slot[0] + 60 / PER_MINUTE, time.monotonic())
        wait = _slot[0] - time.monotonic()
    time.sleep(max(0, wait))
    return c.messages.count_tokens(model=model, messages=[{"role": "user", "content": text}]).input_tokens


def overhead(c, model):
    """Tokens the message wrapper adds to every count. A lone letter is one token, so the wrapper is the rest.
    Sentences joined by newlines must then cost their sum plus one token per newline, or the wrapper isn't constant."""
    o = raw(c, model, "a") - 1
    eng = [r["text"] for r in flores()[1][REF][:40]]
    parts = sum(raw(c, model, s) - o for s in eng)
    joined = raw(c, model, "\n".join(eng)) - o
    assert joined == parts + len(eng) - 1, (model, o, parts, joined)
    return o


def load(model):
    path = os.path.join(CACHE, f"{model}.jsonl")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {(r["code"], r["id"]): r["raw"] for r in map(json.loads, f)}


def measured_on():
    """The day the cached counts were last added to, which the site shows next to the Claude numbers."""
    last = max(os.path.getmtime(os.path.join(CACHE, f"{m}.jsonl")) for m in CLAUDE.values())
    return datetime.date.fromtimestamp(last).isoformat()


def counter(model, langs):
    """A function text -> tokens for `model`, served from the cache (every FLORES+ sentence must be in it)."""
    o, cached = overhead(client(), model), load(model)
    by_text = {r["text"]: cached[code, r["id"]] - o for code, rows in langs.items() for r in rows if (code, r["id"]) in cached}
    return lambda text: by_text[text]


def main():
    _, langs = flores()
    ref_ids = {r["id"] for r in langs[REF]}
    c = client()
    os.makedirs(CACHE, exist_ok=True)
    with ThreadPoolExecutor(96) as pool:
        for model in CLAUDE.values():
            done = load(model)
            todo = [(code, r) for code, rows in langs.items() for r in rows if r["id"] in ref_ids and (code, r["id"]) not in done]
            print(f"{model}: {len(done)} cached, {len(todo)} to count", file=sys.stderr)
            with open(os.path.join(CACHE, f"{model}.jsonl"), "a", encoding="utf-8") as f:
                for i, ((code, r), n) in enumerate(zip(todo, pool.map(lambda cr: raw(c, model, cr[1]["text"]), todo))):
                    f.write(json.dumps({"code": code, "id": r["id"], "raw": n}) + "\n")
                    if i % 5000 == 0:
                        f.flush()
                        print(f"{model}: {i}/{len(todo)}", file=sys.stderr)


if __name__ == "__main__":
    main()
