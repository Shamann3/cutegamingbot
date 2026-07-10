# -*- coding: utf-8 -*-
"""Find implicit string concatenations (missing commas) in a Python file.

Two string literals separated only by whitespace/newlines (no comma, no '+')
are silently concatenated by Python. Inside a big set/list literal like
custom_commands this quietly merges two commands into one broken entry.

Usage:  py -3 -X utf8 scripts\find_str_concat.py [path]  (default: main.py)
"""
import sys
import tokenize

path = sys.argv[1] if len(sys.argv) > 1 else "main.py"

prev = None  # last significant token
hits = []
with tokenize.open(path) as f:
    for tok in tokenize.generate_tokens(f.readline):
        if tok.type in (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT):
            continue
        if tok.type in (tokenize.STRING, getattr(tokenize, "FSTRING_START", -1)):
            if prev is not None and prev.type == tokenize.STRING:
                a = prev.string.strip()
                b = tok.string.strip()
                hits.append((prev.start[0], tok.start[0], a[:40], b[:40]))
        prev = tok

if not hits:
    print("OK: no implicit string concatenations found in", path)
else:
    print(f"FOUND {len(hits)} implicit string concatenation(s) in {path}:")
    for l1, l2, a, b in hits:
        print(f"  line {l1}->{l2}: {a!r}  <MISSING COMMA>  {b!r}")
