# Document Text Extraction App

This is a Streamlit-based web application for extracting text from various document formats including images, PDFs, and Word files. The app uses OCR technologies like EasyOCR and PyTesseract to perform text extraction.

## Features

- Upload single or multiple documents (images, PDFs, DOCX).
- Extract text from images using EasyOCR and PyTesseract.
- Extract text from PDFs using PyMuPDF and pdfplumber.
- Extract text from Word documents using docx2txt.
- View extracted text within the app.
- Download extracted text as a `.txt` file.


## Supported Formats
- Images: JPG, PNG, BMP, etc.
- PDFs
- Word documents: DOCX

## Dependencies
- Streamlit
- PyMuPDF
- pdfplumber
- pandas
- Pillow
- docx2txt
- EasyOCR
- pytesseract
- numpy
