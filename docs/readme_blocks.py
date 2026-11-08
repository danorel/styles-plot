"""The README's generated parts, and its checks. Run from the repository root.

    python docs/readme_blocks.py           rewrite the blocks between <!-- NAME:start --> and <!-- NAME:end -->
    python docs/readme_blocks.py --check   rebuild the README images into a temporary folder and compare their sidecars
                                           with the committed ones (every field but `png` and `styles_plot`: pixels may
                                           move with a matplotlib release, meaning may not); every relative link and
                                           image path in the README exists

Blocks: `refused` is the StyleError of examples/strict/refused.py; `first-figure` is the starter builder `styles-plot init`
writes, so the code in the README is the code the tests run.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
from importlib.resources import files
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
IMAGES = ROOT / "examples" / "figures"
README_FIGURES = ("dot_table", "key", "sweep", "methods")
IGNORED = ("png", "styles_plot")  # sidecar fields that may change without the figure's meaning changing


def _module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def blocks() -> dict[str, str]:
    refused = _module(ROOT / "examples" / "strict" / "refused.py").error_text()
    first = (files("styles_plot") / "data" / "init" / "first_figure.py").read_text(encoding="utf-8")
    return {"refused": f"```\n{refused}\n```", "first-figure": f"```python\n{first.rstrip()}\n```"}


def fill(text: str, parts: dict[str, str]) -> str:
    for name, body in parts.items():
        rx = re.compile(rf"(<!-- {name}:start -->\n).*?(<!-- {name}:end -->)", re.S)
        if not rx.search(text):
            raise SystemExit(f"README.md: no <!-- {name}:start --> … <!-- {name}:end --> block")
        text = rx.sub(lambda m, body=body: f"{m.group(1)}{body}\n{m.group(2)}", text)
    return text


def build_images(out: Path) -> int:
    gallery = _module(ROOT / "examples" / "build_gallery.py")
    return gallery.main(["--out", str(out), "--targets", "readme", "--only", *README_FIGURES, "--no-sheets",
                         "--sidecar-dir", "_meta"])  # fmt: skip


def _meaning(path: Path) -> dict:
    return {k: v for k, v in json.loads(path.read_text()).items() if k not in IGNORED}


def check_images() -> list[str]:
    errors = []
    with tempfile.TemporaryDirectory() as tmp:
        if build_images(Path(tmp)) != 0:
            return ["the README images do not build strict"]
        for name in README_FIGURES:
            rel = Path("readme") / "_meta" / f"{name}.styles.json"
            committed, fresh = IMAGES / rel, Path(tmp) / rel
            if not committed.exists():
                errors.append(f"examples/figures/{rel} is missing: run make readme-images")
            elif _meaning(committed) != _meaning(fresh):
                errors.append(f"examples/figures/{rel} differs from a fresh build: run make readme-images")
    return errors


def check_links(text: str) -> list[str]:
    targets = re.findall(r"\]\(([^)\s]+)\)", text) + re.findall(r'<img [^>]*src="([^"]+)"', text)
    errors = []
    for t in targets:
        if re.match(r"[a-z]+:", t) or t.startswith("#"):
            continue
        if not (README.parent / t.split("#")[0]).exists():
            errors.append(f"README.md links to {t}, which does not exist")
    return errors


def main(argv: list[str]) -> int:
    if "--check" in argv:
        errors = check_images() + check_links(README.read_text())
        for e in errors:
            print(e, file=sys.stderr)
        print(f"readme: {len(errors)} problem(s)")
        return 1 if errors else 0
    README.write_text(fill(README.read_text(), blocks()))
    print("wrote README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
