from uuid import uuid4

from app.retrieval.chunking import split_markdown


def test_chunk_drafts_have_stable_cross_store_ids() -> None:
    document_id, version_id = uuid4(), uuid4()
    drafts = split_markdown("# 政策\n签收后七天内可以退货。", document_id, version_id)

    assert drafts
    assert all(draft.document_id == document_id for draft in drafts)
    assert all(draft.version_id == version_id for draft in drafts)
    assert len({draft.chunk_id for draft in drafts}) == len(drafts)
