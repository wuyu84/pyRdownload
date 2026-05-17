# ============================================
# Stage 1: 构建前端
# ============================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ============================================
# Stage 2: 运行后端
# ============================================
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（SQLite 等 Python 标准库已自带）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ ./backend/

# 复制前端构建产物
COPY --from=frontend-builder /app/frontend/dist/ ./frontend/dist/

# 创建仓库目录
RUN mkdir -p /var/lib/pkgdl/repository/{python,r,runtimes,exports}

# 暴露端口
EXPOSE 3579

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import http.client; conn=http.client.HTTPConnection('localhost:3579'); conn.request('GET','/api/health'); resp=conn.getresponse(); exit(0 if resp.status==200 else 1)"

# 启动
CMD ["python3", "-m", "backend.main"]
