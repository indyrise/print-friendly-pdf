"""Create a synthetic test PDF replicating the white-text-on-dark failure mode:
Page 1: dark navy background, white text, colored chart bars (pink/lavender like the screenshot)
Page 2: light background, dark text (HBR-style) - should be untouched
"""
import fitz

doc = fitz.open()

# Page 1 - dark design page
p1 = doc.new_page(width=612, height=792)
p1.draw_rect(fitz.Rect(0, 0, 612, 792), color=None, fill=(0.06, 0.06, 0.14))  # near-black navy
p1.insert_text((50, 80), "AI now has 308 unicorns", fontsize=28, color=(1, 1, 1))
p1.insert_text((50, 120), "the most of any technology sector", fontsize=22, color=(0.9, 0.9, 0.95))
p1.insert_text((50, 170), "White body text that must remain readable after conversion.", fontsize=12, color=(1, 1, 1))
# colored chart bars - saturated mid-lightness colors
bars = [((50, 300, 110, 500), (0.96, 0.26, 0.21)),   # red
        ((130, 350, 190, 500), (0.91, 0.12, 0.39)),  # pink
        ((210, 250, 270, 500), (0.61, 0.15, 0.69)),  # purple
        ((290, 400, 350, 500), (0.30, 0.69, 0.31)),  # green
        ((370, 320, 430, 500), (1.00, 0.60, 0.00))]  # orange
for rect, col in bars:
    p1.draw_rect(fitz.Rect(*rect), color=None, fill=col)
p1.insert_text((50, 540), "13%   17%   15%   24%   45%", fontsize=11, color=(1, 1, 1))

# Page 2 - light text page
p2 = doc.new_page(width=612, height=792)
p2.draw_rect(fitz.Rect(0, 0, 612, 792), color=None, fill=(1, 1, 1))
p2.insert_text((70, 100), "How People Are Really Using AI in 2026", fontsize=20, color=(0.1, 0.1, 0.1))
for i in range(12):
    p2.insert_text((70, 160 + i*22), "Standard dark body text on a light page. Must pass through unchanged.", fontsize=11, color=(0.15, 0.15, 0.15))

doc.save("/home/claude/print-friendly-pdf/test_input.pdf")
print(f"Created test PDF: {len(doc)} pages")
