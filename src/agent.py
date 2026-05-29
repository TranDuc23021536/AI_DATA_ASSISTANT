"""
agent.py
--------
Core module: LangChain Text-to-SQL Agent.

FLOW TỔNG QUAN:
User hỏi bằng tiếng Anh/Việt
    ↓
Agent nhận câu hỏi + schema info
    ↓
LLM (Groq/GPT) generate SQL query
    ↓
Agent thực thi SQL trên SQLite
    ↓
LLM đọc kết quả, viết câu trả lời tự nhiên
    ↓
Trả về: answer + sql_used + dataframe

"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq

import pandas as pd
import re
import os
from typing import Optional

from src.database import DatabaseManager


# ============================================================
# SYSTEM PROMPT - Đây là "trái tim" của Text-to-SQL
# ============================================================
# Prompt này nói cho LLM biết:
# 1. Nó là ai (SQL expert)
# 2. Database schema trông như thế nào
# 3. Rules cần follow
# 4. Format output cần ra sao
SQL_GENERATION_PROMPT = """You are an expert SQL analyst working with a Vietnamese e-commerce database.

DATABASE SCHEMA:
{schema}

RULES (MUST FOLLOW):
1. Generate ONLY a single valid SQLite SELECT query - no explanations, no markdown backticks
2. Use exact table and column names from the schema above
3. For Vietnamese names/cities in WHERE clauses, use LIKE with wildcards: WHERE city LIKE '%Hanoi%'
4. Always use table aliases for clarity (e.g., c for customers, o for orders)
5. For aggregations, always include meaningful column aliases (e.g., COUNT(*) AS total_orders)
6. LIMIT results to 100 rows maximum unless user asks for all data
7. Date format in database is YYYY-MM-DD (TEXT type, but SQLite can compare strings directly)
8. For "top N" queries, use ORDER BY + LIMIT
9. If the question cannot be answered with the available tables, return: SELECT 'Cannot answer this question' AS message

