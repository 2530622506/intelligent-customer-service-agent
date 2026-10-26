from uuid import uuid4

from app.retrieval.chunking import split_markdown


def test_markdown_chunks_keep_parent_source_links() -> None:
    chunks = split_markdown("# 退换货\n签收后七天内可以退货。", uuid4(), uuid4(), max_chars=10)

    assert chunks
    parent = next(chunk for chunk in chunks if chunk.parent_chunk_id is None)
    children = [chunk for chunk in chunks if chunk.parent_chunk_id == parent.chunk_id]
    assert parent.section_path == "退换货"
    assert children
    assert all(child.chunking_version == "markdown-parent-child-v1" for child in children)
