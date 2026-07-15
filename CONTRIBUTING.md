# Contributing

## Branch naming

- `feature/<short-name>` cho tính năng mới.
- `fix/<short-name>` cho sửa lỗi.
- `docs/<short-name>` cho thay đổi tài liệu.

## Commit convention

```text
feat: add local user registration
fix: prevent guest from uploading second document
test: add authentication integration tests
docs: update API contract
chore: configure project tooling
```

## Definition of Done

- Đúng acceptance criteria.
- Có validation và error handling phù hợp.
- Có test ở cấp độ cần thiết.
- Lint, test và build thành công.
- Không chứa secret hoặc dữ liệu người dùng.
- Cập nhật API contract và migration khi có thay đổi tương ứng.