IMPORTANT: Return ONLY the SQL query, nothing else. No ```sql, no explanation.

USER QUESTION: {question}

SQL QUERY:"""

ANSWER_GENERATION_PROMPT = """You are a helpful data analyst. The user asked a question about e-commerce data,
and a SQL query was executed. Explain the results clearly and concisely.

USER QUESTION: {question}

SQL QUERY USED:
{sql_query}

QUERY RESULTS (first 10 rows shown):
{results}

Total rows returned: {row_count}

Provide a clear, conversational answer in the same language as the user's question.
Include specific numbers and insights from the data.
If the results are empty, explain what that means.
Keep the answer under 150 words."""


class DataAssistantAgent:
    """
    LangChain-based agent để trả lời câu hỏi về database bằng ngôn ngữ tự nhiên.
    
    Architecture:
    - Chain 1: Question → SQL query (sql_chain)
    - Chain 2: Question + SQL + Results → Natural language answer (answer_chain)
    
    Tại sao dùng 2 chain riêng biệt thay vì 1 agent?
    - Dễ debug: biết chính xác SQL được generate là gì
    - Dễ validate: có thể check SQL trước khi chạy
    - Dễ explain khi phỏng vấn!
    """

    def __init__(self, db_manager: DatabaseManager, model_name: str = "llama-3.3-70b-versatile"):
        """
        Args:
            db_manager: DatabaseManager instance đã connected
            model_name: Tên model Groq. Các options phổ biến:
                - "llama-3.3-70b-versatile" (mạnh nhất, free tier)
                - "llama-3.1-8b-instant" (nhanh hơn, ít capable hơn)
                - "mixtral-8x7b-32768" (context window lớn)
        """
        self.db = db_manager

        # Lấy API key từ environment variable
        # KHÔNG bao giờ hardcode API key trong code!
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not found in environment. "
                "Create a .env file with: GROQ_API_KEY=your_key_here\n"
                "Get free key at: https://console.groq.com"
            )

        # ChatGroq: LangChain wrapper cho Groq API
        # temperature=0: output deterministic (SQL cần chính xác, không cần creative)
        self.llm = ChatGroq(
            api_key=api_key,
            model_name=model_name,
            temperature=0,       # 0 = deterministic, 1 = more creative/random
            max_tokens=1024,     # Đủ cho SQL query + answer
        )

        # Build hai chains
        self._sql_chain = self._build_sql_chain()
        self._answer_chain = self._build_answer_chain()

        # Cache schema để không phải đọc database mỗi lần query
        self._schema_cache: Optional[str] = None

    def _build_sql_chain(self):
        """
        Chain 1: Natural language → SQL query
        
        LangChain Expression Language (LCEL) dùng pipe operator |
        Đọc từ trái sang phải:
        prompt → llm → output_parser
        
        prompt: format template với input variables
        llm: gọi API, trả về AIMessage object  
        StrOutputParser: extract .content từ AIMessage → plain string
        """
        prompt = ChatPromptTemplate.from_template(SQL_GENERATION_PROMPT)
        # StrOutputParser chuyển AIMessage → str
        return prompt | self.llm | StrOutputParser()

    def _build_answer_chain(self):
        """
        Chain 2: Question + SQL + Results → Natural language answer
        """
        prompt = ChatPromptTemplate.from_template(ANSWER_GENERATION_PROMPT)
        return prompt | self.llm | StrOutputParser()

    def _get_schema(self) -> str:
        """Lấy schema (có cache để tránh đọc DB nhiều lần)."""
        if not self._schema_cache:
            self._schema_cache = self.db.get_schema_description()
        return self._schema_cache

    def _extract_sql(self, raw_output: str) -> str:
        """
        Clean SQL output từ LLM.
        
        Đôi khi LLM trả về SQL với markdown backticks hoặc text thừa.
        Hàm này extract phần SQL thuần túy.
        
        Args:
            raw_output: Raw string từ LLM
            
        Returns:
            Clean SQL string
        """
        # Remove markdown code blocks nếu có: ```sql ... ``` hoặc ``` ... ```
        raw_output = re.sub(r"```(?:sql)?\n?", "", raw_output, flags=re.IGNORECASE)
        raw_output = raw_output.replace("```", "")

        # Trim whitespace
        sql = raw_output.strip()

        # Nếu LLM trả về nhiều dòng, tìm dòng bắt đầu bằng SELECT/WITH
        lines = sql.split("\n")
        sql_lines = []
        started = False
        for line in lines:
            stripped = line.strip().upper()
            if stripped.startswith(("SELECT", "WITH", "EXPLAIN")):
                started = True
            if started:
                sql_lines.append(line)

        if sql_lines:
            return "\n".join(sql_lines).strip()
        return sql

    def query(self, question: str) -> dict:
        """
        Main method: nhận câu hỏi, trả về answer + metadata.
        
        Args:
            question: Câu hỏi bằng ngôn ngữ tự nhiên (Anh hoặc Việt)
            
        Returns:
            dict với keys:
                - "answer": str - câu trả lời tự nhiên
                - "sql": str - SQL query đã dùng
                - "dataframe": pd.DataFrame - data thô
                - "success": bool
                - "error": str (nếu có lỗi)
        """
        schema = self._get_schema()

        # ---- STEP 1: Generate SQL ----
        try:
            raw_sql = self._sql_chain.invoke({
                "schema": schema,
                "question": question
            })
            sql = self._extract_sql(raw_sql)
        except Exception as e:
            return {
                "answer": f"❌ Failed to generate SQL: {str(e)}",
                "sql": "",
                "dataframe": pd.DataFrame(),
                "success": False,
                "error": str(e)
            }

        # ---- STEP 2: Validate SQL (optional safety check) ----
        is_valid, error_msg = self.db.validate_query(sql)
        if not is_valid:
            # Nếu SQL invalid, thử một lần nữa với error context
            retry_question = f"{question}\n\nNote: Previous attempt generated invalid SQL: {sql}\nError: {error_msg}\nPlease fix."
            try:
                raw_sql = self._sql_chain.invoke({
                    "schema": schema,
                    "question": retry_question
                })
                sql = self._extract_sql(raw_sql)
            except Exception as e:
                return {
                    "answer": f"❌ SQL validation failed: {error_msg}",
                    "sql": sql,
                    "dataframe": pd.DataFrame(),
                    "success": False,
                    "error": error_msg
                }

        # ---- STEP 3: Execute SQL ----
        try:
            df = self.db.run_query(sql)
        except Exception as e:
            return {
                "answer": f"❌ Query execution failed: {str(e)}\n\nSQL attempted:\n{sql}",
                "sql": sql,
                "dataframe": pd.DataFrame(),
                "success": False,
                "error": str(e)
            }

        # ---- STEP 4: Generate natural language answer ----
        try:
            # Chỉ truyền 10 rows đầu vào prompt để không vượt context limit
            results_preview = df.head(10).to_string(index=False) if not df.empty else "No results found."

            answer = self._answer_chain.invoke({
                "question": question,
                "sql_query": sql,
                "results": results_preview,
                "row_count": len(df)
            })
        except Exception as e:
            # Nếu answer chain fail, vẫn trả về data (không crash)
            answer = f"Query returned {len(df)} rows. See the table below for details."

        return {
            "answer": answer,
            "sql": sql,
            "dataframe": df,
            "success": True,
            "error": ""
        }

    def get_suggested_questions(self) -> list[str]:
        """
        Trả về danh sách câu hỏi mẫu để user biết có thể hỏi gì.
        Hiển thị trong sidebar của Streamlit app.
        """
        return [
            "What are the top 5 best-selling products by total revenue?",
            "How many orders were placed each month in 2023?",
            "Which city has the most customers?",
            "What is the average order value by product category?",
            "Show me all orders with status 'cancelled' and their total amount",
            "Which customers have spent the most money overall?",
            "What percentage of orders are delivered vs cancelled?",
            "List products with stock below 50",
            "What is the total revenue by region (North/Central/South)?",
            "Show me the top 3 customers from Hanoi by total spending",
        ]