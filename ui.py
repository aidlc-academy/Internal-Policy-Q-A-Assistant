# ui.py
"""
Streamlit UI for Internal Policy Q&A Assistant.

Usage:
    streamlit run ui.py
"""

import streamlit as st
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL", "http://localhost:8000")

# Page config
st.set_page_config(
    page_title="HR Policy Assistant",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Initialize session state
if 'current_question' not in st.session_state:
    st.session_state.current_question = ""
if 'should_search' not in st.session_state:
    st.session_state.should_search = False

# Custom CSS for dark theme
st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
    }
    
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        color: #ffffff;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    
    .subtitle {
        text-align: center;
        color: #8b92a8;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    .answer-box {
        background: #1e2130;
        padding: 2rem;
        border-radius: 12px;
        border: 2px solid #667eea;
        margin: 1.5rem 0;
        color: #c9d1d9;
        line-height: 1.8;
    }
    
    .unanswerable-box {
        background: #1e2130;
        padding: 2rem;
        border-radius: 12px;
        border: 2px solid #ff6b6b;
        margin: 1.5rem 0;
        color: #c9d1d9;
    }
    
    .source-card {
        background: #1e2130;
        border-left: 4px solid #667eea;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<h1 class="main-title">HR Policy Assistant</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Get answers to your HR policy questions instantly</p>', unsafe_allow_html=True)

# Layout
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Ask a Question")
    question = st.text_area(
        "Question",
        value=st.session_state.current_question,
        placeholder="e.g., How many days of casual leave am I entitled to per year?",
        height=120,
        label_visibility="collapsed"
    )
    
    search_clicked = st.button("Search Policies", use_container_width=True, type="primary")
    
    # Handle search
    if search_clicked or st.session_state.should_search:
        st.session_state.should_search = False
        
        if not question.strip():
            st.warning("Please enter a question.")
        else:
            with st.spinner("Searching policy documents..."):
                try:
                    response = httpx.post(
                        f"{API_URL}/ask",
                        json={"question": question},
                        timeout=60.0,
                    )
                    response.raise_for_status()
                    data = response.json()

                    status = data.get("status", "error")
                    answer = data.get("answer", "No answer returned.")
                    sources = data.get("sources", [])
                    conflict_warning = data.get("conflict_warning")

                    st.markdown("---")
                    
                    # Display answer
                    if status == "answered":
                        st.subheader("Answer")
                        st.markdown(f'<div class="answer-box">{answer}</div>', unsafe_allow_html=True)
                    elif status == "unanswerable":
                        st.subheader("Unable to Answer")
                        st.markdown(f'<div class="unanswerable-box">{answer}</div>', unsafe_allow_html=True)
                    else:
                        st.error(f"Error: {answer}")

                    if conflict_warning:
                        st.warning(f"Policy Conflict: {conflict_warning}")

                    # Display sources
                    if sources:
                        st.subheader("Source References")
                        st.caption(f"Found {len(sources)} relevant sections")
                        
                        for i, src in enumerate(sources, 1):
                            similarity_percent = src['similarity'] * 100
                            
                            with st.expander(f"Source #{i} - Page {src['page']} ({similarity_percent:.1f}% match)"):
                                st.markdown(f"**Document:** {src.get('document', 'Policy Document')}")
                                st.markdown(f"**Page:** {src['page']}")
                                st.markdown(f"**Section:** {src['section']}")
                                st.markdown(f"**Effective Date:** {src['effective_date']}")
                                st.progress(similarity_percent / 100, text=f"Relevance: {similarity_percent:.1f}%")

                except httpx.HTTPError as e:
                    st.error(f"Failed to connect to API: {e}")
                except Exception as e:
                    st.error(f"Unexpected error: {e}")

with col2:
    st.subheader("Try These Questions")
    
    example_questions = [
        "How many days of casual leave can I take?",
        "What is the probation period for new employees?",
        "How does medical reimbursement work?",
        "What are the standard office working hours?",
        "How do I apply for maternity leave?",
        "Can I encash my earned leave?",
    ]
    
    for eq in example_questions:
        if st.button(eq, key=f"example_{hash(eq)}", use_container_width=True):
            st.session_state.current_question = eq
            st.session_state.should_search = True
            st.rerun()

# Minimal sidebar
with st.sidebar:
    st.markdown("## About")
    st.markdown("""
    This system helps you find answers to HR policy questions quickly and accurately.
    
    All answers are sourced from official HR policy documents with page references.
    """)
    st.markdown("---")
    st.caption("Powered by AI")
