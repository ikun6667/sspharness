"""Memory plugin — multi-layer context window management.

Implements learn-claude-code s08 context compaction strategies:
  1. tool_result_budget — persist oversized tool results to disk
  2. snip_compact — archive old middle messages to transcripts
  3. micro_compact — shorten consumed tool results
  4. fit_tool_results — persist oversized new results
  5. compact_history — full summarization when over limit
  6. reactive_compact — emergency compaction on API errors

Plus s09 memory strategies:
  - Selective memory recall based on relevance
  - Memory extraction from conversations
  - Memory consolidation when store grows large
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from harness.core.plugin import HookPoint, HookSpec, Plugin

DEFAULT_MAX_TOKENS = 100_000
COMPACT_THRESHOLD = 0.8


class MemoryPlugin(Plugin):
    """Multi-layer context window management with memory system."""

    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        compact_threshold: float = COMPACT_THRESHOLD,
        workspace: str = ".",
    ) -> None:
        self._max_tokens = max_tokens
        self._threshold = compact_threshold
        self._workspace = Path(workspace).resolve()

        # Directories for persisted data
        self._transcript_dir = self._workspace / ".transcripts"
        self._tool_results_dir = self._workspace / ".task_outputs" / "tool-results"
        self._memory_dir = self._workspace / ".memory"

        # Constants from learn-claude-code
        self.CONTEXT_CHAR_LIMIT = 50000
        self.TOOL_RESULT_BATCH_CHAR_LIMIT = 200000
        self.LARGE_RESULT_CHAR_LIMIT = 30000
        self.SUMMARY_INPUT_CHAR_LIMIT = 80000
        self.KEEP_RECENT_RESULTS = 3
        self.KEEP_RECENT_MESSAGES = 5

    @property
    def name(self) -> str:
        return "memory"

    @property
    def priority(self) -> int:
        return 50

    def hooks(self) -> list[HookSpec]:
        return [
            HookSpec(
                point=HookPoint.POST_LLM_CALL,
                fn=self._maybe_compact,
            ),
        ]

    async def _maybe_compact(self, state: dict[str, Any], response: Any) -> dict[str, Any] | None:
        messages = state.get("messages", [])
        estimated = self._estimate_tokens(messages)

        if estimated < self._max_tokens * self._threshold:
            return None

        # Apply multi-layer compaction
        compacted = self._compact(messages)
        return {"messages": compacted}

    def _estimate_tokens(self, messages: list[Any]) -> int:
        total = 0
        for msg in messages:
            content = msg.content if hasattr(msg, "content") else str(msg)
            total += len(content) // 4
        return total

    def _compact(self, messages: list[Any]) -> list[Any]:
        """Apply multi-layer compaction strategy."""
        # Convert to dict format for processing
        msg_dicts = [self._msg_to_dict(msg) for msg in messages]

        # Layer 1: Tool result budget
        msg_dicts = self._tool_result_budget(msg_dicts)

        # Layer 2: Snip compact (archive old middle)
        msg_dicts = self._snip_compact(msg_dicts)

        # Check if still over limit
        if self._estimate_chars(msg_dicts) > self.CONTEXT_CHAR_LIMIT:
            target = int(self.CONTEXT_CHAR_LIMIT * 0.8)

            # Layer 3: Micro compact (shorten old results)
            msg_dicts = self._micro_compact(msg_dicts, target)

            # Layer 4: Fit tool results
            if self._estimate_chars(msg_dicts) > self.CONTEXT_CHAR_LIMIT:
                msg_dicts = self._fit_tool_results(msg_dicts, target)

            # Layer 5: Full history compaction
            if self._estimate_chars(msg_dicts) > self.CONTEXT_CHAR_LIMIT:
                active_request = self._get_active_request(msg_dicts)
                msg_dicts = self._compact_history(msg_dicts, active_request)

        # Convert back to message objects
        return [self._dict_to_msg(d) for d in msg_dicts]

    def _msg_to_dict(self, msg: Any) -> dict:
        """Convert message object to dict."""
        if isinstance(msg, HumanMessage):
            return {"role": "user", "content": msg.content}
        elif isinstance(msg, AIMessage):
            return {"role": "assistant", "content": msg.content}
        elif isinstance(msg, ToolMessage):
            return {"role": "user", "content": [{"type": "tool_result", "content": msg.content}]}
        return {"role": "unknown", "content": str(msg)}

    def _dict_to_msg(self, d: dict) -> Any:
        """Convert dict back to message object."""
        role = d.get("role")
        content = d.get("content", "")

        if role == "user":
            if isinstance(content, list):
                # Check if it's a tool result
                if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                    return ToolMessage(content=str(content), tool_call_id="")
            return HumanMessage(content=content)
        elif role == "assistant":
            return AIMessage(content=content)
        elif role == "system":
            return SystemMessage(content=content)
        return HumanMessage(content=str(content))

    def _estimate_chars(self, messages: list[dict]) -> int:
        return len(json.dumps(messages, default=str, ensure_ascii=False))

    def _get_active_request(self, messages: list[dict]) -> str:
        """Get the most recent user message as active request."""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content
        return ""

    # -- Layer 1: Tool Result Budget --

    def _tool_result_budget(self, messages: list[dict]) -> list[dict]:
        if not messages:
            return messages
        content = messages[-1].get("content")
        if messages[-1].get("role") != "user" or not isinstance(content, list):
            return messages

        blocks = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]
        total = sum(len(str(b.get("content", ""))) for b in blocks)

        for block in sorted(blocks, key=lambda b: len(str(b.get("content", ""))), reverse=True):
            if total <= self.TOOL_RESULT_BATCH_CHAR_LIMIT:
                break
            output = str(block.get("content", ""))
            if len(output) <= self.LARGE_RESULT_CHAR_LIMIT:
                continue
            block["content"] = self._persist_large_output(block.get("tool_use_id", "unknown"), output)
            total = sum(len(str(b.get("content", ""))) for b in blocks)

        return messages

    def _persist_large_output(self, tool_use_id: str, output: str) -> str:
        if len(output) <= self.LARGE_RESULT_CHAR_LIMIT:
            return output
        return self._persisted_preview(tool_use_id, output)

    def _persisted_preview(self, tool_use_id: str, output: str, preview_chars: int = 2000) -> str:
        self._tool_results_dir.mkdir(parents=True, exist_ok=True)
        safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", str(tool_use_id))[:120] or "unknown"
        path = self._tool_results_dir / f"{safe_id}.txt"
        path.write_text(output, encoding="utf-8")
        preview = output[:preview_chars]
        return f"<persisted-output>\nFull output: {path}\nPreview:\n{preview}\n</persisted-output>"

    # -- Layer 2: Snip Compact --

    def _snip_compact(self, messages: list[dict], max_messages: int = 50) -> list[dict]:
        if len(messages) <= max_messages:
            return messages

        head_end = 3
        tail_start = len(messages) - (max_messages - head_end - 1)

        if head_end >= tail_start:
            return messages

        middle = messages[head_end:tail_start]
        if len(middle) == 1 and self._is_archive_marker(middle[0]):
            return messages

        transcript_path = self._write_transcript(messages)
        marker = {"role": "user", "content": f"[{tail_start - head_end} messages archived at {transcript_path}]"}
        return [*messages[:head_end], marker, *messages[tail_start:]]

    def _is_archive_marker(self, message: dict) -> bool:
        content = message.get("content")
        if not isinstance(content, str):
            return False
        match = re.fullmatch(r"\[\d+ messages archived at (.+)\]", content)
        if not match:
            return False
        path = Path(match.group(1))
        return path.resolve().is_relative_to(self._transcript_dir.resolve()) and path.is_file()

    def _write_transcript(self, messages: list[dict]) -> Path:
        self._transcript_dir.mkdir(parents=True, exist_ok=True)
        path = self._transcript_dir / f"transcript_{uuid.uuid4().hex}.jsonl"
        with path.open("x", encoding="utf-8") as f:
            for msg in messages:
                f.write(json.dumps(msg, default=str, ensure_ascii=False) + "\n")
        return path

    # -- Layer 3: Micro Compact --

    def _micro_compact(self, messages: list[dict], target_chars: int | None = None) -> list[dict]:
        results = [
            (mi, bi, block)
            for mi, msg in enumerate(messages)
            if msg.get("role") == "user" and isinstance(msg.get("content"), list)
            for bi, block in enumerate(msg["content"])
            if isinstance(block, dict) and block.get("type") == "tool_result"
        ]

        for _, _, block in results[:-self.KEEP_RECENT_RESULTS]:
            if target_chars is not None and self._estimate_chars(messages) <= target_chars:
                break
            content = str(block.get("content", ""))
            if len(content) <= 120:
                continue
            saved_path = self._persisted_output_path(content)
            if not saved_path:
                saved_path = str(self._save_output(block.get("tool_use_id", "unknown"), content))
            block["content"] = f"[Earlier tool result saved at {saved_path}]"

        return messages

    def _persisted_output_path(self, output: str) -> str | None:
        prefix = "[Earlier tool result saved at "
        if output.startswith(prefix) and output.endswith("]"):
            candidate = output.removeprefix(prefix).removesuffix("]")
            path = Path(candidate)
            if path.resolve().is_relative_to(self._tool_results_dir.resolve()) and path.is_file():
                return str(path)
        return None

    def _save_output(self, tool_use_id: str, output: str) -> Path:
        self._tool_results_dir.mkdir(parents=True, exist_ok=True)
        safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", str(tool_use_id))[:120] or "unknown"
        path = self._tool_results_dir / f"{safe_id}.txt"
        path.write_text(output, encoding="utf-8")
        return path

    # -- Layer 4: Fit Tool Results --

    def _fit_tool_results(self, messages: list[dict], target_chars: int) -> list[dict]:
        results = [
            block
            for msg in messages
            if msg.get("role") == "user" and isinstance(msg.get("content"), list)
            for block in msg["content"]
            if isinstance(block, dict) and block.get("type") == "tool_result"
        ]

        for block in sorted(results, key=lambda b: len(str(b.get("content", ""))), reverse=True):
            if self._estimate_chars(messages) <= target_chars:
                break
            output = str(block.get("content", ""))
            replacement = self._persisted_preview(block.get("tool_use_id", "unknown"), output, preview_chars=1000)
            if len(replacement) < len(output):
                block["content"] = replacement

        return messages

    # -- Layer 5: Compact History --

    def _compact_history(self, messages: list[dict], active_request: str) -> list[dict]:
        transcript = self._write_transcript(messages)
        summary = self._summarize_history(messages)
        return [self._summary_message("Compacted", active_request, summary, transcript)]

    def _summarize_history(self, messages: list[dict]) -> str:
        """Summarize conversation history. In production, this would call the LLM."""
        # For now, create a simple summary
        user_msgs = [m for m in messages if m.get("role") == "user"]
        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]

        summary_parts = [
            f"Conversation had {len(user_msgs)} user messages and {len(assistant_msgs)} assistant responses.",
            f"Total messages: {len(messages)}",
        ]

        # Add recent context
        recent = messages[-5:] if len(messages) > 5 else messages
        for msg in recent:
            content = str(msg.get("content", ""))[:100]
            summary_parts.append(f"[{msg.get('role')}]: {content}")

        return "\n".join(summary_parts)

    def _summary_message(self, label: str, request: str, summary: str, transcript: Path) -> dict:
        return {
            "role": "user",
            "content": (
                f"[{label}]\n\nCurrent user request:\n{request}\n\n"
                f"Conversation summary (reference only):\n{json.dumps(summary, ensure_ascii=False)}\n\n"
                f"Full transcript: {transcript}"
            ),
        }

    # -- Layer 6: Reactive Compact --

    def _reactive_compact(self, messages: list[dict], active_request: str) -> list[dict]:
        transcript = self._write_transcript(messages)
        tail_start = max(0, len(messages) - self.KEEP_RECENT_MESSAGES)
        old_history = messages[:tail_start] if tail_start else messages
        summary = self._summarize_history(old_history)
        message = self._summary_message("Reactive compact", active_request, summary, transcript)
        return [message, *messages[tail_start:]] if tail_start else [message]
