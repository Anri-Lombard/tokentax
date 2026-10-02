"""How many tokens does the same text cost across LLM tokenizers?

    tokentax "Sawubona, unjani?"
    tokentax zulu.txt --vs english.txt     # same text in both languages -> the tax
"""
import argparse
import os
import sys

# label -> (backend, id). Open tokenizers only; models whose tokenizer is gated or API-only come later.
TOKENIZERS = {
    "GPT-5 / GPT-4o / o3": ("tiktoken", "o200k_base"),
    "GPT-4": ("tiktoken", "cl100k_base"),
    "Qwen3": ("hf", "Qwen/Qwen3-0.6B"),
    "DeepSeek-V3.1": ("hf", "deepseek-ai/DeepSeek-V3.1"),
    "GLM-4.6": ("hf", "zai-org/GLM-4.6"),
}


def counter(backend, name):
    """A function text -> token count."""
    if backend == "tiktoken":
        import tiktoken

        enc = tiktoken.get_encoding(name)
        return lambda text: len(enc.encode(text, disallowed_special=()))
    from tokenizers import Tokenizer

    tok = Tokenizer.from_pretrained(name)
    return lambda text: len(tok.encode(text, add_special_tokens=False).ids)


def read(arg):
    if arg == "-":
        return sys.stdin.read()
    if os.path.isfile(arg):
        with open(arg, encoding="utf-8") as f:
            return f.read()
    return arg


def main(argv=None):
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
