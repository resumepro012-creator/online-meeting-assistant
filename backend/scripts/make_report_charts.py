"""Generates the report charts as PNG files - no third-party libraries required.

Why this exists: this environment has no matplotlib/Pillow/numpy available, and
python-docx cannot embed SVG. So the charts are rasterised here with a tiny
pure-Python PNG encoder (stdlib ``zlib`` + ``struct``) plus a 5x7 bitmap font.

Reads the JSON produced by ``scripts/evaluate_classifier.py --json`` and writes:

    reports/charts/confusion_matrix.png
    reports/charts/per_class_metrics.png
    reports/charts/label_distribution.png

These charts show MEASURED results only. There is deliberately no training-loss
or training-curve chart, because this project does no fine-tuning (see REPORT.md
section 6) - drawing one would be fabricated data.

Run:
    .venv\\Scripts\\python.exe scripts\\make_report_charts.py
"""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent
DEFAULT_EVAL = ROOT / "reports" / "classifier_eval.json"
OUT_DIR = ROOT / "reports" / "charts"

LABELS = ["QUESTION", "INFORMATION", "DISCUSSION", "DECISION", "ACTION_ITEM"]
SHORT = {
    "QUESTION": "QUESTION",
    "INFORMATION": "INFO",
    "DISCUSSION": "DISCUSS",
    "DECISION": "DECISION",
    "ACTION_ITEM": "ACTION",
}

TEXT = (31, 41, 55)
MUTED = (107, 114, 128)
GRID = (226, 232, 240)
BLUES = [(147, 197, 253), (59, 130, 246), (30, 58, 138)]
INDIGO = (79, 70, 229)
INDIGO_DARK = (49, 46, 129)
HEAT_LO = (224, 231, 255)

