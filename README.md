# Internal Policy Q&A Assistant

An offline-first retrieval-augmented generation (RAG) application for answering questions from an approved internal policy manual. The assistant retrieves relevant policy passages, asks a local language model to answer from those passages, and returns page-level sources so the response can be checked against the document.

## The Build Journey

This project was developed as a practical path from an unstructured policy PDF to a usable, testable assistant.

### 1. Start with the trust problem

Policy questions are not a good fit for open-ended chatbot answers. The first design decision was to make the document the source of truth and to return an explicit `unanswerable` result when the retrieved evidence is not strong enough.

### 2. Turn the manual into searchable knowledge

The ingestion pipeline extracts text page by page with PyMuPDF, splits it into overlapping chunks, and preserves metadata such as page number, document name, version, effective date, and approval status. Sentence Transformers creates local embeddings, which are stored in ChromaDB for semantic search.

The current processed collection contains 1,904 policy chunks from the IIMA HR Policy Manual 2024.

### 3. Retrieve evidence before generating language

For every question, the API embeds the query and retrieves the closest passages. Results below the configured similarity threshold are removed before the language model sees them. This keeps the generation step focused on relevant evidence instead of the model's general knowledge.

### 4. Generate a grounded answer

The answer prompt instructs the local Ollama model to use only the supplied context, avoid guessing, and acknowledge when the policy does not provide enough information. Responses include source pages, and the API also flags potential conflicts so the most recent approved policy can be prioritized.

### 5. Verify the workflow with evaluation questions

The evaluation script sends the questions in `evaluation/questions.json` to the running API. It checks expected phrases in the answer and expected source pages, then writes a reviewable report to `evaluation/eval_results.json`. This makes retrieval and answer quality visible instead of relying only on a good-looking demo.

## How Kiro.dev Supported the Project

Kiro.dev was used as a development companion throughout the build. Its value was in turning the idea into a sequence of concrete engineering decisions and keeping those decisions visible:

- **Requirements into an implementation path:** clarified that this was a policy-grounded assistant, not a general chatbot, and separated ingestion, retrieval, generation, interface, and evaluation work.
- **Architecture with clear boundaries:** helped shape the FastAPI, ChromaDB, embedding, Ollama, and Streamlit responsibilities so each part could be tested and changed independently.
- **Better reliability decisions:** surfaced the need for similarity thresholds, refusal behavior, source citations, conflict warnings, deterministic generation, and local operation.
- **Documentation as part of the product:** helped turn the RAG design into explainable documentation, including why embeddings are used, how chunking works, and what a similarity score does and does not mean.
- **A repeatable delivery workflow:** supported setup scripts, evaluation fixtures, and a README that explains how another developer can run, inspect, and extend the project.

Kiro.dev did not replace engineering judgment or policy review. It helped make the reasoning explicit; the application still needs representative evaluation questions and human review before being used for real employee decisions.

## Quick Start

### 1. Install dependencies

Run the setup script in PowerShell:

```powershell
.\SETUP_FRESH.ps1
```

The first setup downloads Python packages and the local models. Make sure Ollama is installed and that the configured model is available locally.

### 2. Start the API

In one PowerShell terminal:

```powershell
.\RUN_API.ps1
```

The API runs at `http://localhost:8000`.

### 3. Start the web interface

In a second PowerShell terminal:

```powershell
.\RUN_UI.ps1
```

Open `http://localhost:8501` in a browser.

### 4. Check the API

```powershell
Invoke-RestMethod http://localhost:8000/health
```

To run the evaluation suite while the API is running:

```powershell
.\venv\Scripts\python.exe evaluation\run_eval.py
```

## Architecture

```text
Policy PDF
	-> PyMuPDF page extraction
	-> Overlapping chunks with metadata
	-> Sentence Transformers embeddings
	-> ChromaDB collection

User question
	-> Query embedding
	-> Similarity search and threshold filtering
	-> Grounded Ollama prompt
	-> Answer with page citations
```

## Offline Operation

After the initial installation and model download, the application can run without external API calls or usage fees. The embeddings, vector database, language model, API, and interface all run locally.

## Project Layout

```text
app/                 FastAPI application and RAG pipeline
data/raw/            Source policy documents
data/processed/      Processed chunks and metadata
db/                  Local ChromaDB data
evaluation/          Questions, runner, and evaluation results
ui.py                Streamlit interface
RAG_EXPLANATION.md   Detailed explanation of retrieval and grounding
```

## Technology

- **Backend:** FastAPI
- **Frontend:** Streamlit
- **Vector database:** ChromaDB
- **Embeddings:** Sentence Transformers (`all-MiniLM-L6-v2`)
- **Language model:** Ollama (`llama3.2:3b`)
- **Document extraction:** PyMuPDF
