# Research: OBSERVABILITY & EVALUATION for a LangGraph agent

> Cited synthesis from the Pitch IQ research workflow (run 2026-06-30). Versions/URLs are primary-source-verified; see open questions for unresolved items.

**Executive summary:** For a LangGraph agent in mid-2026, LangSmith remains the most native tracing/eval option: enable it by exporting LANGSMITH_TRACING=true, LANGSMITH_API_KEY, and LANGSMITH_PROJECT, after which every graph.invoke automatically records the full execution tree per node (inputs/outputs, tool calls, token usage, latency, errors). The current SDK is langsmith 0.9.3 (2026-06-26); the free Developer tier gives 5k base traces/month at 14-day retention and 1 seat, Plus is $39/seat/month with 10k base traces and $2.50/1k overage. LangSmith also accepts OpenTelemetry at https://api.smith.langchain.com/otel (OpenLLMetry semantics), and Langfuse (MIT, self-hostable) or Arize Phoenix (OTel-native) are the leading alternatives when open-source/self-hosting or framework-agnosticism matter. For evaluation, build offline datasets with the langsmith SDK and run them in CI via the pytest integration (pip install "langsmith[pytest]", @pytest.mark.langsmith, request caching via LANGSMITH_TEST_CACHE). Concretely: evaluate router accuracy with a deterministic exact-match evaluator plus a macro-F1/confusion-matrix summary evaluator (optionally agentevals 0.0.9 trajectory match); evaluate the generator-critic step with custom numeric calibration evaluators (Brier/log-loss/ECE) plus an LLM-judge that checks whether the critic flags naive predictions; and evaluate Q&A groundedness with openevals 0.2.0 HALLUCINATION_PROMPT / RAG_GROUNDEDNESS_PROMPT via create_llm_as_judge, passing the live data as context. With OpenAI strict structured outputs, schema validity is guaranteed so evals should target field-value correctness and track the refusal rate rather than JSON parse failures.

---

## Observability & Evaluation for a LangGraph Agent (verified 2026-06-30)

### 1. Tracing with LangSmith

For a LangGraph app the lowest-friction path is LangSmith's native integration. Per the [Trace LangGraph applications docs](https://docs.langchain.com/langsmith/trace-with-langgraph), when you use LangChain/LangGraph modules you enable tracing purely through environment variables — no code changes:

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=<key>
export LANGSMITH_PROJECT=<project-name>     # routes traces into a project
# non-US only, e.g. export LANGSMITH_ENDPOINT="https://eu.api.smith.langchain.com"
```

`LANGSMITH_TRACING` is the current variable name; the older `LANGCHAIN_TRACING_V2` (+ `LANGCHAIN_API_KEY`) still works and maps to the same "tracing v2" path — the client reads `TRACING_V2` falling back to `TRACING` ([env var reference](https://support.langchain.com/articles/3567245886-how-do-i-set-up-langsmith-api-key-environment-variables), [forum/quickstart](https://docs.langchain.com/langsmith/observability-quickstart)). For non-LangChain code, decorate functions with `@traceable`.

**What a trace captures:** every `graph.invoke()` produces the full execution tree. LangSmith records, per node, the inputs/outputs, tool calls, token usage, latency, and errors, plus cost and feedback. Dashboards track P50/P99 latency, token usage, error and cost breakdowns ([LangSmith observability](https://www.langchain.com/langsmith/observability); cross-checked by a practitioner [walkthrough](https://ravjot03.medium.com/langsmith-for-agent-observability-tracing-langgraph-tool-calling-end-to-end-2a97d0024dfb)).

**Pricing** (from the official [LangChain pricing page](https://www.langchain.com/pricing)):

| Tier | Price | Included base traces | Seats | Retention |
|---|---|---|---|---|
| Developer (free) | $0 | 5k/mo then PAYG | 1 | 14-day base |
| Plus | $39/seat/mo | 10k/mo then PAYG | Unlimited | 14-day base |
| Enterprise | Custom | Custom | Custom | Self/hybrid host |

Base traces have 14-day retention at **$2.50 / 1k**; extended traces have 400-day retention at **$5.00 / 1k**. The 5k free-tier figure is cross-checked by third-party trackers ([pecollective](https://pecollective.com/blog/langsmith-pricing/), [inference.net](https://inference.net/content/langsmith-pricing/)).

### 2. OpenTelemetry and alternatives

LangSmith now ingests OpenTelemetry directly: point any OTLP exporter at `https://api.smith.langchain.com/otel` using OpenLLMetry semantic conventions ([OTel docs](https://docs.langchain.com/langsmith/trace-with-opentelemetry), [announcement](https://blog.langchain.com/opentelemetry-langsmith/)). This is the lock-in hedge — you can move the same instrumentation elsewhere.

