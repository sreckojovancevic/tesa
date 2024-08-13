import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import camelot
from docx import Document
from concurrent.futures import ProcessPoolExecutor
import os

def ocr_image(image, language):
    custom_config = r'--oem 3 --psm 3'
    return pytesseract.image_to_string(image, lang=language, config=custom_config)

def preprocess_image(image):
    base_width = 1024
    w_percent = (base_width / float(image.size[0]))
    h_size = int((float(image.size[1]) * float(w_percent)))
    return image.resize((base_width, h_size), Image.LANCZOS).convert('L')

def sanitize_text(text):
    return ''.join(c for c in text if ord(c) > 31 or c in '\t\n\r')

def save_to_docx(text_list, file_path):
    doc = Document()
    for line in text_list:
        doc.add_paragraph(line)
    docx_path = file_path.rsplit('.', 1)[0] + '.docx'
    doc.save(docx_path)
    return docx_path

def process_image(img, language):
    return ocr_image(img, language)

def process_ocr(file_path, language, num_processors=3):
    try:
        print(f"Starting OCR processing for {file_path} with language {language}")
        text_list = []
        if file_path.lower().endswith('.pdf'):
            images = convert_from_path(file_path)
            if images:
                with ProcessPoolExecutor(max_workers=num_processors) as executor:
                    text_results = list(executor.map(process_image, images, [language]*len(images)))
                text = "\n".join(text_results)
                text_list.append(f"OCR Text:\n{text}")
            else:
                tables = camelot.read_pdf(file_path, pages='all')
                table_texts = [table.df.to_string(index=False) for table in tables]
                table_text = "\n\n".join(table_texts)
                text_list.append(f"Tables:\n{table_text}")
        else:
            image = Image.open(file_path)
            image = preprocess_image(image)
            text = ocr_image(image, language)
            text_list.append(text)

        sanitized_text_list = [sanitize_text(text) for text in text_list]
        docx_path = save_to_docx(sanitized_text_list, file_path)
        print(f"OCR processing completed for {file_path}")
        return sanitized_text_list, docx_path
    except Exception as e:
        print(f"Error processing OCR: {e}")
        raise e
