"""Contact sheets: every PNG scaled to a reading width and stacked under its file name, in colour and in grayscale (a
view for the reviewer: every figure should still read through its words and marks)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

LABEL_H = 40
SHEET_NAMES = ("contact_sheet.png", "contact_sheet_gray.png")


def figures_in(directory: Path) -> list[Path]:
    """Every figure PNG under a folder, in subfolders too, but not in folders starting with "_" (_meta, _sheets) and
    not contact sheets."""
    return sorted(p for p in directory.rglob("*.png") if p.name not in SHEET_NAMES
                  and not any(part.startswith("_") for part in p.relative_to(directory).parts[:-1]))  # fmt: skip


def contact_sheets(pngs: list[Path], out_dir: Path, width: int = 720, root: Path | None = None) -> tuple[Path, Path]:
    """Write contact_sheet.png and contact_sheet_gray.png into out_dir; returns their paths."""
    if not pngs:
        raise ValueError("no PNGs to put on a contact sheet")
    tiles = []
    for p in pngs:
        im = Image.open(p).convert("RGB")
        tiles.append((str(p.relative_to(root)) if root else p.name,
                      im.resize((width, max(1, round(im.height * width / im.width))), Image.LANCZOS)))  # fmt: skip
    sheet = Image.new("RGB", (width, sum(im.height + LABEL_H for _n, im in tiles)), "white")
    draw = ImageDraw.Draw(sheet)
    y = 0
    for name, im in tiles:
        draw.text((4, y + 12), name, fill="#6b6b6b")
        sheet.paste(im, (0, y + LABEL_H))
        y += im.height + LABEL_H
    out_dir.mkdir(parents=True, exist_ok=True)
    colour, gray = out_dir / SHEET_NAMES[0], out_dir / SHEET_NAMES[1]
    sheet.save(colour)
    ImageOps.grayscale(sheet).save(gray)
    return colour, gray
