# HR Policy Q&A Assistant

AI-powered system to answer employee questions from HR policy documents.

## Quick Start

### 1. Start the API Server
```powershell
.\RUN_API.ps1
```

### 2. Start the Web Interface
```powershell
.\RUN_UI.ps1
```

### 3. Open Browser
http://localhost:8501

---

## Offline Operation

**YES - Runs 100% offline after setup!**

Initial setup needs internet once to download:
- Python packages
- Ollama model (llama3.2:3b)

After that, disconnect internet and it works perfectly.

---

## Features

- Semantic search through 1,904 policy chunks
- Source citations with page numbers
- Dark theme UI
- Free (no API costs)

---

## Data Source

- IIMA HR Policy Manual 2024 (218 pages)
- File: data/raw/HR Policy Manual 2024.pdf
- All answers from real PDF content

---

## Technology

- Backend: FastAPI
- Frontend: Streamlit
- Database: ChromaDB (local)
- LLM: Ollama (local)
- Embeddings: sentence-transformers (local)
