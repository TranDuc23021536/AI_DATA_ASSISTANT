"""
app.py
------
Streamlit web app - Entry point của toàn bộ project.

Chạy bằng: streamlit run app.py

Streamlit hoạt động như thế nào?
- Mỗi lần user tương tác (click, type), toàn bộ script chạy lại từ đầu
- st.session_state: dict persistent giữa các lần "re-run"
  → Dùng để lưu chat history, agent instance, etc.
- @st.cache_resource: cache objects nặng (DB connection, agent)
  → Chỉ khởi tạo 1 lần, không init lại mỗi lần re-run

UI Layout:
┌─────────────────────────────────────────┐
│  Sidebar: Config + Suggested Questions  │
├─────────────────────────────────────────┤
│  Main: Chat History                     │
│  [User Q] [AI Answer + Chart + Table]   │
│  ...                                    │
│  Input Box (bottom)                     │
└─────────────────────────────────────────┘
"""

import streamlit as st
import pandas as pd
import os
import sys
from dotenv import load_dotenv

# Load .env file (GROQ_API_KEY, etc.)
# load_dotenv() đọc file .env trong thư mục hiện tại
load_dotenv()

# Thêm project root vào Python path để import được src.*
sys.path.insert(0, os.path.dirname(__file__))

from src.database import DatabaseManager
from src.agent import DataAssistantAgent
from src.visualizer import auto_visualize

# ============================================================
# PAGE CONFIG - Phải là lệnh Streamlit đầu tiên được gọi
# ============================================================
st.set_page_config(
    page_title="AI Data Assistant",
    page_icon="🤖",
    layout="wide",       # "wide" dùng full browser width
    initial_sidebar_state="expanded",
)

