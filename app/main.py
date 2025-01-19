from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
import shutil
import os
import sqlite3
import PyPDF2
import re
from collections import Counter

app = FastAPI()

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploaded_files"
DB_FILE = "documents.db"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Initialize SQLite database
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        summary TEXT
    )
''')
conn.commit()
conn.close()

# Helper function to extract text from PDF
def extract_pdf_text(file_path):
    text = ""
    with open(file_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()

# Simple keyword-based summarizer
def summarize_text(text):
    if not text.strip():
        raise HTTPException(status_code=400, detail="Uploaded file is empty or unreadable.")

    sentences = re.split(r'(?<=[.!?]) +', text)
    words = re.findall(r'\w+', text.lower())
    word_freq = Counter(words)

    sentence_scores = {}
    for sentence in sentences:
        for word in re.findall(r'\w+', sentence.lower()):
            if word in word_freq:
                sentence_scores[sentence] = sentence_scores.get(sentence, 0) + word_freq[word]

    summarized_sentences = sorted(sentence_scores, key=sentence_scores.get, reverse=True)[:3]
    summary = ' '.join(summarized_sentences)

    return summary if summary else text

# Enhanced HTML upload page with modern UI and animations
@app.get("/upload", response_class=HTMLResponse)
def upload_page():
    return """
    <html>
        <head>
            <title>Smart Document Summarizer</title>
            <style>
                body {
                    font-family: 'Poppins', sans-serif;
                    background-color: #f2f2f2;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                }
                .upload-container {
                    background-color: #fff;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                    text-align: center;
                }
                button {
                    padding: 10px 20px;
                    background-color: #007BFF;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                }
                button:hover {
                    background-color: #0056b3;
                }
            </style>
        </head>
        <body>
            <div class="upload-container">
                <h2>Upload and Summarize Document</h2>
                <form action="/uploadfile/" method="post" enctype="multipart/form-data">
                    <input type="file" name="file" accept=".pdf,.txt" required>
                    <br><br>
                    <button type="submit">Upload</button>
                </form>
            </div>
        </body>
    </html>
    """

@app.post("/uploadfile/")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        text = extract_pdf_text(file_path) if file.filename.endswith(".pdf") else open(file_path, "r", encoding="utf-8").read()
        summary = summarize_text(text)

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO documents (filename, summary) VALUES (?, ?)", (file.filename, summary))
        conn.commit()
        conn.close()

        return JSONResponse({"filename": file.filename, "summary": summary})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")
