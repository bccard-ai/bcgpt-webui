"""Unit tests for agent/skill definition import & export."""

from __future__ import annotations

from bcgpt.agent.definitions import (
    AgentDefinition,
    SkillDefinition,
    export_agent,
    export_skill,
    import_agent,
    import_skill,
    parse_frontmatter,
)


def test_agent_json_roundtrip():
    defn = AgentDefinition(
        name="researcher",
        description="finds things",
        autonomy_level="operator",
        system_prompt="You research.",
        tools=["rag_search", "web_search"],
    )
    text = export_agent(defn, fmt="json")
    restored = import_agent(text, fmt="json")
    assert restored.name == "researcher"
    assert restored.autonomy_level == "operator"
    assert restored.tools == ["rag_search", "web_search"]


def test_tools_csv_string_parsed_to_list():
    defn = AgentDefinition.from_dict({"name": "a", "tools": "Read, Write, Bash"})
    assert defn.tools == ["Read", "Write", "Bash"]


def test_bad_autonomy_defaults_to_assistant():
    defn = AgentDefinition.from_dict({"name": "a", "autonomy_level": "bogus"})
    assert defn.autonomy_level == "assistant"


def test_agent_knowledge_dict_roundtrip():
    """Persisted meta.knowledge is a list of dicts; round-trip must preserve shape."""
    knowledge = [
        {"id": "kb-123", "type": "collection", "source": "knowledge", "name": "Specs"}
    ]
    defn = AgentDefinition.from_dict({"name": "a", "knowledge": knowledge})
    assert defn.knowledge == knowledge
    # export to JSON and re-import → stable (dict items not stringified)
    text = export_agent(defn, fmt="json")
    restored = import_agent(text, fmt="json")
    assert restored.knowledge == knowledge


def test_agent_knowledge_legacy_strings_preserved():
    """Legacy bare collection-name strings must also round-trip unchanged."""
    defn = AgentDefinition.from_dict({"name": "a", "knowledge": ["col-a", "col-b"]})
    assert defn.knowledge == ["col-a", "col-b"]


def test_parse_frontmatter_splits_meta_and_body():
    text = "---\nname: x\ndescription: y\n---\n\n# Body here\nmore"
    meta, body = parse_frontmatter(text)
    assert meta["name"] == "x" and meta["description"] == "y"
    assert body.startswith("# Body here")


def test_parse_frontmatter_no_frontmatter():
    meta, body = parse_frontmatter("just a body")
    assert meta == {}
    assert body == "just a body"


def test_agent_markdown_roundtrip():
    md = (
        "---\n"
        "name: fullstack\n"
        "description: end to end\n"
        "autonomy_level: operator\n"
        "tools: rag_search, web_search\n"
        "---\n\n"
        "# Fullstack\nYou build features."
    )
    defn = import_agent(md, fmt="md")
    assert defn.name == "fullstack"
    assert defn.autonomy_level == "operator"
    assert defn.tools == ["rag_search", "web_search"]
    assert "You build features." in defn.system_prompt

    # export back to markdown and re-import → stable
    out = export_agent(defn, fmt="md")
    redefn = import_agent(out, fmt="md")
    assert redefn.name == "fullstack"
    assert redefn.autonomy_level == "operator"
    assert redefn.tools == ["rag_search", "web_search"]


def test_skill_markdown_roundtrip():
    md = (
        "---\n"
        "name: summarize\n"
        "description: condense text\n"
        "tools: rag_search\n"
        "---\n\n"
        "Summarize the following: {input}"
    )
    skill = import_skill(md, fmt="md")
    assert skill.name == "summarize"
    assert skill.tools == ["rag_search"]
    assert "{input}" in skill.prompt_template

    out = export_skill(skill, fmt="md")
    re_skill = import_skill(out, fmt="md")
    assert re_skill.name == "summarize"
    assert re_skill.prompt_template.strip().endswith("{input}")


def test_skill_json_roundtrip():
    skill = SkillDefinition(name="s", prompt_template="t", tools=["a"])
    text = export_skill(skill, fmt="json")
    restored = import_skill(text, fmt="json")
    assert restored.name == "s" and restored.tools == ["a"]
