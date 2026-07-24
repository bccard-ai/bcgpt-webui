"""Unit tests for corpus-collection naming (P1.0)."""

from __future__ import annotations

from types import SimpleNamespace

from bcgpt.retrieval.vector.corpus import (
    DEFAULT_WORKSPACE_ID,
    PAYLOAD_INDEX_FIELDS,
    corpus_collection_name,
)


def test_name_is_deterministic():
    a = corpus_collection_name(engine="openai", model="text-embedding-3-small")
    b = corpus_collection_name(engine="openai", model="text-embedding-3-small")
    assert a == b


def test_name_format():
    name = corpus_collection_name(engine="openai", model="text-embedding-3-small")
    assert name.startswith("corpus_")
    suffix = name.split("_", 1)[1]
    # 16-char sha1 truncation, hex only
    assert len(suffix) == 16
    int(suffix, 16)  # parses as hex


def test_different_model_yields_different_name():
    a = corpus_collection_name(engine="openai", model="text-embedding-3-small")
    b = corpus_collection_name(engine="openai", model="text-embedding-3-large")
    assert a != b


def test_different_engine_yields_different_name():
    a = corpus_collection_name(engine="openai", model="m")
    b = corpus_collection_name(engine="ollama", model="m")
    assert a != b


def test_prefix_affects_name():
    a = corpus_collection_name(engine="openai", model="m", prefix="query:")
    b = corpus_collection_name(engine="openai", model="m")
    assert a != b


def test_accepts_embedding_config_dict():
    via_dict = corpus_collection_name({"engine": "openai", "model": "m"})
    via_kwargs = corpus_collection_name(engine="openai", model="m")
    assert via_dict == via_kwargs


def test_normalizes_persistent_config_values():
    # PersistentConfig-like objects expose .value; the helper should use it.
    cfg = SimpleNamespace(value="openai")
    name_from_obj = corpus_collection_name(engine=cfg, model="m")
    name_from_str = corpus_collection_name(engine="openai", model="m")
    assert name_from_obj == name_from_str


def test_payload_index_fields_present():
    # the corpus adapter indexes these for filtered ANN
    assert "knowledge_id" in PAYLOAD_INDEX_FIELDS
    assert "file_id" in PAYLOAD_INDEX_FIELDS
    assert "workspace_id" in PAYLOAD_INDEX_FIELDS
    assert "embedding_config" in PAYLOAD_INDEX_FIELDS


def test_default_workspace_id():
    assert DEFAULT_WORKSPACE_ID == "default"
