import pytest
import pandas as pd
import sqlite3
import tempfile
import os

# Import các modules cần test
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.database import DatabaseManager
from src.visualizer import ChartRecommender, auto_visualize


# ============================================================
# FIXTURES
# ============================================================
# pytest fixture: code setup chạy trước mỗi test function

@pytest.fixture
def temp_db():
    """
    Tạo SQLite database tạm thời trong memory cho testing.
    Dùng ":memory:" thay vì file path → database chỉ tồn tại trong RAM.
    Mỗi test có db sạch, không ảnh hưởng nhau.
    """
    # Tạo file tạm
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Setup schema và data
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            region TEXT NOT NULL,
            signup_date TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            order_date TEXT,
            status TEXT,
            total_amount REAL
        )
    """)
    conn.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
        [
            (1, "Nguyen Van A", "Hanoi", "North", "2023-01-15"),
            (2, "Tran Thi B", "Ho Chi Minh", "South", "2023-03-20"),
            (3, "Le Van C", "Da Nang", "Central", "2023-06-10"),
        ]
    )
    conn.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
        [
            (1, 1, "2023-02-01", "delivered", 500_000),
            (2, 1, "2023-03-15", "delivered", 1_200_000),
            (3, 2, "2023-04-20", "pending", 800_000),
            (4, 3, "2023-05-10", "cancelled", 300_000),
        ]
    )
    conn.commit()
    conn.close()

    yield db_path  # Trả db_path cho test function

    # Teardown: xóa file sau khi test xong
    os.unlink(db_path)


@pytest.fixture
def db_manager(temp_db):
    """DatabaseManager connected tới temp DB."""
    manager = DatabaseManager(temp_db)
    manager.connect()
    yield manager
    manager.disconnect()


# ============================================================
# TEST: DatabaseManager
# ============================================================

class TestDatabaseManager:
    """Tests cho DatabaseManager class."""

    def test_connect_success(self, temp_db):
        """Test connect thành công với file DB hợp lệ."""
        manager = DatabaseManager(temp_db)
        result = manager.connect()
        assert result is manager  # Method chaining: trả về self
        manager.disconnect()

    def test_connect_file_not_found(self):
        """Test connect với file không tồn tại → FileNotFoundError."""
        manager = DatabaseManager("/nonexistent/path/db.sqlite")
        with pytest.raises(FileNotFoundError):
            manager.connect()

    def test_run_query_returns_dataframe(self, db_manager):
        """Test run_query trả về pandas DataFrame."""
        df = db_manager.run_query("SELECT * FROM customers")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3  # 3 customers đã insert
        assert "name" in df.columns
        assert "city" in df.columns

    def test_run_query_with_where(self, db_manager):
        """Test query có WHERE clause."""
        df = db_manager.run_query(
            "SELECT * FROM customers WHERE region = 'North'"
        )
        assert len(df) == 1
        assert df.iloc[0]["city"] == "Hanoi"

    def test_run_query_aggregate(self, db_manager):
        """Test aggregate query."""
        df = db_manager.run_query(
            "SELECT COUNT(*) as total FROM orders WHERE status = 'delivered'"
        )
        assert df.iloc[0]["total"] == 2

    def test_run_query_join(self, db_manager):
        """Test JOIN query."""
        df = db_manager.run_query("""
            SELECT c.name, COUNT(o.order_id) as order_count
            FROM customers c
            LEFT JOIN orders o ON c.customer_id = o.customer_id
            GROUP BY c.customer_id, c.name
            ORDER BY order_count DESC
        """)
        assert len(df) == 3
        # Customer 1 có 2 orders, phải đứng đầu
        assert df.iloc[0]["order_count"] == 2

    def test_get_schema_description(self, db_manager):
        """Test schema description chứa tên bảng và cột."""
        schema = db_manager.get_schema_description()
        assert "customers" in schema
        assert "orders" in schema
        assert "customer_id" in schema
        assert "total_amount" in schema

    def test_get_table_names(self, db_manager):
        """Test get_table_names trả về đúng danh sách."""
        tables = db_manager.get_table_names()
        assert "customers" in tables
        assert "orders" in tables

    def test_validate_query_valid(self, db_manager):
        """Test validate_query với SQL hợp lệ."""
        is_valid, error = db_manager.validate_query("SELECT * FROM customers")
        assert is_valid is True
        assert error == ""

    def test_validate_query_invalid(self, db_manager):
        """Test validate_query với SQL sai syntax."""
        is_valid, error = db_manager.validate_query("SELECT * FROM nonexistent_table")
        assert is_valid is False
        assert len(error) > 0  # Có thông báo lỗi

    def test_context_manager(self, temp_db):
        """Test dùng DatabaseManager như context manager."""
        with DatabaseManager(temp_db) as db:
            df = db.run_query("SELECT COUNT(*) as cnt FROM customers")
            assert df.iloc[0]["cnt"] == 3
        # Sau khi exit context, connection đã close
        assert db._conn is None


# ============================================================
# TEST: ChartRecommender
# ============================================================

class TestChartRecommender:
    """Tests cho ChartRecommender class."""

    def setup_method(self):
        """Khởi tạo trước mỗi test method."""
        self.recommender = ChartRecommender()

    def test_recommend_bar_for_category_and_number(self):
        """Category + Number → bar chart."""
        df = pd.DataFrame({
            "category": ["Electronics", "Fashion", "Books"],
            "total_revenue": [1_000_000, 500_000, 200_000],
        })
        result = self.recommender.recommend_chart_type(df)
        assert result == "bar"

    def test_recommend_line_for_time_series(self):
        """Time column + Number → line chart."""
        df = pd.DataFrame({
            "order_date": ["2023-01", "2023-02", "2023-03"],
            "total_orders": [50, 75, 60],
        })
        result = self.recommender.recommend_chart_type(df)
        assert result == "line"

    def test_recommend_table_for_single_row(self):
        """Single row → table (không có ý nghĩa khi chart)."""
        df = pd.DataFrame({
            "total_revenue": [5_000_000],
            "total_orders": [150],
        })
        result = self.recommender.recommend_chart_type(df)
        assert result == "table"

    def test_recommend_table_for_empty(self):
        """Empty DataFrame → table."""
        df = pd.DataFrame()
        result = self.recommender.recommend_chart_type(df)
        assert result == "table"

    def test_recommend_histogram_for_only_numbers(self):
        """Chỉ numeric columns → histogram."""
        df = pd.DataFrame({
            "amount": [100, 200, 300, 150, 250, 180, 220],
        })
        result = self.recommender.recommend_chart_type(df)
        assert result == "histogram"

    def test_create_bar_chart_not_none(self):
        """Create bar chart với data hợp lệ → không None."""
        df = pd.DataFrame({
            "region": ["North", "Central", "South"],
            "revenue": [1_000_000, 500_000, 800_000],
        })
        fig = self.recommender.create_chart(df, title="Revenue by Region", chart_type="bar")
        assert fig is not None

    def test_create_chart_empty_returns_none(self):
        """Empty DataFrame → None (không crash)."""
        df = pd.DataFrame()
        fig = self.recommender.create_chart(df)
        assert fig is None

    def test_auto_visualize_helper(self):
        """Test helper function auto_visualize."""
        df = pd.DataFrame({
            "city": ["Hanoi", "HCM", "Da Nang"],
            "customers": [20, 35, 10],
        })
        fig = auto_visualize(df, title="Customers by City")
        assert fig is not None  # Phải tạo được chart


# ============================================================
# CHẠY TESTS
# ============================================================
if __name__ == "__main__":
    # Chạy: python tests/test_core.py
    # Hoặc: pytest tests/ -v --tb=short
    pytest.main([__file__, "-v", "--tb=short"])