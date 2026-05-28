"""
database.py
-----------
Module quản lý kết nối database và cung cấp schema info cho LLM.

Tại sao tách ra module riêng?
- Single Responsibility Principle: mỗi file làm 1 việc
- Dễ test: có thể mock DatabaseManager trong unit tests
- Dễ mở rộng: sau này muốn hỗ trợ PostgreSQL chỉ cần sửa file này
"""

import sqlite3
import os
from typing import Optional
import pandas as pd


class DatabaseManager:
    """
    Quản lý kết nối và truy vấn SQLite database.
    
    Pattern: Context Manager → dùng được với `with` statement
    Ví dụ:
        with DatabaseManager("mydb.db") as db:
            df = db.run_query("SELECT * FROM customers")
    """

    def __init__(self, db_path: str):
        """
        Args:
            db_path: Đường dẫn tới file .db
        """
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> "DatabaseManager":
        """Mở kết nối tới database. Trả về self để dùng method chaining."""
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(
                f"Database not found at '{self.db_path}'. "
                f"Run 'python data/seed_database.py' first."
            )
        # check_same_thread=False cần thiết khi dùng với Streamlit
        # vì Streamlit có thể chạy callback trên thread khác
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        # Trả về dict thay vì tuple → dễ dùng hơn
        self._conn.row_factory = sqlite3.Row
        return self

    def disconnect(self) -> None:
        """Đóng kết nối database."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # --- Context Manager Protocol ---
    def __enter__(self):
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False  # False = không suppress exception

    # --- Query Methods ---
    def run_query(self, sql: str) -> pd.DataFrame:
        """
        Thực thi SQL query và trả về DataFrame.
        
        Tại sao dùng DataFrame thay vì list of tuples?
        - DataFrame dễ hiển thị hơn (Streamlit có st.dataframe)
        - Pandas có nhiều method để xử lý data sau query
        - Plotly/Matplotlib nhận DataFrame trực tiếp
        
        Args:
            sql: SQL query string
            
        Returns:
            pandas DataFrame với kết quả query
            
        Raises:
            sqlite3.Error: nếu SQL syntax sai
            RuntimeError: nếu chưa connect
        """
        if not self._conn:
            raise RuntimeError("Not connected. Call connect() first.")
        
        # pd.read_sql_query: wrapper của pandas cho SQL queries
        # Tự động convert kiểu dữ liệu (TEXT → str, INTEGER → int, etc.)
        df = pd.read_sql_query(sql, self._conn)
        return df

    def get_schema_description(self) -> str:
        """
        Tạo mô tả schema dạng text để inject vào system prompt của LLM.
        
        Đây là phần QUAN TRỌNG NHẤT của Text-to-SQL:
        LLM cần biết chính xác tên bảng, tên cột, kiểu dữ liệu
        để generate SQL đúng. Nếu prompt schema sai → SQL sai.
        
        Returns:
            String mô tả đầy đủ schema của database
        """
        if not self._conn:
            raise RuntimeError("Not connected. Call connect() first.")

        cursor = self._conn.cursor()
        
        # sqlite_master là bảng system của SQLite, chứa DDL của tất cả objects
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]

        schema_parts = []
        for table in tables:
            # PRAGMA table_info: trả về metadata của từng cột
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()

            # Lấy 3 dòng sample data để LLM hiểu format của data
            cursor.execute(f"SELECT * FROM {table} LIMIT 3")
            sample_rows = cursor.fetchall()

            col_definitions = []
            for col in columns:
                # col: (cid, name, type, notnull, dflt_value, pk)
                col_name = col[1]
                col_type = col[2]
                is_pk = "PRIMARY KEY" if col[5] else ""
                not_null = "NOT NULL" if col[3] else ""
                col_definitions.append(f"  - {col_name} ({col_type}) {is_pk} {not_null}".strip())

            schema_parts.append(
                f"Table: {table}\n"
                f"Columns:\n" + "\n".join(col_definitions) + "\n"
                f"Sample rows: {[dict(row) for row in sample_rows[:2]]}"
            )

        return "\n\n".join(schema_parts)

    def get_table_names(self) -> list[str]:
        """Trả về danh sách tên bảng trong database."""
        if not self._conn:
            raise RuntimeError("Not connected.")
        cursor = self._conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return [row[0] for row in cursor.fetchall()]

    def validate_query(self, sql: str) -> tuple[bool, str]:
        """
        Kiểm tra query có hợp lệ không mà KHÔNG thực thi thật.
        Dùng EXPLAIN để SQLite parse query mà không chạy.
        
        Returns:
            (True, "") nếu hợp lệ
            (False, error_message) nếu không hợp lệ
        """
        if not self._conn:
            raise RuntimeError("Not connected.")
        try:
            cursor = self._conn.cursor()
            # EXPLAIN chỉ parse, không execute → an toàn
            cursor.execute(f"EXPLAIN {sql}")
            return True, ""
        except sqlite3.Error as e:
            return False, str(e)