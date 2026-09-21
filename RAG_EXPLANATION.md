# RAG Explanation: HR Policy Q&A Assistant

## 1. Why `all-MiniLM-L6-v2`?

`all-MiniLM-L6-v2` is an embedding model from Sentence Transformers. It converts text into numerical vectors that represent the meaning of the text.

For example:

```text
How many leave days do I get?
        -> [0.12, -0.04, 0.88, ...]
```

The model is used because it is:

- Fast
- Small enough to run locally
- Free
- Suitable for semantic search
- Usable offline after installation
- Able to produce 384-dimensional vectors

It is not responsible for generating the final answer. Its job is to help find policy passages with a meaning similar to the user's question.

## 2. How does the AI answer only from HR policy?

The system first retrieves relevant HR policy excerpts. These excerpts are then placed inside the prompt sent to the language model.

The prompt in `app/answer.py` contains rules such as:

```text
Answer ONLY from the CONTEXT section below.
Never use outside knowledge.
Do not guess.
```

The prompt is conceptually structured like this:

```text
SYSTEM:
Answer only from the provided context.

CONTEXT:
[Excerpt 1]
Document: HR Policy Manual
Page: 79
Policy text: ...

[Excerpt 2]
Document: HR Policy Manual
Page: 80
Policy text: ...

QUESTION:
Can I carry forward unused leave?
```

The model is instructed to use only the retrieved context. If the context does not contain enough information, it should return:

```text
The available policy documents do not contain enough information to answer this question.
```

The system reduces hallucinations using:

1. Semantic retrieval from the policy database
2. A minimum similarity threshold
3. A strict prompt
4. An unanswerable response when no chunks pass the threshold
5. Temperature `0`, which makes generation more deterministic
6. Source metadata and citations

This is a prompt-based restriction, not an absolute security boundary. A language model can still make mistakes, so answer quality should be tested and monitored.

If the HR PDF contains unrelated information, that information normally will not be sent to the model unless it is retrieved as one of the relevant excerpts.

## 3. How is a chunk created?

The ingestion process is implemented in `app/ingest.py`.

First, PyMuPDF extracts text from each PDF page:

```python
raw_text = page.get_text()
```

The project uses these chunking settings:

```python
TARGET_CHUNK_SIZE = 600
OVERLAP = 100
```

The chunker uses a sliding window. In simplified form:

```python
start = 0

while start < len(text):
    end = start + 600
    chunk = text[start:end]
    start = start + 500
```

This produces chunks approximately like this:

```text
Chunk 1: characters 0-599
Chunk 2: characters 500-1099
Chunk 3: characters 1000-1599
```

Each chunk overlaps the previous chunk by 100 characters. The overlap helps preserve context when a sentence or policy rule crosses a chunk boundary.

Chunks shorter than 50 non-space characters are ignored.

Each chunk receives metadata, for example:

```json
{
  "page": 79,
  "section": "General",
  "doc_id": "HR Policy Manual 2024",
  "effective_date": "2023-12-29",
  "version": "1.0",
  "status": "approved"
}
```

The chunk text and metadata are stored in ChromaDB. The processed chunks are also saved in `data/processed/chunks.json`.

## 4. How is the similarity score calculated?

The policy chunks are embedded during ingestion. When a user asks a question, the question is embedded using the same model:

```python
query_embedding = model.encode([question], convert_to_numpy=True)[0].tolist()
```

ChromaDB compares the question vector with the stored chunk vectors using cosine distance.

The project converts the returned distance into a similarity value in `app/retrieve.py`:

```python
similarity = 1.0 - (distance / 2.0)
```

Conceptually:

```text
distance = 0 -> similarity = 1.0
distance = 1 -> similarity = 0.5
distance = 2 -> similarity = 0.0
```

A higher score means that the question and chunk are more semantically related.

The default minimum score is `0.72`:

```python
min_score = float(os.getenv("MIN_RETRIEVAL_SCORE", "0.72"))
```

Chunks below this value are discarded.

The similarity score is not a probability that the answer is 72% correct. It is only a configured measure of semantic closeness between the question and a chunk.

## 5. How are the top five excerpts fetched?

The retrieval process is implemented in `app/retrieve.py`.

The API normally sets the number of results to five:

```python
top_k = int(os.getenv("RETRIEVAL_TOP_K", "5"))
```

The question is sent to ChromaDB like this:

```python
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=top_k,
)
```

ChromaDB returns the five closest chunks according to vector distance. The project then calculates similarity scores and removes results below the threshold.

The complete flow is:

```text
User question
    -> Question embedding
    -> ChromaDB vector search
    -> Five nearest chunks
    -> Convert distance to similarity
    -> Remove chunks below 0.72
    -> Send remaining chunks to the language model
```

For example, ChromaDB might return:

```text
Page 79  similarity 0.84
Page 80  similarity 0.81
Page 78  similarity 0.77
Page 155 similarity 0.74
Page 77  similarity 0.70
```

With a threshold of `0.72`, the last result is removed. The language model receives four excerpts instead of five.

Therefore, "top five" means:

> Retrieve up to five nearest chunks first, then filter them using the similarity threshold.

## 6. Complete RAG flow

```text
HR Policy PDF
    -> Extract page text
    -> Split text into overlapping chunks
    -> Create embeddings
    -> Store chunks and vectors in ChromaDB

User question
    -> Create question embedding
    -> Search ChromaDB
    -> Retrieve top five chunks
    -> Filter by similarity threshold
    -> Build LLM context
    -> Generate answer from context
    -> Return answer with source pages
```

## 7. Main limitation

The current chunker is character-based. It can split a sentence, paragraph, or table in the middle. A future improvement would split primarily at paragraph or section boundaries while still enforcing a maximum chunk size.
