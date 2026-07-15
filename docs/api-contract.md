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

- `POST /documents/{document_id}/ask`
- `GET /conversations`
- `GET /conversations/{conversation_id}`

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
