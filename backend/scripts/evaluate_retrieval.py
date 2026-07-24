import uuid

from app.clients.qdrant_client import get_qdrant_client
from app.services.retrieval_service import VectorRetrievalService

QUESTIONS = (
    "Tài liệu này nói về vấn đề gì?",
    "Mục đích của Form W-9 là gì?",
    "Ai cần cung cấp Form W-9?",
    "Phải nhập tên nào ở dòng 1?",
    "Khi nào áp dụng backup withholding?",
    "Làm thế nào để báo cáo hành vi giả mạo IRS?",
    "Tài liệu có hướng dẫn về hợp đồng SAFE không?",
)


def find_test_owner() -> tuple[str, uuid.UUID]:
    qdrant = get_qdrant_client()

    points, _ = qdrant.client.scroll(
        collection_name=qdrant.settings.qdrant_collection_name,
        limit=1,
        with_payload=True,
        with_vectors=False,
    )

    if not points:
        raise RuntimeError("Qdrant collection does not contain any chunks.")

    payload = points[0].payload or {}
    owner_type = payload.get("owner_type")
    owner_id = payload.get("owner_id")

    if owner_type not in {"user", "guest"}:
        raise RuntimeError("Stored owner_type is invalid.")

    if not isinstance(owner_id, str):
        raise RuntimeError("Stored owner_id is invalid.")

    return owner_type, uuid.UUID(owner_id)


def main() -> None:
    owner_type, owner_id = find_test_owner()
    retrieval = VectorRetrievalService()

    print(f"Testing owner: {owner_type} / {owner_id}")

    for question in QUESTIONS:
        if owner_type == "user":
            results = retrieval.retrieve(
                question,
                user_id=owner_id,
                limit=3,
            )
        else:
            results = retrieval.retrieve(
                question,
                guest_session_id=owner_id,
                limit=3,
            )

        print()
        print("=" * 80)
        print(f"QUESTION: {question}")

        for index, result in enumerate(results, start=1):
            compact_text = " ".join(result.text.split())

            print()
            print(
                f"[{index}] score={result.score:.4f} "
                f"page={result.page_number} "
                f"file={result.filename}"
            )
            print(compact_text[:300])


if __name__ == "__main__":
    main()
