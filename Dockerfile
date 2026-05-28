# Dockerfile
# -----------
# Multi-stage build không cần thiết ở đây vì Python app không compile
# Dùng Python 3.11 slim (nhỏ hơn full image, đủ cho project này)

FROM python:3.11-slim

# Set working directory trong container
WORKDIR /app

# Tại sao copy requirements trước, rồi mới copy code?
# → Docker layer caching: nếu code thay đổi nhưng requirements không đổi,
#   Docker không cần reinstall packages → build nhanh hơn
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ project vào container
COPY . .

# Tạo database với sample data khi build image
# (Alternative: tạo lúc container start, nhưng build-time sạch hơn)
RUN python data/seed_database.py

# Expose Streamlit port
EXPOSE 8501

# Streamlit config để chạy trong Docker
# --server.address=0.0.0.0: listen trên tất cả interfaces (không chỉ localhost)
# --server.headless=true: không mở browser tự động
# --server.enableCORS=false: tắt CORS check (OK trong container)
CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true", \
     "--server.enableCORS=false"]