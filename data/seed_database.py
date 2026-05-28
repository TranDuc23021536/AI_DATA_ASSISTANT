"""
seed_database.py
----------------
Script tạo database SQLite mẫu với dữ liệu e-commerce thực tế.
Chạy một lần để khởi tạo data trước khi dùng app.

Tại sao dùng SQLite?
- File-based, không cần cài server (như PostgreSQL/MySQL)
- Hoàn hảo cho demo/prototype
- LangChain có SQLDatabase connector built-in cho SQLite
"""

import sqlite3
import random
from datetime import datetime, timedelta
import os

# Đường dẫn tới file database
DB_PATH = os.path.join(os.path.dirname(__file__), "ecommerce.db")


def create_tables(conn: sqlite3.Connection) -> None:
    """
    Tạo schema cho 4 bảng chính.
    Dùng IF NOT EXISTS để script có thể chạy lại mà không lỗi.
    """
    cursor = conn.cursor()

    # Bảng customers: thông tin khách hàng
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            city          TEXT    NOT NULL,
            region        TEXT    NOT NULL,
            signup_date   TEXT    NOT NULL   -- lưu dạng ISO string: YYYY-MM-DD
        )
    """)

    # Bảng products: danh mục sản phẩm
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            category      TEXT    NOT NULL,
            price         REAL    NOT NULL,
            stock         INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Bảng orders: đơn hàng (1 customer có nhiều orders)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id   INTEGER NOT NULL,
            order_date    TEXT    NOT NULL,
            status        TEXT    NOT NULL,  -- pending / shipped / delivered / cancelled
            total_amount  REAL    NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        )
    """)

    # Bảng order_items: chi tiết từng sản phẩm trong đơn hàng
    # Đây là bảng "junction" giữa orders và products (quan hệ many-to-many)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            item_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id      INTEGER NOT NULL,
            product_id    INTEGER NOT NULL,
            quantity      INTEGER NOT NULL,
            unit_price    REAL    NOT NULL,  -- giá tại thời điểm mua (có thể khác price hiện tại)
            FOREIGN KEY (order_id)   REFERENCES orders(order_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        )
    """)

    conn.commit()
    print("✅ Tables created successfully.")


def seed_customers(conn: sqlite3.Connection) -> list[int]:
    """
    Insert 50 khách hàng mẫu, trả về list customer_id để dùng sau.
    """
    cursor = conn.cursor()

    # Check xem đã có data chưa (tránh insert duplicate khi chạy lại)
    cursor.execute("SELECT COUNT(*) FROM customers")
    if cursor.fetchone()[0] > 0:
        print("⚠️  Customers already seeded, skipping.")
        cursor.execute("SELECT customer_id FROM customers")
        return [row[0] for row in cursor.fetchall()]

    cities_regions = [
        ("Hanoi", "North"), ("Hai Phong", "North"), ("Nam Dinh", "North"),
        ("Da Nang", "Central"), ("Hue", "Central"), ("Hoi An", "Central"),
        ("Ho Chi Minh", "South"), ("Can Tho", "South"), ("Vung Tau", "South"),
        ("Bien Hoa", "South"),
    ]

    names = [
        "Nguyen Van An", "Tran Thi Bich", "Le Hoang Cuong", "Pham Minh Duc",
        "Hoang Thi Em", "Vu Van Phuc", "Do Thi Giang", "Bui Quoc Hung",
        "Ngo Thi Lan", "Dinh Van Minh", "Ly Thi Ngoc", "Truong Van Oanh",
        "Dang Thi Phuong", "Nguyen Quang Son", "Tran Thi Thu", "Le Van Uyen",
        "Pham Thi Viet", "Hoang Van Xuan", "Vu Thi Yen", "Do Quoc Zung",
        "Bui Thi Anh", "Ngo Van Binh", "Dinh Thi Chi", "Ly Van Dat",
        "Truong Thi Eo", "Dang Van Phong", "Nguyen Thi Gai", "Tran Van Hoa",
        "Le Thi Inh", "Pham Van Khoa", "Hoang Thi Lan", "Vu Van Mai",
        "Do Thi Ngai", "Bui Van Oi", "Ngo Thi Phai", "Dinh Van Quyen",
        "Ly Thi Ren", "Truong Van Son", "Dang Thi Tuan", "Nguyen Van Uoc",
        "Tran Thi Van", "Le Van Xoa", "Pham Thi Yen", "Hoang Van Zoan",
        "Vu Thi Ac", "Do Van Bong", "Bui Thi Cam", "Ngo Van Dan",
        "Dinh Thi Eng", "Ly Van Phuc",
    ]

    customers = []
    base_date = datetime(2022, 1, 1)

    for i, name in enumerate(names):
        city, region = random.choice(cities_regions)
        # Email: lấy tên, bỏ dấu cách, lower case
        email_name = name.lower().replace(" ", ".").replace("đ", "d")
        email = f"{email_name}{i+1}@gmail.com"
        signup_date = (base_date + timedelta(days=random.randint(0, 700))).strftime("%Y-%m-%d")

        customers.append((name, email, city, region, signup_date))

    cursor.executemany(
        "INSERT INTO customers (name, email, city, region, signup_date) VALUES (?, ?, ?, ?, ?)",
        customers
    )
    conn.commit()

    cursor.execute("SELECT customer_id FROM customers")
    ids = [row[0] for row in cursor.fetchall()]
    print(f"✅ Seeded {len(ids)} customers.")
    return ids


def seed_products(conn: sqlite3.Connection) -> list[tuple]:
    """
    Insert sản phẩm mẫu, trả về list (product_id, price) để tính order_items.
    """
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] > 0:
        print("⚠️  Products already seeded, skipping.")
        cursor.execute("SELECT product_id, price FROM products")
        return cursor.fetchall()

    products = [
        # (name, category, price, stock)
        ("iPhone 15 Pro", "Electronics", 28_990_000, 50),
        ("Samsung Galaxy S24", "Electronics", 22_990_000, 80),
        ("MacBook Air M3", "Electronics", 32_990_000, 30),
        ("Dell XPS 15", "Electronics", 38_990_000, 20),
        ("AirPods Pro", "Electronics", 6_990_000, 100),
        ("Sony WH-1000XM5", "Electronics", 8_490_000, 60),
        ("iPad Air", "Electronics", 16_990_000, 45),
        ("Xiaomi 14", "Electronics", 14_990_000, 70),

        ("Nike Air Max 270", "Fashion", 3_290_000, 200),
        ("Adidas Ultraboost", "Fashion", 3_890_000, 150),
        ("Levis 501 Jeans", "Fashion", 1_590_000, 300),
        ("Uniqlo Ultra Light Down", "Fashion", 990_000, 500),
        ("Converse Chuck Taylor", "Fashion", 1_290_000, 250),
        ("The North Face Jacket", "Fashion", 4_290_000, 80),

        ("The Alchemist", "Books", 89_000, 1000),
        ("Atomic Habits", "Books", 105_000, 800),
        ("Deep Work", "Books", 98_000, 600),
        ("Clean Code", "Books", 145_000, 400),
        ("Dune", "Books", 115_000, 500),

        ("Instant Pot Duo", "Home & Kitchen", 2_490_000, 120),
        ("Dyson V15 Vacuum", "Home & Kitchen", 12_990_000, 40),
        ("IKEA BILLY Bookcase", "Home & Kitchen", 1_490_000, 200),
        ("Philips Air Fryer", "Home & Kitchen", 1_990_000, 90),

        ("Whey Protein 2kg", "Sports", 890_000, 300),
        ("Yoga Mat Premium", "Sports", 490_000, 400),
        ("Resistance Bands Set", "Sports", 299_000, 500),
        ("Garmin Forerunner 255", "Sports", 8_990_000, 60),
    ]

    cursor.executemany(
        "INSERT INTO products (name, category, price, stock) VALUES (?, ?, ?, ?)",
        products
    )
    conn.commit()

    cursor.execute("SELECT product_id, price FROM products")
    result = cursor.fetchall()
    print(f"✅ Seeded {len(result)} products.")
    return result


def seed_orders(conn: sqlite3.Connection, customer_ids: list[int], products: list[tuple]) -> None:
    """
    Tạo 300 orders với order_items thực tế.
    Mỗi order có 1-4 sản phẩm ngẫu nhiên.
    """
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM orders")
    if cursor.fetchone()[0] > 0:
        print("⚠️  Orders already seeded, skipping.")
        return

    statuses = ["pending", "shipped", "delivered", "delivered", "delivered", "cancelled"]
    # "delivered" xuất hiện 3 lần → xác suất cao hơn (realistic hơn)

    base_date = datetime(2023, 1, 1)

    orders_data = []
    items_data = []

    for _ in range(300):
        customer_id = random.choice(customer_ids)
        order_date = (base_date + timedelta(days=random.randint(0, 500))).strftime("%Y-%m-%d")
        status = random.choice(statuses)

        # Chọn 1-4 sản phẩm cho đơn hàng này
        num_items = random.randint(1, 4)
        chosen_products = random.sample(products, min(num_items, len(products)))

        total_amount = 0.0
        order_items_temp = []
        for product_id, price in chosen_products:
            quantity = random.randint(1, 3)
            subtotal = quantity * price
            total_amount += subtotal
            order_items_temp.append((product_id, quantity, price))

        orders_data.append((customer_id, order_date, status, round(total_amount, 2)))

    # Insert orders và lấy lastrowid
    for i, order in enumerate(orders_data):
        cursor.execute(
            "INSERT INTO orders (customer_id, order_date, status, total_amount) VALUES (?, ?, ?, ?)",
            order
        )
        order_id = cursor.lastrowid

        # Insert items cho order này
        # Tái tạo items vì đã mất trong loop trên → cách đơn giản: redo
        num_items = random.randint(1, 4)
        chosen = random.sample(products, min(num_items, len(products)))
        for product_id, price in chosen:
            quantity = random.randint(1, 3)
            cursor.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                (order_id, product_id, quantity, price)
            )

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM orders")
    cursor2 = conn.cursor()
    cursor2.execute("SELECT COUNT(*) FROM order_items")
    print(f"✅ Seeded {cursor.fetchone()[0]} orders and {cursor2.fetchone()[0]} order items.")


def main():
    print(f"📂 Database path: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    try:
        create_tables(conn)
        customer_ids = seed_customers(conn)
        products = seed_products(conn)
        seed_orders(conn, customer_ids, products)
        print("\n🎉 Database seeded successfully! Ready to use.")
    finally:
        conn.close()


if __name__ == "__main__":
    # Nếu muốn reset và seed lại từ đầu, xóa file db trước:
    # os.remove(DB_PATH)
    main()