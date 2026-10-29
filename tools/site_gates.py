#!/usr/bin/env python3
"""Site gates: internal-link resolution, HTML sanity, forbidden strings.

Usage: python3 site_gates.py <site_dir>
Exit non-zero on any failure. Dependency-free (stdlib only).
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

FORBIDDEN_SUBSTRINGS = [
    "simsun", "subagent", "agent", "orchestrator",
]

# Claim-word gate (mission list + paper-check vocabulary forms).
FORBIDDEN_WORDS = [
    "first", "novel", "novelty", "novelties", "state-of-the-art",
    "state of the art", "sota", "validated", "validating",
    "production-ready", "production-proven", "cutting-edge",
    "seamless", "seamlessly", "battle-tested", "industrial-grade",
]

# Owner-approved verbatim copy (signed off 2026-10-29; recorded in
# docs/plans/site_vision_roadmap.md): the vision statement on
# site/roadmap.html uses "first" in "Yes — as its natural first home."
# Exact snippets only, masked length-preservingly — every other
# occurrence of a claim word, anywhere, still fails the gate.
APPROVED_CLAIM_SNIPPETS = {
    "roadmap.html": [
        "Yes — as its natural first home.",
    ],
}


class BalanceChecker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append((tag, self.getpos()))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append(f"unexpected </{tag}> at {self.getpos()}")
            return
        open_tag, pos = self.stack.pop()
        if open_tag != tag:
            self.errors.append(
                f"mismatch: <{open_tag}> opened at {pos}, closed by </{tag}> at {self.getpos()}"
            )


def main(site: Path) -> int:
    failures = []
    pages = sorted(site.glob("*.html"))
    if not pages:
        failures.append("no HTML pages found")

    for page in pages:
        text = page.read_text(encoding="utf-8")

        # --- forbidden substrings (case-insensitive) ---
        low = text.lower()
        for bad in FORBIDDEN_SUBSTRINGS:
            if bad in low:
                idx = low.index(bad)
                failures.append(f"{page.name}: forbidden substring '{bad}' near: ...{text[max(0, idx-40):idx+40]!r}...")

        # --- claim words as words (case-insensitive) ---
        # Approved snippets are masked with equal-length non-word filler
        # so match positions still index into the original text.
        scan = low
        for snip in APPROVED_CLAIM_SNIPPETS.get(page.name, []):
            snip_low = snip.lower()
            scan = scan.replace(snip_low, "\x00" * len(snip_low))
        for word in FORBIDDEN_WORDS:
            pattern = r"\b" + re.escape(word) + r"\b"
            m = re.search(pattern, scan)
            if m:
                idx = m.start()
                failures.append(f"{page.name}: claim word '{word}' near: ...{text[max(0, idx-40):idx+40]!r}...")

        # --- HTML balance ---
        checker = BalanceChecker()
        checker.feed(text)
        checker.close()
        for err in checker.errors:
            failures.append(f"{page.name}: {err}")
        for tag, pos in checker.stack:
            failures.append(f"{page.name}: unclosed <{tag}> opened at {pos}")

        # --- internal link resolution ---
        for attr in ("href", "src"):
            for target in re.findall(rf'{attr}="([^"]+)"', text):
                parsed = urlparse(target)
                if parsed.scheme or parsed.netloc:
                    continue  # external link, allowed
                if parsed.fragment and not parsed.path:
                    continue  # same-page anchor
                local = parsed.path
                if local.startswith("/"):
                    failures.append(f"{page.name}: non-relative link {attr}='{target}'")
                    continue
                resolved = (page.parent / local)
                if not resolved.exists():
                    failures.append(f"{page.name}: broken link {attr}='{target}'")
                # fragment target must exist in the linked page
                frag = parsed.fragment
                if frag and resolved.exists() and resolved.suffix == ".html":
                    dest = resolved.read_text(encoding="utf-8")
                    if f'id="{frag}"' not in dest:
                        failures.append(f"{page.name}: missing fragment '{frag}' in '{local}'")

    # CSS gate too
    for css in site.glob("*.css"):
        low = css.read_text(encoding="utf-8").lower()
        for bad in FORBIDDEN_SUBSTRINGS:
            if bad in low:
                failures.append(f"{css.name}: forbidden substring '{bad}'")
        for word in FORBIDDEN_WORDS:
            if re.search(r"\b" + re.escape(word) + r"\b", low):
                failures.append(f"{css.name}: claim word '{word}'")

    if failures:
        print("SITE GATES: FAIL")
        for f in failures:
            print(" -", f)
        return 1
    print(f"SITE GATES: PASS ({len(pages)} pages: {', '.join(p.name for p in pages)})")
    print(" - all internal links resolve (relative, fragments included)")
    print(" - all tags balanced (html.parser)")
    print(f" - forbidden substrings absent: {', '.join(FORBIDDEN_SUBSTRINGS)}")
    print(f" - claim words absent: {', '.join(FORBIDDEN_WORDS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
