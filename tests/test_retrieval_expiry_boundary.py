"""Public retrieval adopts only evidence still live after asynchronous reads."""

import asyncio
import time
from dataclasses import asdict

import pytest

from relf_agent.errors import ValidationError
from relf_agent.retrieval import (
    Document,
    InMemoryKnowledgeStore,
    KnowledgeContext,
    LexicalRetriever,
    RetrievalQuery,
    RetrievalResult,
    RetrievedChunk,
)
from relf_agent.types import Scope, canonical
from relf_agent.vector import InMemoryVectorIndex, VectorEntry, VectorRetriever


class _Embedding:
    identity = {"kind": "expiry-boundary-fixed-embedding", "version": "1"}
    dimensions = 2

    async def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


def _vector_source(monkeypatch, *, expires_at=101.0, advance_to=102.0, first_text="expiring"):
    clock = [100.0]
    monkeypatch.setattr(time, "time", lambda: clock[0])
    scope = Scope()
    source = InMemoryKnowledgeStore()
    source.put(scope, "n", Document("a", first_text), expected_version=0, expires_at=expires_at)
    source.put(scope, "n", Document("b", "permanent"), expected_version=0)
    first, second = (source.chunks(scope, "n", name)[0] for name in ("a", "b"))
    reads = []

    class AsyncSource:
        backend_id = "expiry-boundary-authority"

        def get(self, *args, **kwargs):
            return source.get(*args, **kwargs)

        def chunks(self, *args, **kwargs):
            return source.chunks(*args, **kwargs)

        async def get_chunk(self, scope, namespace, chunk_id):
            reads.append(chunk_id)
            if chunk_id == second.chunk_id:
                await asyncio.sleep(0)
                clock[0] = advance_to
            return source.get_chunk(scope, namespace, chunk_id)

    index = InMemoryVectorIndex(dimensions=2)
    retriever = VectorRetriever(AsyncSource(), index, _Embedding())
    index.upsert(
        scope,
        retriever.index_namespace("n"),
        [
            VectorEntry(first.chunk_id, "a", 1, first.text_digest, [1.0, 0.0]),
            VectorEntry(second.chunk_id, "b", 1, second.text_digest, [0.0, 1.0]),
        ],
    )
    return clock, source, retriever, reads


@pytest.mark.parametrize("advance_to", [101.0, 102.0])
def test_vector_rejects_earlier_selected_chunk_expired_during_later_async_read(
    monkeypatch, advance_to
):
    _, source, retriever, reads = _vector_source(monkeypatch, advance_to=advance_to)
    with pytest.raises(ValidationError, match="expired"):
        asyncio.run(retriever.retrieve(Scope(), "n", RetrievalQuery("query")))
    assert len(reads) == 2  # Final TTL adoption must not issue additional source I/O.
    assert source.get(Scope(), "n", "a") is None


def _custom_retriever(expires_at):
    item = RetrievedChunk("doc", "chunk", 1, "evidence", "", {}, expires_at, Scope(), "n", 1.0)
    result = RetrievalResult((item,), "custom", len(canonical([asdict(item)])))

    class CustomRetriever:
        identity = {"kind": "expiry-boundary-custom", "version": "1"}

        async def retrieve(self, scope, namespace, query):
            await asyncio.sleep(0)
            return result

        async def validate(self, scope, namespace, items):
            raise AssertionError("References must not add source validation I/O")

    return CustomRetriever()


@pytest.mark.parametrize("now", [101.0, 102.0])
def test_context_refuses_expired_completed_result_from_custom_retriever(monkeypatch, now):
    monkeypatch.setattr(time, "time", lambda: now)
    context = KnowledgeContext(_custom_retriever(101.0), namespace="n")
    with pytest.raises(ValidationError, match="expired"):
        asyncio.run(context.references(Scope(), "query"))


@pytest.mark.parametrize("expires_at", [None, 103.0])
def test_vector_keeps_permanent_and_live_sources_without_additional_reads(monkeypatch, expires_at):
    _, _, retriever, reads = _vector_source(monkeypatch, expires_at=expires_at)
    result = asyncio.run(retriever.retrieve(Scope(), "n", RetrievalQuery("query")))
    assert [item.document_id for item in result.items] == ["a", "b"]
    assert len(reads) == 2


@pytest.mark.parametrize("expires_at", [None, 103.0])
def test_context_keeps_permanent_and_live_custom_results(monkeypatch, expires_at):
    monkeypatch.setattr(time, "time", lambda: 102.0)
    context = KnowledgeContext(_custom_retriever(expires_at), namespace="n")
    references = asyncio.run(context.references(Scope(), "query"))
    assert [reference["value"]["document_id"] for reference in references] == ["doc"]


def test_vector_does_not_reject_expired_candidate_excluded_by_character_budget(monkeypatch):
    _, _, retriever, reads = _vector_source(monkeypatch, first_text="large " * 200)
    result = asyncio.run(retriever.retrieve(Scope(), "n", RetrievalQuery("query", max_chars=600)))
    assert [item.document_id for item in result.items] == ["b"]
    assert len(reads) == 2


def test_original_retriever_can_return_newly_indexed_live_source_after_expiry_refusal(monkeypatch):
    _, source, retriever, reads = _vector_source(monkeypatch)

    async def run():
        with pytest.raises(ValidationError, match="expired"):
            await retriever.retrieve(Scope(), "n", RetrievalQuery("query"))
        assert len(reads) == 2
        source.put(
            Scope(), "n", Document("a", "fresh evidence"), expected_version=1, expires_at=103.0
        )
        await retriever.index_document(Scope(), "n", "a")
        reads.clear()
        result = await retriever.retrieve(Scope(), "n", RetrievalQuery("query"))
        assert {(item.document_id, item.version) for item in result.items} == {("a", 2), ("b", 1)}
        assert len(reads) == 2

    asyncio.run(run())


def test_lexical_port_result_cannot_expire_during_await_before_adoption(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(time, "time", lambda: clock[0])
    source = InMemoryKnowledgeStore()
    source.put(Scope(), "n", Document("doc", "evidence"), expected_version=0, expires_at=101.0)

    class AsyncLexicalSource:
        backend_id = "expiry-boundary-lexical-authority"

        async def lexical(self, scope, namespace, query):
            result = source.lexical(scope, namespace, query)
            await asyncio.sleep(0)
            clock[0] = 102.0
            return result

        def get_chunk(self, *args, **kwargs):
            raise AssertionError("Result TTL checks must not add source reads")

    retriever = LexicalRetriever(AsyncLexicalSource())
    with pytest.raises(ValidationError, match="expired"):
        asyncio.run(retriever.retrieve(Scope(), "n", RetrievalQuery("evidence")))
