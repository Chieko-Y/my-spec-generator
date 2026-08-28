"""Dev-only helper: synthesize a small owner's-manual-shaped PDF with bookmarks, for
manual browser testing since no real manual is loaded in this environment yet.
NOT part of the app — safe to delete once a real manual PDF is available.
"""
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter

OUT = Path(__file__).resolve().parent.parent / "scratch" / "test_manual.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)
TMP = OUT.with_suffix(".raw.pdf")

pages = [
    ["2026 SUBARU OUTBACK", "Multimedia Owner's Manual", "OM0S123U"],
    ["Navigation"],
    [
        "Map Screen Overview",
        "Touch the map icon to open the map screen.",
        "The screen dims after a certain period of time if no operation is made.",
        "1. Touch the Menu button.",
        "2. Touch Navigation.",
        "3. Touch Map.",
    ],
    [
        "Route Overview",
        "A calculated route is shown on the map in blue.",
        "If you are too far from the nearest road, the vehicle icon may not display correctly.",
    ],
    ["Audio"],
    [
        "Source Selection",
        "Touch the Source button to switch between AM, FM, and Bluetooth Audio.",
    ],
]

c = canvas.Canvas(str(TMP), pagesize=letter)
width, height = letter
for page_lines in pages:
    y = height - 72
    for line in page_lines:
        c.drawString(72, y, line)
        y -= 18
    c.showPage()
c.save()

reader = PdfReader(str(TMP))
writer = PdfWriter()
for page in reader.pages:
    writer.add_page(page)

nav = writer.add_outline_item("Navigation", 1)
writer.add_outline_item("Map Screen Overview", 2, parent=nav)
writer.add_outline_item("Route Overview", 3, parent=nav)
audio = writer.add_outline_item("Audio", 4)
writer.add_outline_item("Source Selection", 5, parent=audio)

with open(OUT, "wb") as f:
    writer.write(f)

TMP.unlink()
print(f"wrote {OUT}")
