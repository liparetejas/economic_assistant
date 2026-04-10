# RAG-Powered Economic Intelligence Assistant
**Hackathon submission — ML & AI Track**

A retrieval-augmented generation (RAG) pipeline over Snowflake Marketplace financial and government datasets. Users ask plain-English questions; the system returns grounded, cited answers through a Streamlit in Snowflake chat interface.

---

## Architecture

```
Snowflake Marketplace
┌─────────────────────────┐   ┌──────────────────────────────┐
│  Banking Analytics      │   │  Demographics Data Bundle    │
│  Bundle (InSights)      │   │  (InSights)                  │
└────────────┬────────────┘   └────────────┬─────────────────┘
             │                             │
             └──────────────┬──────────────┘
                            ▼
              SNOWFLAKE.CORTEX.SPLIT_TEXT_RECURSIVE_CHARACTER
              (512 tokens / 50-token overlap)
                            │
                            ▼
              CREATE CORTEX SEARCH SERVICE
              (Arctic Embed M v1.5 — hybrid semantic + keyword)
                            │
              User Question ──► Cortex Search top-k retrieval
                                          │
                                          ▼
                                 SNOWFLAKE.CORTEX.COMPLETE
                                 (llama3.1-70b, grounded prompt)
                                          │
                                          ▼
                              Streamlit in Snowflake Chat UI
                              + Sidebar Source Citation Panel
```

---

## Files

| File | Purpose | Run in |
|------|---------|--------|
| `step1_ingest_chunk.ipynb`    | Load Marketplace data → chunk into 512-token passages | Snowflake Notebook |
| `step2_embed_index.ipynb`     | Create Cortex Search Service (Arctic Embed + hybrid index) | Snowflake Notebook |
| `step3_rag_chain.ipynb`       | Full RAG chain: retrieve + generate + log | Snowflake Notebook |
| `step4_evaluate.ipynb`        | 20-question eval: retrieval precision + answer faithfulness | Snowflake Notebook |
| `step5_streamlit_app.py`      | Streamlit in Snowflake chat UI with source citation panel | Streamlit in Snowflake |
| `README.md`                   | This file | — |
| `Snowflake Hackathon - AI #1 - Report.pdf` | Full detailed report | — |

---

## Prerequisites

1. Snowflake account with `ACCOUNTADMIN` or equivalent privileges
2. Both free Marketplace datasets installed:
   - [InSights: Banking Analytics Bundle](https://app.snowflake.com/marketplace/listing/GZTYZAPS3FP)
   - [InSights: Demographics Data Bundle](https://app.snowflake.com/marketplace/listing/GZTYZAPS3FT)
3. Run the setup SQL once:

```sql
CREATE DATABASE IF NOT EXISTS RAG_HACKATHON_DB;
CREATE SCHEMA  IF NOT EXISTS RAG_HACKATHON_DB.RAG_SCHEMA;
CREATE WAREHOUSE IF NOT EXISTS RAG_WH
  WITH WAREHOUSE_SIZE = 'MEDIUM' AUTO_SUSPEND = 300 AUTO_RESUME = TRUE;
```

---

## Running Order

```
Step 1 → Step 2 → Step 3 → Step 4 → Step 5
```

1. **Step 1** — Import `step1_ingest_chunk.ipynb` into Snowflake Notebooks. Run all cells.
   - Update `BANKING_DB` and `DEMOGRAPHICS_DB` variables with the exact names from Cell 2 output.
   - Output: `CHUNKED_DOCUMENTS` table (~10k–100k chunks depending on dataset size)

2. **Step 2** — Import `step2_embed_index.ipynb`. Run all cells.
   - Wait for Cortex Search service status = ACTIVE (~10–30 min)
   - Output: `ECONOMIC_SEARCH` Cortex Search Service

3. **Step 3** — Import `step3_rag_chain.ipynb`. Run all cells to validate the full pipeline.
   - Output: `RAG_QUERY_LOG` table for auditing

4. **Step 4** — Import `step4_evaluate.ipynb`. Run all cells (~10–15 min for 20 questions).
   - Output: `EVAL_RESULTS` table with precision + faithfulness scores

5. **Step 5** — Deploy the Streamlit app:
   - Navigate to **Streamlit** in Snowflake console
   - Click **+ Streamlit App**
   - Name it `Economic_Intelligence_Assistant`
   - Select `RAG_WH`, `RAG_HACKATHON_DB`, `RAG_SCHEMA`
   - Paste the contents of `step5_streamlit_app.py` into the editor
   - Click **Run**

---

## Hackathon Constraints Compliance

| Constraint | How it is met |
|-----------|---------------|
| All ML/inference inside Snowflake | `SNOWFLAKE.CORTEX.COMPLETE()` and Cortex Search used exclusively |
| No external LLM APIs | No OpenAI, Anthropic, or other external API calls anywhere in the codebase |
| Data from Marketplace listings only | All data sourced from Banking Analytics Bundle + Demographics Data Bundle |
| Streamlit in Snowflake for UI | `step5_streamlit_app.py` is deployed as a Streamlit in Snowflake app |
| Open-source libraries | All libraries listed below with attribution |

---

## Open-Source Library Attribution

| Library | Version | License | Use |
|---------|---------|---------|-----|
| [streamlit](https://github.com/streamlit/streamlit) | ≥1.28 | Apache 2.0 | Chat UI framework |
| [snowflake-snowpark-python](https://github.com/snowflakedb/snowpark-python) | ≥1.11 | Apache 2.0 | Snowflake session + DataFrame API |
| [snowflake-core](https://pypi.org/project/snowflake-core/) | ≥0.8 | Apache 2.0 | Cortex Search client |
| [snowflake-cortex](https://pypi.org/project/snowflake-cortex/) | ≥0.1 | Apache 2.0 | `Complete()` Python wrapper |
| [pandas](https://github.com/pandas-dev/pandas) | ≥2.0 | BSD 3-Clause | DataFrames for eval results |

---

## Evaluation  (Target)

| Metric | Target | Meaning |
|--------|--------|---------|
| Retrieval Precision | > 0.70 | ≥70% of retrieved chunks are relevant |
| Answer Faithfulness | > 0.80 | ≥80% of answer is grounded in retrieved context |

---
---

## Evaluation  (Results)

| Metric | Results | Meaning |
|--------|--------|---------|
| Retrieval Precision |  0.94 | ≥70% of retrieved chunks are relevant |
| Answer Faithfulness |  ~0.83 | ≥80% of answer is grounded in retrieved context |

---