Choose an alternative when constraints dominate ([Langfuse comparison](https://langfuse.com/faq/all/langsmith-alternative), [Laminar ranking](https://laminar.sh/article/2026-04-23-top-6-agent-observability-platforms)):
- **Langfuse** — MIT-licensed, self-hostable, framework-agnostic, transparent pricing; third-party numbers put ~100k traces/mo at ~$69/mo cloud vs ~$420/mo for a 5-seat LangSmith plan. Best when open-source/self-hosting or cost dominate.
- **Arize Phoenix** — open-source (Elastic 2.0), OTel/OpenInference-native; best when you want vendor-neutral OTel debugging or already use Arize.
- **LangSmith** — pick it when you are committed to LangGraph and want the deepest native UX (LangGraph Studio).

### 3. Evaluation harness and CI

Build datasets with the [langsmith SDK](https://pypi.org/project/langsmith/) (`0.9.3`, 2026-06-26): `Client.create_dataset(...)` + `client.create_examples(dataset_id, examples=[{"inputs":..., "outputs":...}])`. Define a `target(inputs)->dict`, a list of evaluators, and run `client.evaluate(target, data=..., evaluators=[...], experiment_prefix=...)` ([quickstart](https://docs.langchain.com/langsmith/evaluation-quickstart)). Row-level evaluators receive `inputs/outputs/reference_outputs` and return `{"key":..., "score":...}`; summary evaluators run over the whole dataset for aggregate metrics ([evaluate() reference](https://langsmith-sdk.readthedocs.io/en/latest/evaluation/langsmith.evaluation._runner.evaluate.html)).

**In CI:** install `pip install -U "langsmith[pytest]"`, decorate tests with `@pytest.mark.langsmith`, and log via `t.log_inputs / t.log_outputs / t.log_reference_outputs` ([pytest docs](https://docs.langchain.com/langsmith/pytest), [announcement](https://blog.langchain.com/pytest-and-vitest-for-langsmith-evals/)). Key env knobs: `LANGSMITH_TEST_CACHE` (cache LLM HTTP calls so commits don't re-pay), `LANGSMITH_TEST_SUITE`, `LANGSMITH_EXPERIMENT`, `LANGSMITH_EXPERIMENT_METADATA` (JSON, for CI labels), and `LANGSMITH_TEST_TRACKING=false` for dry runs. Parametrize with `@pytest.mark.parametrize`, parallelize with `pytest -n auto`.

Prebuilt judges come from [openevals](https://pypi.org/project/openevals/) (`0.2.0`, 2026-04-07) and [agentevals](https://pypi.org/project/agentevals/) (`0.0.9`). `create_llm_as_judge(prompt=..., model="openai:o3-mini", feedback_key=..., continuous=?, choices=?, use_reasoning=?)` returns an evaluator you call with `inputs/outputs/reference_outputs/context` ([openevals repo](https://github.com/langchain-ai/openevals)).

### 4. Concrete evaluators per task

**(a) Routing accuracy (classifier/router node).** This is closed-set classification with labels, so use a *deterministic* exact-match row evaluator, not an LLM judge:

```python
def routing_correct(outputs, reference_outputs):
    ok = outputs["route"] == reference_outputs["route"]
    return {"key": "routing_correct", "score": int(ok)}
```

Add a **summary evaluator** computing accuracy, per-class precision/recall, macro-F1 and a confusion matrix to expose which routes collide. Force the router to emit an enum via OpenAI strict structured outputs so the label space is closed. If the route manifests as a tool/subgraph call, also assert it with agentevals `create_trajectory_match_evaluator(trajectory_match_mode="unordered"|"subset")` ([trajectory docs](https://docs.langchain.com/langsmith/trajectory-evals)).

**(b) Prediction sanity for a generator-evaluator (critic).** Two complementary suites:
- *Does the critic catch naive predictions?* Build a labeled dataset of deliberately naive predictions (e.g. "always pick the favorite", ignores live data) tagged `should_flag=true` plus sound ones tagged `false`. Measure the critic's **precision/recall/F1** at flagging — recall = caught bad ones, precision = didn't over-flag good ones. An openevals `create_llm_as_judge` with a custom rubric ("does the critique correctly identify the flaw?") works as a categorical judge here.
- *Calibration vs odds.* Use **deterministic numeric** summary evaluators: Brier score, log loss, and expected calibration error (ECE) comparing predicted probabilities to outcomes/market-implied odds; plus a sanity evaluator asserting probabilities are in [0,1], sum to 1, and fall within a sane band of the implied market line. Numeric calibration should never be delegated to an LLM judge.

**(c) Groundedness / faithfulness (Q&A over live data).** Use openevals `create_llm_as_judge(prompt=HALLUCINATION_PROMPT, ...)` (or `RAG_GROUNDEDNESS_PROMPT`) and pass the live data as `context` and the answer as `outputs`; report a **hallucination rate / groundedness pass-rate**. If you retrieve, add `RAG_RETRIEVAL_RELEVANCE_PROMPT`. Pair the judge with a cheap deterministic check that numeric facts/entities in the answer actually appear in the source — this catches fabricated figures the judge may miss and reduces reliance on judge variance.

### 5. OpenAI structured outputs — eval considerations

Per the [OpenAI structured outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs): with `response_format: {type:"json_schema", json_schema:{strict:true,...}}` the model is guaranteed to adhere to the schema (all required keys present, valid enum values, correct types). Consequences for evals:
- **Schema validity stops being the interesting metric** for supported models — evaluate field *values*, e.g. openevals `create_json_match_evaluator` (exact match per key, or per-key LLM judge with an aggregator).
- **Track refusals as a first-class failure**: a refusal surfaces as `message.refusal` rather than schema-conforming JSON; count refusal rate separately from "wrong answer."
- Schema constraints to honor when building eval fixtures: `additionalProperties:false` on every object, all fields required by default (optional = union with `null`), and unsupported keywords (`minimum/maximum`, `pattern`, etc.). This is corroborated by OpenAI's [original announcement](https://openai.com/index/introducing-structured-outputs-in-the-api/). Support spans `gpt-4o-2024-08-06` and later snapshots through the 2026 gpt-5.x line — **pin a snapshot** for reproducible evals.

### Recommendations
See the structured `recommendations` list. In short: trace with LangSmith via `LANGSMITH_TRACING`; gate CI with the `langsmith[pytest]` integration + caching; use deterministic evaluators for routing accuracy and calibration, openevals LLM judges for groundedness, and value-level checks (not schema validity) plus refusal-rate tracking for structured outputs; keep Langfuse/Phoenix and the LangSmith `/otel` endpoint as the lock-in hedge.

---

### Open questions from this stream

- agentevals on PyPI shows version 0.0.9 with a 2025-07-24 date, which looks stale relative to langsmith/openevals; confirm whether a newer agentevals release exists or whether trajectory eval has been folded into openevals before pinning it in production.
- The exact OpenAI judge/generation model snapshot to pin for 2026 is unverified from a primary OpenAI model-list source. Third-party guides and the openevals example reference gpt-5.x (e.g. gpt-5.5 / gpt-5.4 / o3-mini); verify the live snapshot id on OpenAI's models page before hardcoding.
- LangSmith's free Developer tier retention: the official pricing page lists base traces at 14-day retention generally, but does not separately state free-tier retention on a primary page; cross-checked only against third-party pricing blogs.
- LangSmith OTel ingestion currently requires OpenLLMetry semantic conventions; support for the OpenTelemetry GenAI semantic convention was described as planned. Verify current status before standardizing on GenAI semconv.
- langgraph 1.2.6 was obtained from a web search summary of PyPI rather than a direct fetch of the PyPI/releases page; re-confirm the exact current patch version directly.