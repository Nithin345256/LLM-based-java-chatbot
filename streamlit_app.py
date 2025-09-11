import streamlit as st
import numpy as np
import json
import requests
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    st.error("GOOGLE_API_KEY is not set. Please add it to your .env file and restart the app.")
    st.stop()

# Load data efficiently
@st.cache_resource(show_spinner=True)
def load_data():
    with open("embeddings.json", "r", encoding="utf-8") as f:
        embeddings = np.array(json.load(f))
    with open("chunks.json", "r", encoding="utf-8") as f:
        chunks = json.load(f)
        if isinstance(chunks, dict) and "chunks" in chunks:
            chunks = chunks["chunks"]
    return embeddings, chunks

embeddings, chunks = load_data()

# Load embedding model
@st.cache_resource(show_spinner=True)
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

embedder = load_model()

# Cosine similarity
def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def get_top_k_chunks(query_embedding, k=5):
    scores = [cosine_similarity(query_embedding, emb) for emb in embeddings]
    top_k_idx = np.argsort(scores)[-k:][::-1]
    return [(chunks[i] if isinstance(chunks[i], str) else chunks[i].get("text", ""), scores[i]) for i in top_k_idx]

# Gemini API call
def ask_gemini(prompt):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=" + GOOGLE_API_KEY
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    response = requests.post(url, headers=headers, json=data, timeout=30)
    if response.status_code == 200:
        result = response.json()
        try:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return "[Error: Unexpected Gemini API response format]"
    else:
        return f"[Error: Gemini API returned {response.status_code}]"

# Streamlit UI
st.set_page_config(page_title="Java RAG Chatbot", layout="wide")
st.title("🔍 Java RAG Chatbot (Streamlit)")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

with st.form("ask_form"):
    query = st.text_area("Ask a question about Java:", height=80, key="query")
    submitted = st.form_submit_button("🚀 Ask Question")

if submitted and query.strip():
    with st.spinner("Generating embedding and searching knowledge base..."):
        query_embedding = embedder.encode([query])[0]
        top_chunks = get_top_k_chunks(query_embedding, k=5)
        context = "\n\n---\n\n".join([
            f"[Context {i+1} - Similarity: {score:.4f}]\n{chunk}" for i, (chunk, score) in enumerate(top_chunks)
        ])
        prompt = f"""You are an expert Java programming tutor. Answer the following question based ONLY on the provided context from the Java textbook.\n\nCONTEXT FROM JAVA TEXTBOOK:\n{context}\n\nQUESTION: {query}\n\nINSTRUCTIONS:\n- Provide a comprehensive answer based solely on the context\n- Include code examples in markdown format if present\n- If the context lacks sufficient information, clearly state this\n- Structure the answer with clear explanations and examples\n- Use proper Java terminology\n\nANSWER:"""
        answer = ask_gemini(prompt)
        st.session_state.chat_history.append({"question": query, "answer": answer, "context": context})

# Display chat history
for chat in reversed(st.session_state.chat_history):
    with st.expander(f"Q: {chat['question']}"):
        st.markdown(f"**A:**\n{chat['answer']}")
        with st.expander("Show context"):
            st.code(chat["context"], language="markdown")

st.info("💡 Tip: You can ask about Java concepts, code, or textbook content. Each answer is based only on the most relevant textbook chunks.")