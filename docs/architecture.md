# Architecture

## Phong cách kiến trúc

Backend là Modular Monolith: một ứng dụng FastAPI duy nhất với ranh giới module
rõ ràng. Không tách microservices trong MVP.

## Thành phần

```text
React frontend
      |
      v
FastAPI API
      |
      +-- Auth / Guest / Documents / Chat services
      +-- PostgreSQL: user, session và conversation metadata
      +-- Qdrant: document chunk vectors
      +-- External clients: Google, embedding và LLM
```

## Quy tắc layer

- API nhận request, validate và gọi service; không chứa business logic dài.
- Service điều phối use case và transaction.
- Repository chỉ truy cập PostgreSQL.
- Client giao tiếp với hệ thống bên ngoài.
- Schema là Pydantic request/response model.
- Model là SQLAlchemy database model.

## Quy tắc dữ liệu

- Mọi truy vấn tài liệu phải được giới hạn theo `user_id` hoặc
  `guest_session_id` ở backend.
- Qdrant payload phải chứa thông tin ownership và document/page identity.
- Dữ liệu guest có `expires_at` và phải được cleanup sau khi hết hạn.
- Secret chỉ được lấy từ environment, không ghi vào source hoặc log.

## Decision log

Các quyết định quan trọng sẽ được lưu trong `docs/decisions/` dưới dạng ADR.
