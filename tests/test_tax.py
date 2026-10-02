"""Run: uv run python tests/test_tax.py"""
from tokentax.cli import spec, tax

# a language missing a sentence is compared only on the sentences both sides have
langs = {
    "eng_Latn": [{"id": 0, "text": "ab"}, {"id": 1, "text": "cd"}],
    "zul_Latn": [{"id": 1, "text": "cdcd"}],
}
taxes, tokens = tax(len, langs)  # 1 token per character
assert taxes == {"eng_Latn": 1.0, "zul_Latn": 2.0}, taxes
assert tokens == {"eng_Latn": 4, "zul_Latn": 4}, tokens

assert spec("tiktoken:o200k_base") == ("tiktoken", "o200k_base")
assert spec("Qwen/Qwen3-0.6B") == ("hf", "Qwen/Qwen3-0.6B")
print("ok")
