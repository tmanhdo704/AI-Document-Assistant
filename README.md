# DocAlly

Ứng dụng hỏi đáp tài liệu PDF sử dụng FastAPI, React, PostgreSQL và kiến trúc
Modular Monolith. Đây là bộ khung ban đầu; các nghiệp vụ authentication, guest,
document processing và RAG sẽ được bổ sung theo kế hoạch 4 tuần.

## Cấu trúc chính

```text
backend/    FastAPI API và business modules
frontend/   React + TypeScript + Vite
docs/       Requirements, architecture và API contract
storage/    Dữ liệu runtime cục bộ, không commit lên Git
scripts/    Lệnh hỗ trợ development
```

Luồng phụ thuộc backend:

```text
API -> Service -> Repository -> PostgreSQL
              -> Client -> Google / Qdrant / LLM
```

## Khởi động bằng Docker

1. Sao chép `.env.example` thành `.env` và thay các giá trị mẫu khi cần.
2. Chạy:

   ```bash
   docker compose up --build
   ```

3. Truy cập:

   - Frontend: `http://localhost:5173`
   - Backend health check: `http://localhost:8000/api/v1/health`
   - OpenAPI: `http://localhost:8000/docs`

## Chạy backend cục bộ

```bash
cd backend
python -m venv .venv
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
```

## Chạy frontend cục bộ

```bash
cd frontend
npm install
npm run dev
```

## Trạng thái scaffold

- Health check đã hoạt động.
- Các router nghiệp vụ mới chỉ là ranh giới module, chưa có logic.
- PostgreSQL đã được khai báo trong Docker Compose.
- Qdrant và pipeline RAG sẽ được bổ sung ở tuần 3.
