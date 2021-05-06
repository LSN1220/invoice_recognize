from PIL import Image
import pytesseract

text = pytesseract.image_to_string(Image.open('./data/00003.png'))
print(text)