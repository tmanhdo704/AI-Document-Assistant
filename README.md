# DocAlly

Ứng dụng hỏi đáp tài liệu PDF sử dụng FastAPI, React, PostgreSQL và kiến trúc
Modular Monolith. Luồng MVP hiện hỗ trợ authentication, guest session, upload
và trích xuất PDF, truy xuất đoạn liên quan, gọi LLM và citation theo trang.

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
   Để bật chức năng trả lời, tạo API key trong Google AI Studio và cấu hình:

   ```env
   GEMINI_API_KEY=<api-key-tu-google-ai-studio>
   GEMINI_MODEL=gemini-2.5-pro
   ```

   Không đưa `GEMINI_API_KEY` vào frontend hoặc commit file `.env`.
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

## Trạng thái hiện tại

- Email/password, Google login, JWT và guest session đã hoạt động.
- PDF được kiểm tra, lưu cục bộ và trích xuất text theo trang.
- `POST /ask` tìm kiếm trên toàn bộ tài liệu của phiên hiện tại, trả lời dựa
  trên các đoạn liên quan và kèm citation tên file, số trang.
- Backend kiểm tra quyền sở hữu tài liệu và giới hạn guest tối đa 3 câu hỏi.
- Retrieval hiện dùng xếp hạng từ khóa cục bộ; embedding và Qdrant là bước
  nâng cấp tiếp theo.
