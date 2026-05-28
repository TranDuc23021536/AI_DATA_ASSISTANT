# 🤖 AI Data Assistant

> **Natural Language → SQL → Interactive Visualization**
>
> Ask questions about your e-commerce data in plain English or Vietnamese — no SQL knowledge needed.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![LangChain](https://img.shields.io/badge/LangChain-0.3-green?logo=chainlink)
![Streamlit](https://img.shields.io/badge/Streamlit-1.45-red?logo=streamlit)
![SQLite](https://img.shields.io/badge/SQLite-3-lightblue?logo=sqlite)
![Plotly](https://img.shields.io/badge/Plotly-5.24-purple?logo=plotly)
![Docker](https://img.shields.io/badge/Docker-ready-blue?logo=docker)

---

## 🎯 What It Does

Type a question like:
- *"What are the top 5 products by revenue?"*
- *"How many orders were placed each month in 2023?"*
- *"Which region generates the most sales?"*

The AI will:
1. **Understand** your question using an LLM (Llama 3.3 via Groq)
2. **Generate** the correct SQL query automatically
3. **Execute** it against a real SQLite database
4. **Visualize** results with interactive Plotly charts
5. **Explain** the findings in natural language

---

## 🏗️ Architecture

```
User Question (Natural Language)
         │
         ▼
┌─────────────────────────────────┐
│       DataAssistantAgent        │  ← src/agent.py
│                                 │
│  1. Inject DB schema into prompt│
│  2. LLM generates SQL query     │
│  3. Validate SQL syntax         │
│  4. Execute query on SQLite     │
│  5. LLM explains results        │
└─────────────────────────────────┘
         │                │
         ▼                ▼
┌──────────────┐  ┌──────────────────┐
│DatabaseManager│  │  ChartRecommender │
│  src/database │  │  src/visualizer   │
│               │  │                  │
│ SQLite conn   │  │ Auto-detect chart │
│ Schema reader │  │ type → Plotly fig │
│ Query runner  │  │                  │
└──────────────┘  └──────────────────┘
         │
         ▼
┌──────────────┐
│  Streamlit   │  ← app.py
│   Web UI     │
│              │
│ Chat history │
│ Chart display│
│ SQL viewer   │
│ Data table   │
└──────────────┘
```

### Key Design Decisions

| Decision | Why |
|----------|-----|
| **2 LLM chains** instead of 1 agent | Easier to debug (see exact SQL), easier to explain in interviews |
| **SQLite** instead of PostgreSQL | No server setup needed, perfect for demo |
| **Groq + Llama 3.3** instead of OpenAI | Free tier available, very fast inference |
| **Pandas DataFrame** as return type | Works natively with Streamlit, Plotly |
| **Schema injection in prompt** | LLM needs exact table/column names to generate correct SQL |

---

## 📁 Project Structure

```
AI_DATA_ASSISTANT/
├── app.py                    # Streamlit app (entry point)
├── requirements.txt          # Python dependencies
├── Dockerfile                # Docker container config
├── docker-compose.yml        # Multi-container setup
├── .env.example              # Environment variables template
├── .gitignore
│
├── src/                      # Core business logic
│   ├── __init__.py
│   ├── agent.py              # LangChain SQL agent
│   ├── database.py           # SQLite connection & query manager
│   └── visualizer.py        # Auto chart generation with Plotly
│
├── data/
│   └── seed_database.py      # Script to create & populate DB
│
└── tests/
    └── test_core.py          # Unit tests (pytest)
```

---

## 🚀 Quick Start

### Option 1: Local Setup (Recommended for Development)

```bash
# 1. Clone the repo
git clone https://github.com/TranDuc23021536/AI_DATA_ASSISTANT.git
cd AI_DATA_ASSISTANT

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Get a FREE Groq API key
# → Go to https://console.groq.com → Sign up → Create API key

# 5. Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

# 6. Create the database with sample data
python data/seed_database.py

# 7. Run the app!
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

### Option 2: Docker

```bash
# 1. Clone & configure
git clone https://github.com/TranDuc23021536/AI_DATA_ASSISTANT.git
cd AI_DATA_ASSISTANT
cp .env.example .env
# Edit .env with your GROQ_API_KEY

# 2. Build and run
docker-compose up --build

# App will be at http://localhost:8501
```

---

## 🔧 Configuration

Edit `.env` file:

```env
GROQ_API_KEY=your_key_here    # Required: get at https://console.groq.com
```

Available LLM models (selectable in sidebar):
- `llama-3.3-70b-versatile` — Best accuracy, free tier
- `llama-3.1-8b-instant` — Faster, slightly less accurate
- `mixtral-8x7b-32768` — Large context window

---

## 🗄️ Database Schema

The app comes with a realistic e-commerce dataset:

```sql
customers (customer_id, name, email, city, region, signup_date)
    └── 50 customers across Vietnam (North/Central/South)

products (product_id, name, category, price, stock)
    └── 27 products: Electronics, Fashion, Books, Home & Kitchen, Sports

orders (order_id, customer_id, order_date, status, total_amount)
    └── 300 orders (pending / shipped / delivered / cancelled)

order_items (item_id, order_id, product_id, quantity, unit_price)
    └── Order line items connecting orders ↔ products
```

---

## 🧪 Running Tests

```bash
# Run all tests with verbose output
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=src --cov-report=term-missing
```

Current test coverage: **database.py** and **visualizer.py** modules.

---

## 💡 Example Questions

```
# Revenue Analysis
"What are the top 5 products by total revenue?"
"Show me monthly revenue trend in 2023"
"Which category generates the most sales?"

# Customer Analytics
"Which customers have placed the most orders?"
"How many customers are from Hanoi?"
"Show me customers who joined in 2023 and have spent over 5 million VND"

# Order Insights
"What percentage of orders are cancelled?"
"Show me all pending orders sorted by amount"
"Which month had the highest number of orders?"

# Inventory
"List products with stock below 50"
"What is the average price per category?"
```

---

## 🛠️ Tech Stack

| Technology | Purpose | Why Chosen |
|-----------|---------|-----------|
| **Python 3.11** | Language | Strong data ecosystem |
| **LangChain** | LLM orchestration | Abstracts provider differences, built-in chains |
| **Groq (Llama 3.3)** | LLM inference | Free tier, very fast (GroqChip hardware) |
| **SQLite** | Database | Zero-config, file-based, perfect for demos |
| **Pandas** | Data manipulation | Standard for tabular data in Python |
| **Plotly** | Visualization | Interactive charts, native Streamlit support |
| **Streamlit** | Web UI | Rapid prototyping, Python-native |
| **Docker** | Containerization | Reproducible environment |
| **pytest** | Testing | Industry standard Python test framework |

---

## 📚 How Text-to-SQL Works

The core technique is **prompt engineering with schema injection**:

```python
prompt = f"""
You are an expert SQL analyst.

DATABASE SCHEMA:
{schema}           # ← Inject actual table names, columns, sample data

USER QUESTION: {question}

Generate ONLY a valid SQLite SELECT query:
"""
```

The LLM uses the schema to know exact table/column names, then generates syntactically correct SQL. The result is executed on the real database, and a second LLM call converts the data rows into a human-readable answer.

---

## 🙋 Author

**Tran Manh Duc** — Computer Science @ UET VNU Hanoi

- GitHub: [@TranDuc23021536](https://github.com/TranDuc23021536)
- Email: ducalhp3@gmail.com