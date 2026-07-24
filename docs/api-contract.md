# API Contract

Base path: `/api/v1`

## Đã có trong scaffold

### `GET /health`

Response `200`:

```json
{
  "status": "ok",
  "service": "DocAlly API"
}
```

## Dự kiến triển khai

### Authentication

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/google`
- `GET /auth/me`

### Guest

- `POST /guest/session`
- `GET /guest/usage`

### Documents

- `POST /documents`
- `GET /documents`
- `GET /documents/{document_id}`
- `DELETE /documents/{document_id}`

### Chat

- `POST /ask`
- `GET /conversations`
- `GET /conversations/{conversation_id}`

Request:

```json
{
  "question": "Chính sách nghỉ phép là gì?"
}
```

Response `200`:

```json
{
  "answer": "Nhân viên có 12 ngày nghỉ phép mỗi năm [1].",
  "citations": [
    {
      "index": 1,
      "document_id": "00000000-0000-0000-0000-000000000000",
      "filename": "handbook.pdf",
      "page_number": 3,
      "excerpt": "Nhân viên có 12 ngày nghỉ phép mỗi năm."
    }
  ],
  "questions_remaining": 2
}
```

Backend tìm kiếm trên toàn bộ tài liệu thuộc user hoặc guest hiện tại trước
khi gọi model. `questions_remaining` là `null` với người dùng đã đăng nhập.
Backend gọi Gemini `generateContent` và được cấu hình bằng
`GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_BASE_URL`.

## Error envelope

```json
{
  "error": {
    "code": "STABLE_ERROR_CODE",
    "message": "Human-readable message",
    "details": null,
    "request_id": null
  }
}
```
