# Requirements

## Mục tiêu

Xây dựng ứng dụng web cho phép người dùng tải PDF và đặt câu hỏi dựa trên nội
dung tài liệu, kèm citation theo tên tài liệu và số trang.

## Nhóm người dùng

### Guest

- Không cần đăng nhập.
- Tối đa 1 PDF, 10 MB, 30 trang và 3 câu hỏi trong phiên 30 phút.
- Không lưu tài liệu hoặc lịch sử lâu dài.

### Logged-in user

- Đăng nhập bằng email/password hoặc Google.
- Lưu danh sách tài liệu và lịch sử hội thoại.
- Tối đa 10 tài liệu, 20 MB và 200 trang mỗi file, 100 câu hỏi mỗi ngày.

## Phạm vi MVP

- Authentication và authorization.
- Guest session và usage limits được kiểm tra ở backend.
- Upload và trích xuất PDF có text theo từng trang.
- Chunking, embedding, Qdrant retrieval và LLM response.
- Citation theo tài liệu và số trang.
- Docker Compose, CI, deployment và tài liệu sử dụng.

## Ngoài phạm vi 4 tuần

- Microservices, Kubernetes, fine-tuning, mobile app và payment.
- OCR, streaming, Redis và multi-document chat chỉ làm khi còn thời gian.

## Acceptance criteria cấp sản phẩm

- Guest bị chặn ở câu hỏi thứ tư và không có lịch sử lâu dài.
- User A không thể đọc hoặc truy vấn dữ liệu của User B.
- Xóa tài liệu đồng thời xóa metadata, file và vector liên quan.
- Câu trả lời không đủ bằng chứng phải trả no-answer fallback.
- Toàn bộ luồng chính chạy được bằng Docker và có live demo.
