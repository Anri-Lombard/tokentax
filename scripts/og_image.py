"""Render the 1200x630 social card from docs/tax.json -> docs/og.svg (+ og.png if rsvg-convert exists)."""
import json
import math
import shutil
import statistics
import subprocess
from html import escape

TOK = "GPT-5 / GPT-4o"
d = json.load(open("docs/tax.json", encoding="utf-8"))
L = sorted(d["languages"], key=lambda l: -l["tax"][TOK])
median = statistics.median(l["tax"][TOK] for l in L)
zul = next(l for l in L if l["code"] == "zul_Latn")

W, H = 1200, 630
x0, x1, base, top = 80, 1120, 560, 330  # skyline box
step = (x1 - x0) / len(L)
peak = L[0]["tax"][TOK]

y = lambda v: base - (base - top) * math.log2(max(v, 1)) / math.log2(peak)
font = 'font-family="system-ui, -apple-system, Helvetica, sans-serif"'
o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
     f'<rect width="{W}" height="{H}" fill="#0d0d0d"/>',
     f'<text x="80" y="110" {font} font-size="34" fill="#c3c2b7">Tokenizer Tax</text>',
     f'<text x="80" y="185" {font} font-size="54" font-weight="700" fill="#ffffff">Same sentence, more tokens.</text>',
     f'<text x="80" y="250" {font} font-size="30" fill="#c3c2b7">Median language: {median:.2f}× English on GPT-5. '
     f'isiZulu {zul["tax"][TOK]:.2f}×. Rare scripts: up to {peak:.0f}×.</text>']
for i, l in enumerate(L):
    v = l["tax"][TOK]
    on = l["code"] == "zul_Latn"
    o.append(f'<rect x="{x0 + i * step:.1f}" y="{y(v):.1f}" width="{max(1, step - 1):.1f}" height="{base - y(v):.1f}" '
             f'rx="1" fill="{"#3987e5" if on else "#4a4946"}"/>')
o.append(f'<line x1="{x0}" x2="{x1}" y1="{base}" y2="{base}" stroke="#383835"/>')
zi = next(i for i, l in enumerate(L) if l["code"] == "zul_Latn")
o.append(f'<text x="{x0 + zi * step:.1f}" y="{y(zul["tax"][TOK]) - 10:.1f}" text-anchor="middle" {font} font-size="20" '
         f'fill="#ffffff">isiZulu</text>')
o.append(f'<text x="{x0 + 4}" y="{y(peak) - 10:.1f}" {font} font-size="20" fill="#ffffff">{escape(L[0]["name"])} {peak:.1f}×</text>')
o.append(f'<text x="80" y="600" {font} font-size="22" fill="#898781">{len(L)} languages · {len(d["tokenizers"])} tokenizers · '
         f'paste your own text to compare</text>')
o.append("</svg>")
open("docs/og.svg", "w", encoding="utf-8").write("\n".join(o))
if shutil.which("rsvg-convert"):
    subprocess.run(["rsvg-convert", "docs/og.svg", "-o", "docs/og.png"], check=True)
print("wrote docs/og.svg" + (" and docs/og.png" if shutil.which("rsvg-convert") else ""))
