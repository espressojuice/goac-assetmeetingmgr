"""Quick OCR test on one page of the Ashdown PDF."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pypdfium2 as pdfium
from PIL import Image
import io

PDF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "samples", "ashdown_2026-02-11.pdf"
)

# Render page 11 (Service Loaners - known content) to image
pdf = pdfium.PdfDocument(PDF_PATH)
page = pdf[10]  # 0-indexed, page 11
bitmap = page.render(scale=2)  # 2x scale for better OCR
img = bitmap.to_pil()
print(f"Page 11 rendered: {img.size}")

# Save for inspection
img.save("/tmp/ashdown_page11.png")
print("Saved to /tmp/ashdown_page11.png")

# Run easyocr
import easyocr
reader = easyocr.Reader(['en'], gpu=False)
result = reader.readtext(
    "/tmp/ashdown_page11.png",
    detail=0,
    paragraph=False,
)
print(f"\nOCR extracted {len(result)} text segments:")
for line in result:
    print(f"  {line}")

pdf.close()
