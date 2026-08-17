from src.services import summarizer_agent as summarizer_module
from src.services.summarizer_agent import _build_user_message
from src.services.mcp_client import ToolCallResult
from src.services.retrieval import RetrievedChunk


def _chunk(text: str = "Revenue grew 12%.") -> RetrievedChunk:
    return RetrievedChunk(
        document_id="doc-1", filename="report.pdf", chunk_index=0, text=text, score=0.9
    )


def _tool_result(output: str = "42") -> ToolCallResult:
    return ToolCallResult(
        tool_name="calculate", tool_input={"expression": "40+2"}, output=output, is_error=False
    )


def test_build_user_message_includes_numbered_excerpts_and_tool_results():
    message = _build_user_message("What grew, and what is 40+2?", [_chunk()], [_tool_result()])

    assert "[1] (from report.pdf) Revenue grew 12%." in message
    assert "Tool 'calculate' result:\n42" in message
    assert "Question: What grew, and what is 40+2?" in message


def test_build_user_message_notes_when_nothing_was_gathered():
    message = _build_user_message("What is the capital of France?", [], [])

    assert "No document excerpts or tool results" in message


async def test_summarize_returns_the_complete_answer(monkeypatch):
    async def fake_ask_claude(*, system, user_message):
        assert "Revenue grew 12%." in user_message
        return "Revenue grew 12% [1]."

    monkeypatch.setattr(summarizer_module, "ask_claude", fake_ask_claude)

    answer = await summarizer_module.summarize("What grew?", [_chunk()], [])

    assert answer == "Revenue grew 12% [1]."


async def test_stream_summary_yields_text_deltas_in_order(monkeypatch):
    async def fake_stream_claude(*, system, user_message):
        for delta in ["Revenue ", "grew ", "12% [1]."]:
            yield delta

    monkeypatch.setattr(summarizer_module, "stream_claude", fake_stream_claude)

    deltas = [delta async for delta in summarizer_module.stream_summary(
        "What grew?", [_chunk()], []
    )]

    assert deltas == ["Revenue ", "grew ", "12% [1]."]
    assert "".join(deltas) == "Revenue grew 12% [1]."
