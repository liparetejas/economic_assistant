# ============================================================================
#  Economic Intelligence Assistant — Streamlit in Snowflake (SiS)
#  Uses only: streamlit, snowflake-snowpark-python (both pre-installed in SiS)
#  All Cortex calls via session.sql() — zero extra packages needed.
# ============================================================================

import streamlit as st
import json
from snowflake.snowpark.context import get_active_session

# ── CONFIG ────────────────────────────────────────────────────────────────────
TARGET_DB     = "RAG_HACKATHON_DB"
TARGET_SCHEMA = "RAG_SCHEMA"
SERVICE_NAME  = "ECONOMIC_SEARCH"
LLM_MODEL     = "llama3.1-70b"
TOP_K         = 5
# ─────────────────────────────────────────────────────────────────────────────

session = get_active_session()


# ── CORE FUNCTIONS ────────────────────────────────────────────────────────────

def retrieve(query: str, k: int, source_filter: str = "all") -> list:
    """
    Calls Cortex Search via the REST endpoint using session._run_query.
    Falls back to SEARCH_PREVIEW SQL if REST is unavailable.
    """
    # Build request payload
    payload = {
        "query": query,
        "columns": ["chunk_text", "source", "doc_id", "title", "chunk_index"],
        "limit": k
    }
    if source_filter != "all":
        payload["filter"] = {"@eq": {"source": source_filter}}

    # Escape the JSON for embedding inside a SQL string literal
    payload_str = json.dumps(payload, ensure_ascii=True)
    # Double-escape single quotes for SQL safety
    payload_escaped = payload_str.replace("'", "\\'")

    sql = f"""
        SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
            '{TARGET_DB}.{TARGET_SCHEMA}.{SERVICE_NAME}',
            $${payload_str}$$
        )::VARCHAR AS results
    """
    try:
        row = session.sql(sql).collect()[0]
        parsed = json.loads(row["RESULTS"])
        return parsed.get("results", [])
    except Exception as e:
        st.error(f"Retrieval error: {e}")
        return []


def complete(model: str, prompt: str) -> str:
    """Calls SNOWFLAKE.CORTEX.COMPLETE via SQL using dollar-quote escaping."""
    # Use Snowflake dollar-quoting ($$) to avoid single-quote escaping issues
    sql = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', $${prompt}$$) AS response"
    try:
        return session.sql(sql).collect()[0]["RESPONSE"]
    except Exception as e:
        return f"Generation error: {e}"


def build_context(chunks: list) -> tuple:
    ctx, sources = "", []
    for i, c in enumerate(chunks):
        title  = str(c.get("title",  "N/A") or "N/A")
        source = str(c.get("source", "unknown"))
        text   = str(c.get("chunk_text", ""))
        ctx   += f"\n[Source {i+1}: {title[:60]} | {source}]\n{text}\n"
        sources.append({
            "id":      i + 1,
            "title":   title,
            "source":  source,
            "snippet": text[:280],
            "doc_id":  str(c.get("doc_id", "")),
        })
    return ctx, sources


def generate_answer(question: str, context: str, model: str) -> str:
    prompt = f"""You are an economic and financial intelligence assistant.
Answer using ONLY the context below. Add [Source N] citations after every fact.
If the context lacks information, say: 'The available data does not cover this topic.'
Do NOT invent facts or use outside knowledge.

Context:
{context}

Question: {question}

Answer (with [Source N] citations):"""
    return complete(model, prompt)


def log_to_snowflake(question: str, answer: str, sources: list, model: str, k: int):
    try:
        session.sql(f"""
            CREATE TABLE IF NOT EXISTS {TARGET_DB}.{TARGET_SCHEMA}.RAG_QUERY_LOG (
                query_id   VARCHAR DEFAULT UUID_STRING(),
                question   VARCHAR,
                answer     VARCHAR,
                sources    VARIANT,
                model      VARCHAR,
                top_k      INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
            )
        """).collect()
        s_json = json.dumps(sources)
        session.sql(f"""
            INSERT INTO {TARGET_DB}.{TARGET_SCHEMA}.RAG_QUERY_LOG
                (question, answer, sources, model, top_k)
            SELECT $${question}$$, $${answer}$$, PARSE_JSON($${s_json}$$), '{model}', {k}
        """).collect()
    except Exception:
        pass


# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Economic Intelligence Assistant", page_icon="📊", layout="wide")

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")

    source_filter = st.selectbox(
        "Dataset filter", options=["all", "banking", "demographics"], index=0
    )
    top_k = st.slider("Chunks retrieved (k)", min_value=3, max_value=10, value=TOP_K)
    model_choice = st.selectbox(
        "Cortex LLM model",
        options=["llama3.1-70b", "llama3.1-8b", "mistral-large2", "snowflake-arctic"],
        index=0,
    )

    st.divider()
    st.header("🔍 Source Citations")
    if "last_sources" in st.session_state and st.session_state.last_sources:
        for s in st.session_state.last_sources:
            with st.expander(f"[{s['id']}] {s['title'][:42]}..."):
                st.caption(f"Dataset: **{s['source'].upper()}**")
                st.write(s["snippet"])
                if s.get("doc_id"):
                    st.caption(f"doc_id: `{s['doc_id']}`")
    else:
        st.info("Sources appear here after each answer.")

    st.divider()
    if st.button("🗑️ Clear conversation"):
        st.session_state.messages = []
        st.session_state.last_sources = []
        st.rerun()

# ── MAIN CHAT ─────────────────────────────────────────────────────────────────
st.title("📊 Economic Intelligence Assistant")
st.caption(
    "Powered by **Snowflake Cortex Search** + **COMPLETE()** · "
    "Banking Analytics Bundle + Demographics Data Bundle"
)

# Starter chips
col1, col2, col3 = st.columns(3)
starters = [
    "What banking metrics are in the dataset?",
    "Summarize income distribution from demographics data",
    "How might demographic trends affect credit risk?",
]
for col, starter in zip([col1, col2, col3], starters):
    if col.button(starter, use_container_width=True):
        if "messages" not in st.session_state:
            st.session_state.messages = []
        st.session_state.messages.append({"role": "user", "content": starter})
        st.session_state["_pending_query"] = starter

st.divider()

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content":
        "👋 Hello! Ask me about US banking analytics, demographic data, loan performance, income distribution, or cross-dataset economic insights."}]
if "last_sources" not in st.session_state:
    st.session_state.last_sources = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

pending    = st.session_state.pop("_pending_query", None)
user_input = st.chat_input("Ask about banking data, demographics, or economic trends...")
question   = pending or user_input

if question:
    if not pending:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("🔍 Searching and generating answer..."):
            chunks           = retrieve(question, k=top_k, source_filter=source_filter)
            context, sources = build_context(chunks)
            answer           = generate_answer(question, context, model=model_choice)
            st.session_state.last_sources = sources
            log_to_snowflake(question, answer, sources, model_choice, top_k)

        st.markdown(answer)

        if sources:
            st.markdown("---")
            st.caption("**Retrieved sources:**")
            pills = st.columns(min(len(sources), 5))
            for idx, s in enumerate(sources):
                pills[idx % 5].markdown(f"`[{s['id']}]` **{s['source'].upper()}** · {s['title'][:28]}...")

    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.rerun()