# --- 5x7 bitmap font (uppercase only; text is upper-cased before drawing) ---- #
FONT: dict[str, list[str]] = {
    " ": ["00000"] * 7,
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "11110", "10001", "10001", "10001", "11110"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "11110", "10000", "10000", "10000", "11111"],
    "F": ["11111", "10000", "11110", "10000", "10000", "10000", "10000"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01111"],
    "H": ["10001", "10001", "11111", "10001", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11111", "00010", "00100", "00010", "00001", "10001", "01110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    ",": ["00000", "00000", "00000", "00000", "01100", "01100", "11000"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    "/": ["00001", "00010", "00010", "00100", "01000", "01000", "10000"],
    ":": ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
    "%": ["11001", "11010", "00010", "00100", "01000", "01011", "10011"],
    "(": ["00010", "00100", "01000", "01000", "01000", "00100", "00010"],
    ")": ["01000", "00100", "00010", "00010", "00010", "00100", "01000"],
    "|": ["00100", "00100", "00100", "00100", "00100", "00100", "00100"],
    "?": ["01110", "10001", "00001", "00110", "00100", "00000", "00100"],
}
GLYPH_W, GLYPH_H, GLYPH_GAP = 5, 7, 1


class Canvas:
    def __init__(self, width: int, height: int, bg: tuple[int, int, int] = (255, 255, 255)):
        self.w = width
        self.h = height
        self.rows = [bytearray(bytes(bg) * width) for _ in range(height)]

    def rect(self, x: float, y: float, w: float, h: float, color: tuple[int, int, int]) -> None:
        x0, y0 = max(0, int(round(x))), max(0, int(round(y)))
        x1, y1 = min(self.w, int(round(x + w))), min(self.h, int(round(y + h)))
        if x1 <= x0 or y1 <= y0:
            return
        stamp = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            self.rows[yy][x0 * 3 : x1 * 3] = stamp

    def text_width(self, s: str, scale: int = 1) -> int:
        return max(0, len(s) * (GLYPH_W + GLYPH_GAP) * scale - GLYPH_GAP * scale)

    def text(self, x: float, y: float, s: str, scale: int = 1,
             color: tuple[int, int, int] = TEXT) -> None:
        cx = x
        for ch in s.upper():
            glyph = FONT.get(ch, FONT["?"])
            for r, line in enumerate(glyph):
                for c, bit in enumerate(line):
                    if bit == "1":
                        self.rect(cx + c * scale, y + r * scale, scale, scale, color)
            cx += (GLYPH_W + GLYPH_GAP) * scale

    def text_center(self, cx: float, y: float, s: str, scale: int = 1,
                    color: tuple[int, int, int] = TEXT) -> None:
        self.text(cx - self.text_width(s, scale) / 2, y, s, scale, color)

    def text_right(self, x: float, y: float, s: str, scale: int = 1,
                   color: tuple[int, int, int] = TEXT) -> None:
        self.text(x - self.text_width(s, scale), y, s, scale, color)

    def save(self, path: Path) -> None:
        raw = b"".join(b"\x00" + bytes(row) for row in self.rows)
        compressed = zlib.compress(raw, 9)

        def chunk(tag: bytes, data: bytes) -> bytes:
            body = tag + data
            return (struct.pack(">I", len(data)) + body
                    + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

        header = struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0)
        png = (b"\x89PNG\r\n\x1a\n"
               + chunk(b"IHDR", header)
               + chunk(b"IDAT", compressed)
               + chunk(b"IEND", b""))
        path.write_bytes(png)


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (round(a[0] + (b[0] - a[0]) * t),
            round(a[1] + (b[1] - a[1]) * t),
            round(a[2] + (b[2] - a[2]) * t))


# --------------------------------------------------------------------------- #
def confusion_png(result: dict) -> Canvas:
    confusion = result["confusion"]
    cell, left, top = 80, 150, 120
    width = left + cell * len(LABELS) + 60
    height = top + cell * len(LABELS) + 60
    canvas = Canvas(width, height)
    max_v = max((confusion[a].get(b, 0) for a in LABELS for b in LABELS), default=1) or 1

    canvas.text_center(width / 2, 24, "CONFUSION MATRIX - ACTIVE CLASSIFIER", 2, INDIGO_DARK)
    canvas.text_center(width / 2, 52, f"METHOD: {result['method']}", 1, MUTED)
    canvas.text_center(width / 2, 66, f"{result['total']} LABELLED DEV SEGMENTS", 1, MUTED)
    canvas.text_center(left + cell * len(LABELS) / 2, top - 40, "PREDICTED", 1, MUTED)

    for i, actual in enumerate(LABELS):
        cy = top + i * cell
        canvas.text_right(left - 12, cy + cell / 2 - 3, SHORT[actual], 1, TEXT)
        for j, predicted in enumerate(LABELS):
            value = confusion[actual].get(predicted, 0)
            fill = (249, 250, 251) if value == 0 else _mix(HEAT_LO, INDIGO_DARK, value / max_v)
            canvas.rect(left + j * cell, cy, cell - 2, cell - 2, fill)
            canvas.text_center(left + j * cell + cell / 2 - 1, cy + cell / 2 - 8,
                               str(value), 2, (255, 255, 255) if value / max_v > 0.5 else TEXT)

    for j, predicted in enumerate(LABELS):
        canvas.text_center(left + j * cell + cell / 2 - 1, top - 22, SHORT[predicted], 1, MUTED)

    canvas.text(20, top - 40, "ACTUAL", 1, MUTED)
    return canvas


def metrics_png(result: dict) -> Canvas:
    per_class = result["per_class"]
    width, height = 820, 460
    left, top, bottom = 90, 100, 90
    plot_w, plot_h = width - left - 50, height - top - bottom
    group_w = plot_w / len(LABELS)
    bar_w = group_w / 5.0
    series = [("precision", "PRECISION", BLUES[0]),
              ("recall", "RECALL", BLUES[1]),
              ("f1", "F1", BLUES[2])]

    canvas = Canvas(width, height)
    canvas.text_center(width / 2, 26, "PER-CLASS PRECISION / RECALL / F1", 2, INDIGO_DARK)
    canvas.text_center(width / 2, 54, f"METHOD: {result['method']}", 1, MUTED)
    canvas.text_center(width / 2, 68, f"MACRO F1 = {result['macro_f1']:.4f}", 1, MUTED)

    for tick in range(0, 6):
        v = tick / 5
        y = top + plot_h - v * plot_h
        canvas.rect(left, y, plot_w, 1, GRID)
        canvas.text_right(left - 10, y - 3, f"{v:.1f}", 1, MUTED)

    for gi, label in enumerate(LABELS):
        gx = left + gi * group_w
        canvas.text_center(gx + group_w / 2, top + plot_h + 14, SHORT[label], 1, TEXT)
        for si, (key, _name, color) in enumerate(series):
            value = per_class[label][key]
            bar_h = value * plot_h
            bx = gx + group_w * 0.16 + si * (bar_w + 6)
            by = top + plot_h - bar_h
            canvas.rect(bx, by, bar_w, bar_h, color)
            canvas.text_center(bx + bar_w / 2, by - 12, f"{value:.2f}", 1, TEXT)

    lx = left
    for _key, name, color in series:
        canvas.rect(lx, top + plot_h + 42, 12, 12, color)
        canvas.text(lx + 18, top + plot_h + 45, name, 1, TEXT)
        lx += 150
    return canvas


def distribution_png(result: dict) -> Canvas:
    per_class = result["per_class"]
    counts = [(label, per_class[label]["support"]) for label in LABELS]
    max_v = max(c for _l, c in counts) or 1
    width, height = 760, 420
    left, top, bottom = 90, 105, 90
    plot_w, plot_h = width - left - 50, height - top - bottom
    slot = plot_w / len(counts)
    bar_w = slot * 0.5

    canvas = Canvas(width, height)
    canvas.text_center(width / 2, 26, "DEVELOPMENT-SET LABEL DISTRIBUTION", 2, INDIGO_DARK)
    canvas.text_center(width / 2, 54, "TESTS/DATA/LABELLED_SEGMENTS.JSONL", 1, MUTED)
    canvas.text_center(width / 2, 68, f"{result['total']} SEGMENTS TOTAL", 1, MUTED)

    for gi, (label, count) in enumerate(counts):
        gx = left + gi * slot
        bar_h = count / max_v * plot_h
        bx = gx + (slot - bar_w) / 2
        by = top + plot_h - bar_h
        canvas.rect(bx, by, bar_w, bar_h, INDIGO)
        canvas.text_center(bx + bar_w / 2, by - 16, str(count), 2, INDIGO_DARK)
        canvas.text_center(gx + slot / 2, top + plot_h + 14, SHORT[label], 1, TEXT)

    canvas.rect(left, top + plot_h, plot_w, 1, MUTED)
    return canvas


def main() -> int:
    if not DEFAULT_EVAL.exists():
        print(f"FAIL: {DEFAULT_EVAL} not found. Run evaluate_classifier.py --json first.")
        return 1

    result = json.loads(DEFAULT_EVAL.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    outputs = {
        "confusion_matrix.png": confusion_png(result),
        "per_class_metrics.png": metrics_png(result),
        "label_distribution.png": distribution_png(result),
    }
    for name, canvas in outputs.items():
        canvas.save(OUT_DIR / name)
        print(f"wrote {OUT_DIR / name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
