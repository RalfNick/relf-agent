"""Only an omitted Agent definition selects the convenience default."""

import asyncio

import pytest

from relf_agent import Agent, AgentSpec, LocalEngine, Runtime, SQLiteStore, ToolRegistry
from relf_agent.errors import ValidationError
from relf_agent.runtime_builder import EchoProvider


@pytest.fixture
def entry_factory(tmp_path, request):
    path = tmp_path / "agent.sqlite"
    loop = asyncio.new_event_loop()
    runtime = None
    agents = []
    if request.param != "standalone":
        runtime = Runtime(
            LocalEngine(
                SQLiteStore(path),
                providers={"default": EchoProvider("definition")},
                tools=ToolRegistry(),
            ),
            owned=True,
        )

    def create(definition):
        if request.param == "standalone":
            agent = Agent(model=EchoProvider("definition"), definition=definition, db_path=path)
        elif request.param == "shared":
            agent = Agent(runtime=runtime, definition=definition)
        else:
            agent = runtime.create_agent(definition)
        agents.append(agent)
        return agent

    try:
        yield path, runtime, create, loop.run_until_complete
    finally:
        try:
            for agent in agents:
                loop.run_until_complete(agent.aclose())
            if runtime is not None:
                loop.run_until_complete(runtime.aclose())
        finally:
            loop.close()


ENTRIES = ["standalone", "shared", "runtime-factory"]


@pytest.mark.parametrize("entry_factory", ENTRIES, indirect=True)
@pytest.mark.parametrize(
    "definition",
    ["", False, 0, {}, [], ()],
    ids=["text", "false", "zero", "object", "list", "tuple"],
)
def test_explicit_invalid_definition_is_not_replaced_with_a_default(entry_factory, definition):
    path, runtime, create, _ = entry_factory
    with pytest.raises(ValidationError):
        create(definition)
    if runtime is None:
        assert not path.exists()
    else:
        assert runtime.engine.store.conn.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
        assert runtime.state == "open"


@pytest.mark.parametrize("entry_factory", ENTRIES, indirect=True)
def test_valid_falsey_definition_keeps_the_explicit_identity(entry_factory):
    _, _, create, run = entry_factory

    class Definition(AgentSpec):
        def __bool__(self):
            return False

    definition = Definition("explicit", "Use exactly this definition")
    agent = create(definition)
    assert agent.harness.definition.name == "explicit"
    assert agent.harness.definition.instructions == "Use exactly this definition"
    result = run(agent.run("q", command_id="once", wait_timeout=1))
    assert result.snapshot.result == {"echo": "q", "label": "definition"}


@pytest.mark.parametrize("entry_factory", ENTRIES, indirect=True)
def test_none_still_selects_the_default_agent(entry_factory):
    _, _, create, run = entry_factory
    agent = create(None)
    assert agent.harness.definition.name == "assistant"
    result = run(agent.run("q", command_id="once", wait_timeout=1))
    assert result.snapshot.state == "succeeded"
