"""Evaluate conservative grounded answers against live services."""

from app.clients.llm_client import LLMClient
from app.services.retrieval_service import VectorRetrievalService
from scripts.evaluate_retrieval import find_test_owner

QUESTIONS = (
    "Tài liệu này nói về vấn đề gì?",
    "Khi nào áp dụng backup withholding?",
    "Tài liệu có hướng dẫn về hợp đồng SAFE không?",
)


def main() -> None:
    owner_type, owner_id = find_test_owner()
    retrieval = VectorRetrievalService()
    llm = LLMClient()

    for question in QUESTIONS:
        if owner_type == "user":
            sources = retrieval.retrieve(
                question,
                user_id=owner_id,
            )
        else:
            sources = retrieval.retrieve(
                question,
                guest_session_id=owner_id,
            )

        answer = llm.answer(
            question=question,
            sources=sources,
        )

        print()
        print("=" * 80)
        print(f"QUESTION: {question}")
        print(f"ANSWERABLE: {answer.answerable}")
        print(f"CITED SOURCES: {answer.cited_indexes}")
        print(f"ANSWER: {answer.text}")


if __name__ == "__main__":
    main()
