# Architecture

This document is the "why," not the "what" — [README.md](README.md) covers
setup and a plain-English tour of the concepts. Here: the actual design
decisions, the trade-offs behind each one, the limitations that were left in
deliberately (and why), and a forward-looking path to what would actually
need to change to run this at real scale.

## Request flow

**Uploading a document** (`POST /api/documents/upload`, auth required):
parse (pypdf/python-docx) → split into overlapping chunks
(`langchain-text-splitters`) → embed every chunk locally (fastembed, ONNX,
no network call) → upsert into Qdrant with `owner_id` in the payload → run
the NLP pipeline (spaCy NER, frequency-ranked keyphrases, TextRank
summarization) → write the document row (with entities/topics/summary as
JSON columns) to SQL → invalidate that user's cached document list in
Redis.

**Asking a question** (`POST /api/chat/ask` or `WS /ws/chat`, auth
required): the compiled LangGraph pipeline runs `START → router →
(retrieval, tool, both, or neither) → END`. The Router calls Claude for a
structured `{route, reasoning}` decision (`messages.parse()` against a
Pydantic model). Retrieval embeds the question and queries Qdrant with a
`Filter` on `owner_id` (never search another user's documents). Tool asks
Claude which MCP tool(s) to call (`tool_choice: {"type": "any"}`), then
actually calls them against the real MCP server. Once the graph reaches
`END`, the Summarizer — not a graph node, see below — composes the final
answer from whatever was gathered. The REST endpoint waits for the whole
answer; the WebSocket streams agent-activity events and the answer's text
deltas live as they happen.

## Design decisions and trade-offs

### LLM: Claude, via `AsyncAnthropic`

Chosen over OpenAI for three concrete reasons that mattered for *this*
project, not as a blanket claim one is "better": (1) `client.messages.parse()`
gives schema-validated structured output for the Router's routing decision
without hand-rolling JSON-mode parsing/retries; (2) the async client means
Claude calls inside LangGraph nodes never block the FastAPI event loop while
handling concurrent requests — this was a real bug caught and fixed
(Phase 3's original `services/llm.py` used the sync client, would have
serialized concurrent chat requests behind Claude's response latency); (3)
per-request `output_config={"effort": ...}` lets each agent trade cost/
quality independently — the Router and Tool-selector use `"medium"`, cheaper
than the API default, because routing decisions don't need the same depth as
the final answer.

**Trade-off named, not hidden:** every agent node currently shares one
`CLAUDE_EFFORT` setting rather than being tuned per-node. Fine at this
scope; a production system doing real cost optimization would tune this
per-agent based on measured routing-decision quality vs. cost.

### Vector DB: Qdrant, self-hosted

Chosen over Chroma (great for prototyping, weaker production filtering
story) and over a fully managed option (Pinecone) specifically to
demonstrate operating a real vector database, not just calling a library.
The concrete payoff: per-user document isolation is a `Filter` on
`owner_id` passed to `query_points`, evaluated by Qdrant at query time — not
an application-layer "fetch everything, filter in Python" workaround, which
wouldn't scale and would leak data under any bug in that filtering code.

**Trade-off named, not hidden:** one shared collection holds every user's
chunks, distinguished only by the `owner_id` payload field. Fine at this
scale (a demo with a handful of users); a system with real multi-tenancy at
scale would consider per-tenant collections or a payload-indexed field with
Qdrant's dedicated tenant-isolation features, trading some operational
simplicity for stronger blast-radius containment.

### Agent orchestration: LangGraph (`StateGraph`)

Chosen over CrewAI (higher-level, more opinionated, less control over exact
execution semantics) and over hand-written sequential function calls,
because the control flow here is genuinely conditional and sometimes
parallel: the `"both"` route runs Retrieval and Tool in the same LangGraph
superstep, and `AgentState.events` uses an `Annotated[list[AgentEvent],
operator.add]` reducer specifically so both agents' concurrent partial state
updates get concatenated instead of one silently overwriting the other —
this is Pregel-style parallel fan-out/fan-in, not something a linear chain
of `await` calls expresses naturally. A conditional-edges graph is also
inspectable (`graph.get_graph().draw_mermaid()` renders the actual decision
structure) in a way a function full of `if`/`elif` isn't.

**The one real architectural pivot in this project:** the Summarizer started
as a graph node, then was deliberately pulled *out* of the graph in the
phase that added WebSocket streaming. Reason: LangGraph's `stream_mode=
"messages"` auto-detection targets LangChain-wrapped chat models, not raw
Anthropic SDK calls, so streaming a graph node's tokens live would have
needed deep custom-streaming plumbing. Instead, the graph's job stops at
"gather context" (`router → retrieval/tool → END`), and `summarize()`/
`stream_summary()` are plain async functions called directly by each
endpoint afterward. This is also why the WebSocket handler has to
hand-construct a synthetic "summarizer" activity event before calling
`stream_summary()` — since it's not a graph node, it never appears in the
`astream(stream_mode="updates")` loop that produces every other agent's
event automatically.

### MCP: a real, separate server

The MCP server (`mcp-server/`) is a genuinely standalone process reachable
over HTTP (`streamable-http` transport), not a Python function imported and
called directly — the backend's Tool Agent connects to it as an ordinary MCP
client (`mcp.Client`, `list_tools()`, `call_tool()`), the same way it would
connect to any third-party MCP server. Three tools: `web_search` (DuckDuckGo
via `ddgs`, zero API key so the whole demo runs with no signup),
`calculate` (parses expressions via `ast` and walks them with an operator
allowlist — **deliberately not `eval()`**, since `eval()` would execute
arbitrary Python from a string an agent, or a prompt-injected document,
could influence; this is tested explicitly with an
`__import__('os').system(...)` rejection case), and `document_metadata`
(calls back into the main backend's own REST API over HTTP, not a shared
database — keeping the MCP server a genuinely standalone process with no
direct dependency on the backend's internals).

**Trade-off named, not hidden:** `document_metadata` authenticates to the
backend via a shared internal service key (`X-Internal-Api-Key`), not the
original asking user's JWT — MCP tool calls in this SDK's design don't carry
the calling end-user's identity through the protocol hop. That means this
one lookup-by-ID path bypasses per-user document filtering (it still
requires *a* valid credential, just not the *asking user's* one). Named
explicitly rather than left as a silent gap: propagating end-user identity
through an MCP tool call is a real, harder problem (the tool's schema is
static, defined once at server registration) that would need either a
custom MCP extension or restructuring which layer decides to call this tool.

### Classical NLP: spaCy + TextRank, not an LLM call

Named entity recognition and summarization run through spaCy's
`en_core_web_sm` model and a hand-rolled TextRank implementation (sentence
embeddings → cosine-similarity graph → power-iteration PageRank), not
another Claude call. This is a deliberate second skill demonstration, not a
cost-cutting measure — the LLM half of this project (agents, RAG generation)
and the classical-NLP half are intentionally built with different
techniques on the same underlying documents so both are independently
visible in the codebase.

**Trade-off named, not hidden:** keyphrase extraction ranks noun phrases by
frequency *within a single document*, not TF-IDF against a corpus — it won't
downweight generic phrases the way a corpus-aware method would. Good enough
for a single-document "what's this about" signal; a multi-document corpus
feature would need the TF-IDF (or embedding-based) upgrade.

### Data layer: SQL + vector DB, deliberately split

Qdrant stays a pure vector index (chunk text + embedding + `owner_id` +
`document_id`); SQLite (via SQLAlchemy 2.0) is the source of truth for
document-level metadata (filename, chunk count, computed entities/topics/
summary) and for user accounts. `filename` is duplicated onto every Qdrant
chunk's payload specifically so retrieval/citation doesn't need a join back
to SQL at answer time — a deliberate denormalization for read-path latency,
not an oversight.

**Trade-off named, not hidden:** the Qdrant upsert and the SQL write for a
new document aren't in one transaction — a crash between them could leave
chunks indexed in Qdrant with no matching SQL row (or vice versa). Acceptable
for a portfolio-scope project; a production system would need an outbox
pattern or a reconciliation job to guarantee the two stay consistent.

### Auth: JWT access + rotating refresh tokens

Access tokens are short-lived, stateless JWTs (fast — no DB/Redis lookup to
verify one). Refresh tokens are also JWTs, but are additionally tracked in a
Redis allowlist (`refresh_token:{jti} → user_id`, TTL matching the token's
own expiry) specifically so they're *actually* revocable — a pure JWT can't
be un-issued before it expires. Every successful refresh **rotates**: the
old `jti` is deleted and a brand-new pair issued, so a stolen refresh token
works exactly once before the legitimate client's next refresh fails — a
real signal of theft, not just a longer exposure window.

WebSocket auth rides in a `?token=` query param (browsers can't set headers
on a WS handshake) and is checked once at connect time. On failure, the
handler **accepts the connection, then immediately closes it** with an
app-specific code (`4401`) — closing before accept would only surface to the
browser as an opaque connection error with no machine-readable reason;
closing after accept is what the browser's `WebSocket.onclose` handler can
actually read as `event.code`.

**Trade-offs named, not hidden:**
- The WS token isn't re-validated per message — a session that outlives its
  access token's expiry stays connected until it disconnects/reconnects.
  Real fix: a short-lived, WS-specific token, or periodic re-auth.
- Tokens live in `localStorage`, not an httpOnly cookie — simpler (no
  cookie/CORS/CSRF wiring) at the cost of being readable by any script on
  the page, including from an XSS vulnerability. A cookie-based design would
  be the right call for anything handling genuinely sensitive data.

### Redis: one primitive, three jobs

Redis's actual primitive is "a key with an optional TTL, fast." This project
leans on that directly for three unrelated-looking jobs instead of treating
Redis as just a cache: the refresh-token allowlist above, a fixed-window
rate limiter (`INCR` + `EXPIRE`, applied to login/register/upload/chat),
and a cache-aside layer on `GET /api/documents` (short TTL as a staleness
backstop, explicit `DELETE` on upload as the real invalidation path).

**Trade-off named, not hidden:** the rate limiter is fixed-window, not
sliding-window/token-bucket — a client can send up to 2x the limit across a
window boundary. It's also keyed by client IP (covers the unauthenticated
login/register endpoints, the classic brute-force targets), which means
everyone behind one NAT/proxy shares a bucket. Both are reasonable
simplifications for protecting a demo from accidental hammering, not a
hardened abuse defense.

### Frontend: React Query for REST, a plain hook for the socket

Documents (upload/list/detail) go through React Query — request
caching/retry/loading states are exactly its job. The WebSocket chat
deliberately does **not** use React Query: it's a long-lived, stateful
stream where messages arrive out of band, not a cacheable request/response
pair, so a hand-rolled `useChatSocket` hook owns reconnect-on-close logic
and translates the wire protocol into React state directly.

The axios interceptor's 401-handling dedupes concurrent refresh attempts
behind one shared in-flight promise — since refresh tokens rotate on use, a
"refresh stampede" from several requests failing at once would otherwise
invalidate all but one rotation and spuriously log out the others.

Tailwind v4 was chosen over the reference project's older CSS conventions
deliberately (a documented departure, not an oversight) for a cleaner setup
(`@tailwindcss/vite`, no config file) and a more modern chat-product feel.

### Testing: hermetic by construction

Every external dependency — Qdrant, the Claude client, the MCP client,
Redis, the SQL database — is faked at the exact point the code imports it
(`monkeypatch.setattr(module, "name", fake)` for singletons/clients,
`fakeredis`/in-memory SQLite for stateful stores, `app.dependency_overrides`
for FastAPI's own DI). This isn't incidental — it's *why* CI (see below)
needs zero live infrastructure, and it's why tests are fast and
deterministic enough to run on every push without flaking on network
conditions a real service might introduce.

### CI/CD: zero live infrastructure

`.github/workflows/ci.yml` runs three independent jobs (backend, mcp-server,
frontend) with no `services:` containers, no API keys, no secrets — a direct
consequence of the hermetic testing philosophy above. This was verified
concretely before writing the workflow: neither `test_nlp.py` nor
`test_documents.py` ever triggers a real spaCy model load or fastembed
download, so CI doesn't need a `spacy download` step either.

### Deployment: environment-variable-driven config as the portability layer

The same backend code runs correctly against Qdrant/Redis/the MCP server at
`localhost` (bare host dev), a Docker Compose service name (`http://
qdrant:6333`), or a Render private-network hostname — because every one of
those addresses is a `Settings` field read from the environment, never
hardcoded. The one place this pattern *can't* apply is the frontend's API
base URL: Vite bakes `VITE_*` values into the JS bundle at **build** time,
not read from the environment at container start the way a server-rendered
app would — so it has to be the browser-reachable URL specifically, and
changing it means rebuilding the image, not just restarting a container.
This is documented at the point of maximum confusion (the `ARG` in
`frontend/Dockerfile`) rather than assumed obvious.

**Trade-off named, not hidden:** the live Render deployment targets the free
tier, which has an ephemeral filesystem — Qdrant's index and the SQLite
database reset on every restart/redeploy/15-minute-idle spin-down. Chosen
deliberately (zero cost, acceptable for "register/upload/chat in one
sitting" portfolio demo purposes) over paying for a persistent disk; the
upgrade path is a plan change plus a `disk:` block, not an architecture
change. See [DEPLOYMENT.md](DEPLOYMENT.md).

## Known limitations (consolidated)

Everything below is a named, deliberate scope boundary — cross-referenced to
where it's discussed above — not something missed:

1. Qdrant/SQL writes on upload aren't transactional (data layer).
2. `document_metadata`'s MCP tool call doesn't carry end-user identity
   through the protocol hop (MCP).
3. Keyphrase extraction is single-document frequency-ranked, not corpus-aware
   TF-IDF (classical NLP).
4. WebSocket sessions aren't re-validated per message after connect-time
   auth (auth).
5. Tokens live in `localStorage`, not an httpOnly cookie (auth).
6. The rate limiter is fixed-window and IP-keyed (Redis).
7. One Qdrant collection for every user, distinguished by a payload field,
   not per-tenant collections (vector DB).
8. Every agent node shares one Claude "effort" setting rather than being
   tuned per-node (LLM).
9. Free-tier live deployment has an ephemeral filesystem — no data
   persistence across restarts (deployment).
10. Web search runs through a free, unauthenticated DuckDuckGo wrapper
    (`ddgs`) — less reliable than a dedicated paid search API, and not
    something to depend on in production.

## Enterprise-scale evolution path

What would actually need to change to run this for real traffic, roughly in
the order it would start to matter:

1. **Postgres instead of SQLite.** Already a `DATABASE_URL` change — the
   whole point of routing every DB access through SQLAlchemy. Needed the
   moment more than one backend instance runs concurrently (SQLite's
   single-writer file lock doesn't survive horizontal scaling).
2. **Horizontal scaling of the backend + WebSocket fanout.** Multiple
   backend replicas behind a load balancer need either sticky sessions for
   `/ws/chat` or a pub/sub layer (Redis Streams/pub-sub, or a message
   broker) so any replica can relay agent events to a client connected to a
   different one.
3. **Observability.** Structured JSON logs with request-ID propagation
   exist today (`core/logging.py`, `core/middleware.py`); a real deployment
   adds distributed tracing (OpenTelemetry spans across the REST call →
   LangGraph node → Claude API → MCP call chain) and metrics (latency/error
   rate per route, per agent node, per Claude call) feeding an actual
   dashboard/alerting stack.
4. **Secrets management.** `.env` files and platform dashboard env vars are
   fine for a demo; a real deployment moves `ANTHROPIC_API_KEY`,
   `JWT_SECRET_KEY`, `INTERNAL_API_KEY` into a proper secrets manager (AWS
   Secrets Manager, Vault, or the cloud platform's native equivalent) with
   rotation.
5. **MCP identity propagation.** Solve limitation #2 above properly —
   likely means the Tool Agent passing a short-lived, narrowly-scoped
   service token derived from the requesting user's identity into the MCP
   call, rather than the current shared internal-service key.
6. **RAG evaluation harness.** Nothing currently measures retrieval quality
   or answer faithfulness beyond manual spot-checking. A real system needs a
   golden-question-set eval loop (retrieval precision/recall, answer
   groundedness scoring) run in CI against representative documents, so a
   change to chunking/embedding/prompting has a measurable regression
   signal instead of a vibe check.
7. **Multi-tenant vector DB isolation.** Move from one collection +
   `owner_id` filter to genuinely isolated per-tenant storage once the
   number of users/documents makes shared-collection blast radius a real
   risk, not a theoretical one.
8. **A paid, reliable web search API** (Tavily, Serper, Brave Search)
   replacing the free DuckDuckGo wrapper — trading zero-signup convenience
   for actual uptime/rate-limit guarantees.
9. **A proper API gateway for rate limiting**, replacing the hand-rolled
   fixed-window Redis limiter — sliding-window or token-bucket semantics,
   and limiting infrastructure that survives the backend itself scaling
   horizontally without every replica needing its own correct Redis-backed
   counter logic.