# ============================================================
# CUSTOM CSS
# ============================================================
st.markdown("""
<style>
    /* Chat message styling */
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 12px 16px;
        border-radius: 12px 12px 4px 12px;
        margin: 8px 0;
        max-width: 80%;
        margin-left: auto;
    }
    .assistant-message {
        background: #f8f9fa;
        border-left: 4px solid #667eea;
        padding: 12px 16px;
        border-radius: 4px 12px 12px 12px;
        margin: 8px 0;
    }
    .sql-box {
        background: #1e1e1e;
        color: #d4d4d4;
        padding: 12px;
        border-radius: 8px;
        font-family: 'Courier New', monospace;
        font-size: 13px;
        white-space: pre-wrap;
    }
    .metric-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    /* Sidebar styling */
    .sidebar-question {
        background: #f0f2f6;
        padding: 8px 12px;
        border-radius: 6px;
        margin: 4px 0;
        cursor: pointer;
        font-size: 13px;
    }
    .sidebar-question:hover {
        background: #e0e4ec;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# DATABASE PATH
# ============================================================
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "ecommerce.db")


# ============================================================
# CACHED RESOURCES
# ============================================================
# @st.cache_resource: chạy 1 lần, cache kết quả suốt session
# Tại sao? DatabaseManager và Agent nặng, không muốn init lại mỗi click

@st.cache_resource
def get_db_manager() -> DatabaseManager:
    """Khởi tạo và connect DatabaseManager (cached)."""
    db = DatabaseManager(DB_PATH)
    db.connect()
    return db


@st.cache_resource
def get_agent() -> DataAssistantAgent:
    """Khởi tạo Agent với DatabaseManager (cached)."""
    db = get_db_manager()
    return DataAssistantAgent(db_manager=db)


# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================
# session_state persist qua các re-runs trong cùng browser tab
if "chat_history" not in st.session_state:
    # List of dicts: {"role": "user"/"assistant", "content": str, "data": dict}
    st.session_state.chat_history = []

if "query_count" not in st.session_state:
    st.session_state.query_count = 0


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/artificial-intelligence.png", width=60)
    st.title("AI Data Assistant")
    st.caption("E-commerce Analytics powered by LLM + SQL")

    st.divider()

    # Model selector
    model_choice = st.selectbox(
        "🤖 LLM Model",
        options=[
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
        ],
        help="Larger models = more accurate SQL, but slower. All free on Groq.",
    )

    st.divider()

    # Database stats
    st.subheader("📊 Database Info")
    try:
        db = get_db_manager()
        tables = db.get_table_names()
        for table in tables:
            count_df = db.run_query(f"SELECT COUNT(*) as cnt FROM {table}")
            cnt = count_df["cnt"].iloc[0]
            st.metric(label=f"📋 {table}", value=f"{cnt:,} rows")
    except Exception as e:
        st.error(f"DB Error: {e}")

    st.divider()

    # Suggested questions
    st.subheader("💡 Try asking:")
    try:
        agent = get_agent()
        suggestions = agent.get_suggested_questions()
        for q in suggestions:
            # Mỗi button click sẽ set session state
            if st.button(f"→ {q}", key=f"suggest_{q[:20]}", use_container_width=True):
                st.session_state.pending_question = q
    except Exception:
        pass

    st.divider()

    # Clear history button
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.query_count = 0
        st.rerun()  # Trigger re-run để clear UI


# ============================================================
# MAIN CONTENT
# ============================================================
st.title("🤖 AI Data Assistant")
st.caption(f"Ask questions about your e-commerce data in plain English or Vietnamese")

# Stats row
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Queries this session", st.session_state.query_count)
with col2:
    st.metric("Database", "E-commerce SQLite")
with col3:
    st.metric("LLM", model_choice.split("-")[0].upper())

st.divider()

# ============================================================
# CHAT HISTORY DISPLAY
# ============================================================
chat_container = st.container()

with chat_container:
    for i, msg in enumerate(st.session_state.chat_history):
        if msg["role"] == "user":
            # User message (right-aligned via CSS)
            with st.chat_message("user"):
                st.write(msg["content"])

        else:
            # Assistant message
            with st.chat_message("assistant", avatar="🤖"):
                data = msg.get("data", {})

                # Natural language answer
                st.write(data.get("answer", ""))

                if data.get("success"):
                    # Tabs: Answer | SQL | Data
                    tab1, tab2, tab3 = st.tabs(["📊 Chart", "🔍 SQL Query", "📋 Data Table"])

                    with tab1:
                        # Auto-generate chart
                        df = data.get("dataframe", pd.DataFrame())
                        if not df.empty:
                            fig = auto_visualize(df, title=msg.get("question", ""))
                            if fig:
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("📋 This result is better shown as a table. See 'Data Table' tab.")
                        else:
                            st.info("No data to visualize.")

                    with tab2:
                        # SQL query với syntax highlighting
                        st.markdown("**Generated SQL:**")
                        st.code(data.get("sql", ""), language="sql")
                        st.caption("💡 This is the exact SQL query sent to the database")

                    with tab3:
                        # Data table
                        df = data.get("dataframe", pd.DataFrame())
                        if not df.empty:
                            st.caption(f"Showing {min(100, len(df))} of {len(df)} rows")
                            st.dataframe(
                                df.head(100),
                                use_container_width=True,
                                hide_index=True,
                            )
                            # Download button
                            csv = df.to_csv(index=False)
                            st.download_button(
                                label="⬇️ Download as CSV",
                                data=csv,
                                file_name=f"query_result_{i}.csv",
                                mime="text/csv",
                            )
                        else:
                            st.info("No data returned.")
                else:
                    # Error case
                    st.error(data.get("error", "Unknown error"))


# ============================================================
# CHAT INPUT
# ============================================================
# Handle suggested question từ sidebar buttons
default_input = ""
if "pending_question" in st.session_state:
    default_input = st.session_state.pending_question
    del st.session_state.pending_question

# st.chat_input: Streamlit built-in chat input box (fixed at bottom)
user_input = st.chat_input(
    "Ask anything about your data... (e.g. 'Top 5 customers by revenue')",
)

# Nếu user nhấn suggestion button, dùng câu đó
question = user_input or default_input

if question:
    # ---- Add user message to history ----
    st.session_state.chat_history.append({
        "role": "user",
        "content": question,
    })

    # ---- Run agent ----
    with st.spinner("🤔 Thinking... Generating SQL..."):
        try:
            agent = get_agent()
            result = agent.query(question)
            result["question"] = question
        except FileNotFoundError as e:
            result = {
                "answer": f"❌ Database not found. Please run:\n```\npython data/seed_database.py\n```",
                "sql": "",
                "dataframe": pd.DataFrame(),
                "success": False,
                "error": str(e),
                "question": question,
            }
        except ValueError as e:
            result = {
                "answer": f"❌ Configuration error: {str(e)}",
                "sql": "",
                "dataframe": pd.DataFrame(),
                "success": False,
                "error": str(e),
                "question": question,
            }

    # ---- Add assistant response to history ----
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": result["answer"],
        "question": question,
        "data": result,
    })

    st.session_state.query_count += 1

    # Trigger re-run để hiển thị message mới
    st.rerun()


# ============================================================
# EMPTY STATE
# ============================================================
if not st.session_state.chat_history:
    st.markdown("""
    <div style="text-align: center; padding: 60px 20px; color: #666;">
        <h2>👋 Welcome to AI Data Assistant!</h2>
        <p>Ask questions about your e-commerce data in plain English or Vietnamese.</p>
        <p><strong>Examples:</strong></p>
        <p>• "What are the top 5 products by revenue?"</p>
        <p>• "How many orders were placed in Q1 2023?"</p>
        <p>• "Which region generates the most sales?"</p>
        <br>
        <p style="font-size: 12px;">💡 Click any suggestion in the sidebar to get started!</p>
    </div>
    """, unsafe_allow_html=True)