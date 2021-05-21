import os
import pdfplumber
import matplotlib.pyplot as plt

path = './data/Mobius_March.pdf'
filename = os.path.basename(path)

pdf = pdfplumber.open(path)
page = pdf.pages[0]

img = page.to_image(resolution=100)
img.draw_rects(page.extract_words())

plt.figure()
plt.imshow(img.original)
plt.show()