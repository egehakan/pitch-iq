# Research: LangGraph — CORE API (current state)

> Cited synthesis from the Pitch IQ research workflow (run 2026-06-30). Versions/URLs are primary-source-verified; see open questions for unresolved items.

**Executive summary:** As of 2026-06-30, the current stable `langgraph` is 1.2.7 (released 2026-06-30), built on the LangChain 1.x line: it requires langchain-core <2,>=1.4.7 (latest core is 1.4.8), and pairs with langchain 1.3.11 and langchain-openai 1.3.3 (both 2026-06-22). The StateGraph authoring API is unchanged in shape: state is a TypedDict (or Pydantic BaseModel) with reducers attached via typing.Annotated (e.g. messages: Annotated[list, add_messages]), wired with add_node/add_edge/add_conditional_edges between START and END, then .compile(). The biggest current-state shift is agents and streaming. The langgraph.prebuilt create_react_agent is now officially deprecated in favor of langchain.agents.create_agent (same engine, adds a middleware system; note prompt= became system_prompt=). For streaming, LangGraph 1.x introduces graph.stream_events(input, version="v3"), a run-stream object with typed projections (.messages, .values, .output, .updates, .custom, .subgraphs, .interrupts) that is now the recommended in-process model for token-by-token UI; the lower-level graph.stream(stream_mode=..., version="v2") still exists with modes values/updates/messages/custom/debug. Subgraphs compose either by adding a compiled graph directly as a node (shared state keys) or by wrapping subgraph.invoke() in a function node (different schemas). The documented workflow patterns (prompt chaining, routing, parallelization, orchestrator-worker, evaluator-optimizer) use fan-out edges and the Send API (langgraph.types.Send) for dynamic parallel fan-out / map-reduce.

---

## LangGraph — Core API, Current State (2026-06-30)

### Versions and the dependency chain

The current stable `langgraph` is **1.2.7**, uploaded **2026-06-30** ([PyPI JSON](https://pypi.org/pypi/langgraph/json)). LangGraph is now firmly on the LangChain 1.x line. Its declared constraints are `langchain-core<2,>=1.4.7`, `langgraph-checkpoint<5.0.0,>=4.1.0`, `langgraph-prebuilt<1.2.0,>=1.1.0`, `langgraph-sdk<0.5.0,>=0.4.2`, `pydantic>=2.7.4`, Python `>=3.10`.

| Package | Version | Released | Source |
|---|---|---|---|
| langgraph | **1.2.7** | 2026-06-30 | [pypi](https://pypi.org/pypi/langgraph/json) |
| langchain | **1.3.11** | 2026-06-22 | [pypi](https://pypi.org/pypi/langchain/json) |
| langchain-openai | **1.3.3** | 2026-06-22 | [pypi](https://pypi.org/pypi/langchain-openai/json) |
| langchain-core | **1.4.8** | 2026-06-18 | [pypi](https://pypi.org/pypi/langchain-core/json) |
| langgraph-prebuilt | **1.1.0** | 2026-05-12 | [pypi](https://pypi.org/pypi/langgraph-prebuilt/json) |
| langgraph-checkpoint | **4.1.1** | 2026-05-22 | [pypi](https://pypi.org/pypi/langgraph-checkpoint/json) |
| langgraph-sdk | **0.4.2** | 2026-06-01 | [pypi](https://pypi.org/pypi/langgraph-sdk/json) |

`langchain` 1.3.11 and `langchain-openai` 1.3.3 both require `langchain-core<2.0.0,>=1.4.7`; `langchain-openai` additionally requires `openai<3.0.0,>=2.26.0`. These all satisfy langgraph 1.2.7's pins, so the four-package set installs cleanly together. (Dates verified directly from each package's PyPI JSON `upload_time_iso_8601`.)

### StateGraph: declaring state, nodes, edges

State is a schema class. The dominant form is a `TypedDict` with reducers attached through `typing.Annotated`; a Pydantic `BaseModel` is also supported and adds runtime input validation ([Graph API docs](https://docs.langchain.com/oss/python/langgraph/use-graph-api)).

```python
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain.messages import AnyMessage

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]   # append+merge reducer
    aggregate: Annotated[list[str], __import__("operator").add]  # append-only fan-in
    foo: str   # no reducer -> last-write-wins (overwrite)
```

Key points: a bare key overwrites on each write; an `Annotated[..., reducer]` key merges via the reducer. `add_messages` is the messages reducer (and `MessagesState` is the prebuilt convenience class). For append-only accumulation across parallel branches use `operator.add`. A `langgraph.types.Overwrite(...)` wrapper bypasses a reducer to force-replace a value.

Graph construction is the familiar builder, with chainable methods:

```python
builder = StateGraph(State)                 # optionally input_schema=, output_schema=, context_schema=
builder.add_node("llm", llm_node)           # node = fn(state[, runtime]) -> partial state
builder.add_edge(START, "llm")              # START/END from langgraph.graph
builder.add_conditional_edges("llm", route, ["tools", END])  # route(state) -> next node name(s)
builder.add_edge("tools", "llm")
graph = builder.compile(checkpointer=..., store=...)   # validates; returns a Pregel runnable
```

`add_conditional_edges(source, fn, mapping)` accepts either a list of allowed targets or a dict mapping the router's return values to node names. Nodes can also return a `Command(update=..., goto=...)` to update state and route in one step, including `graph=Command.PARENT` to jump into a parent graph from a subgraph. `add_node(..., defer=True)` delays a node until all upstream branches finish (useful for fan-in). Compiled graphs run via `.invoke()`, `.stream()`, `.stream_events()` and async variants.

### Prebuilt agent: create_react_agent is deprecated → create_agent

`create_react_agent` still lives at `from langgraph.prebuilt import create_react_agent` (params include `model`, `tools`, `prompt`, `state_schema`, `checkpointer`, `interrupt_before/after`, `debug`, `version`, `name`), but it is **officially deprecated** ([reference page](https://reference.langchain.com/python/langgraph.prebuilt/chat_agent_executor/create_react_agent), [v1 migration guide](https://docs.langchain.com/oss/python/migrate/langgraph-v1)). The replacement is **`langchain.agents.create_agent`**, which runs on the same LangGraph engine and adds a middleware system:

```python
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware

agent = create_agent(
    model="gpt-5.4-mini",            # or a chat model instance / init_chat_model(...)
    tools=[my_tool],                 # @tool fns or ToolNode; bound automatically
    system_prompt="You are ...",     # NOTE: renamed from prompt= in create_react_agent
    middleware=[ToolCallLimitMiddleware(tool_name="my_tool", run_limit=1)],
    checkpointer=MemorySaver(),      # or True to inherit parent checkpointer
)
agent.invoke({"messages": [{"role": "user", "content": "..."}]})
```

Migration is essentially an import swap plus `prompt=` → `system_prompt=`. Tools are passed as a list and bound for you; the agent returns/streams a `messages` state exactly like a compiled graph, so it slots into subgraphs and the streaming APIs below. Guidance from the field: stay on `create_agent` until you need to intercept state mid-run, add human review, or build multi-agent handoffs, then drop to an explicit `StateGraph` ([migration discussion](https://github.com/langchain-ai/langgraph/issues/6404)).

### Streaming: stream_events(version="v3") is now the recommended in-process model

LangGraph 1.x elevates **`graph.stream_events(input, version="v3")`** (and `astream_events`) to the recommended in-process streaming model ([event-streaming docs](https://docs.langchain.com/oss/python/langgraph/event-streaming)). It returns a run-stream object with typed, concurrently-consumable projections instead of raw tuples:

```python
stream = graph.stream_events({"messages": [...]}, version="v3")
for message in stream.messages:        # chat-model token deltas
    for token in message.text:
        print(token, end="", flush=True)
final_state = stream.output            # final value
# other projections: stream.values, stream.updates, stream.custom, stream.subgraphs, stream.interrupts
```

This is the path to use for **token-by-token UI streaming** today. Under it sits the lower-level **`graph.stream(input, stream_mode=..., version="v2")`** with modes `"values"` (full state after each step), `"updates"` (per-node changed keys), `"messages"` (LLM token chunk + metadata), `"custom"` (data emitted via `get_stream_writer()`), and `"debug"`. With `version="v2"` each chunk is a unified `StreamPart` dict keyed by `chunk["type"]` / `chunk["data"]`; multiple modes can be requested with a list. (`version="v1"` is the legacy format where multi-mode yields `(mode, chunk)` tuples.) For custom progress events, call `get_stream_writer()` inside a node/tool and read them via the `custom` mode or `stream.custom`.

### Subgraphs

Two documented composition patterns ([subgraph docs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)):

1. **Shared state keys** — add the compiled subgraph directly as a node; it reads/writes the parent's channels automatically:
```python
subgraph = sub_builder.compile()
builder.add_node("node_1", subgraph)
```
2. **Different schemas** — wrap `subgraph.invoke()` in a function node and transform state in/out:
```python
def node_2(state: ParentState):
    resp = subgraph.invoke({"bar": state["foo"]})   # map parent -> sub
    return {"foo": resp["bar"]}                      # map sub -> parent
```
Subgraphs inherit the parent checkpointer for per-invocation persistence; `compile(checkpointer=False)` makes one stateless, `checkpointer=True` (on `create_agent`) opts into per-thread persistence. `stream.subgraphs` (or filtering raw events by `event["params"]["namespace"]`) surfaces nested runs.

### Workflow building blocks and the Send API

LangGraph documents the canonical workflow patterns (mirroring Anthropic's "effective agents" taxonomy) on the [workflows-and-agents page](https://docs.langchain.com/oss/python/langgraph/workflows-agents): **prompt chaining** (sequential `add_edge`s), **routing** (`add_conditional_edges`), **parallelization** (fan-out: multiple edges from one node into a shared `operator.add` channel, fan-in via a downstream node or `defer=True`), **orchestrator-worker**, and **evaluator-optimizer** (a loop with a conditional edge back to a generator until a quality check passes).

For **dynamic** parallel fan-out where the branch count is unknown until runtime, use the **Send API** (`from langgraph.types import Send`). A conditional-edge function returns a list of `Send` objects, each dispatching one worker invocation with its own payload; results merge through an `operator.add` channel (map-reduce):

```python
from langgraph.types import Send
def continue_to_jokes(state):
    return [Send("generate_joke", {"subject": s}) for s in state["subjects"]]

builder.add_conditional_edges("generate_topics", continue_to_jokes, ["generate_joke"])
```

### Recommendations

Pin `langgraph==1.2.7` and let its constraints resolve the companion 1.x packages. Write new agents with `langchain.agents.create_agent` (treat `langgraph.prebuilt.create_react_agent` as legacy). Stream UIs with `stream_events(version="v3")` and the `.messages` projection. Declare state as a `TypedDict` with `add_messages`/`operator.add` reducers, and reach for the `Send` API plus an `operator.add` channel whenever fan-out is data-dependent. See open questions for the few details (full `create_agent` signature, default `version` behavior, exact removal timeline for `create_react_agent`) that warrant one more primary-source check before you depend on them.

---

### Open questions from this stream

- Exact full signature of langchain.agents.create_agent (beyond model/tools/system_prompt/middleware/checkpointer/store seen in examples) was not pulled from its primary reference page; confirm response_format, state_schema, context_schema, and pre/post-model hook parameters before relying on them.
- Whether version="v2" is now the default for graph.stream and version="v3" the default for stream_events, or whether the legacy v1 behavior is still the default when version is omitted, is unclear — the docs examples always pass version explicitly. Verify the default against the API reference before omitting it.
- Individual release dates for the 1.0.0 / 1.1.0 / 1.2.0 langgraph milestones were not extracted (only the current 1.2.7 upload time was confirmed); pull from PyPI release history or GitHub releases if a precise upgrade timeline is needed.
- The precise removal timeline/version for the deprecated create_react_agent (i.e., when it will be deleted, not just deprecated) was not found in a primary source.