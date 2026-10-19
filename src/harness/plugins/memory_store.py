"""Memory store plugin — selective recall, extraction, and consolidation.

Implements learn-claude-code s09 memory system:
  - Memory recall: select relevant memories based on current context
  - Memory extraction: extract durable knowledge from conversations
  - Memory consolidation: merge and deduplicate when store grows large
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from harness.core.plugin import HookPoint, HookSpec, Plugin


MEMORY_TYPES = ("user", "feedback", "project", "reference")
TEMPORARY_MARKERS = (
    "this session", "current session", "this turn", "current turn",
    "this task", "current task", "for now", "just this time", "today only",
    "本次会话", "当前会话", "这一轮", "当前轮次", "本次任务", "当前任务", "暂时",
)
RECALL_CHAR_LIMIT = 20000
CONSOLIDATE_THRESHOLD = 10
CONSOLIDATE_INPUT_CHAR_LIMIT = 20000


class MemoryStorePlugin(Plugin):
    """Persistent memory system with selective recall and extraction."""

    def __init__(self, workspace: str = ".") -> None:
        self._workspace = Path(workspace).resolve()
        self._memory_dir = self._workspace / ".memory"
        self._memory_index = self._memory_dir / "MEMORY.md"

    @property
    def name(self) -> str:
        return "memory_store"

    @property
    def priority(self) -> int:
        return 40  # Lower than memory plugin so it runs after

    def hooks(self) -> list[HookSpec]:
        return [
            HookSpec(
                point=HookPoint.PRE_LLM_CALL,
                fn=self._inject_memories,
            ),
            HookSpec(
                point=HookPoint.POST_LLM_CALL,
                fn=self._maybe_extract_memories,
            ),
        ]

    async def _inject_memories(self, state: dict[str, Any]) -> dict[str, Any] | None:
        """Inject relevant memories into the system prompt."""
        relevant = self._load_memories(state.get("messages", []))
        if not relevant:
            return None

        # Add memories as a system message
        from langchain_core.messages import SystemMessage
        memory_msg = SystemMessage(content=f"Relevant memories:\n{relevant}")

        messages = state.get("messages", [])
        return {"messages": [memory_msg, *messages]}

    async def _maybe_extract_memories(self, state: dict[str, Any], response: Any) -> dict[str, Any] | None:
        """Extract memories after LLM response if appropriate."""
        messages = state.get("messages", [])
        # Extract memories every 5 turns to avoid excessive calls
        if len(messages) % 10 != 0:
            return None

        self._extract_memories(messages)
        self._maybe_consolidate()
        return None

    # -- Memory Store Operations --

    def _memory_slug(self, name: str) -> str:
        slug = re.sub(r"[^\w]+", "-", name.lower()).strip("-_")
        return slug or "memory"

    def _memory_path(self, filename: str, allow_index: bool = False) -> Path:
        if Path(filename).name != filename:
            raise ValueError(f"Invalid memory filename: {filename}")
        if filename == self._memory_index.name and not allow_index:
            raise ValueError("The memory index is not a memory record")

        root = self._memory_dir.resolve()
        if not root.is_relative_to(self._workspace.resolve()):
            raise ValueError("Memory directory escapes the workspace")
        path = (root / filename).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"Memory path escapes the store: {filename}")
        return path

    def _parse_frontmatter(self, text: str) -> tuple[dict, str]:
        if not text.startswith("---\n"):
            return {}, text
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text
        try:
            # Simple YAML parsing without yaml library
            metadata = {}
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip()] = value.strip()
        except Exception:
            return {}, text
        return metadata, parts[2].lstrip()

    def _write_memory_file(self, name: str, mem_type: str, description: str, body: str) -> Path:
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        path = self._memory_path(f"{self._memory_slug(name)}.md")

        metadata = f"name: {name}\ndescription: {description}\ntype: {mem_type}\n"
        content = f"---\n{metadata}---\n\n{body.strip()}\n"
        path.write_text(content, encoding="utf-8")

        self._rebuild_memory_index()
        return path

    def _rebuild_memory_index(self) -> None:
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        lines = []
        for path in sorted(self._memory_dir.glob("*.md")):
            if path.name == self._memory_index.name:
                continue
            try:
                path = self._memory_path(path.name)
            except ValueError:
                continue
            metadata, body = self._parse_frontmatter(path.read_text(encoding="utf-8"))
            name = " ".join(str(metadata.get("name") or path.stem).split())
            first_line = next((line for line in body.splitlines() if line.strip()), "")
            description = " ".join(str(metadata.get("description") or first_line).split())
            lines.append(f"- [{name}]({path.name}) - {description}")

        self._memory_path(self._memory_index.name, allow_index=True).write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
        )

    def _read_memory_index(self) -> str:
        try:
            path = self._memory_path(self._memory_index.name, allow_index=True)
        except ValueError:
            return ""
        return path.read_text(encoding="utf-8").strip() if path.exists() else ""

    def _read_memory_file(self, filename: str) -> str | None:
        try:
            path = self._memory_path(filename)
        except ValueError:
            return None
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def _list_memory_files(self) -> list[dict]:
        records = []
        if not self._memory_dir.exists():
            return records
        for path in sorted(self._memory_dir.glob("*.md")):
            if path.name == self._memory_index.name:
                continue
            try:
                path = self._memory_path(path.name)
            except ValueError:
                continue
            metadata, body = self._parse_frontmatter(path.read_text(encoding="utf-8"))
            records.append({
                "filename": path.name,
                "name": str(metadata.get("name") or path.stem),
                "description": str(metadata.get("description") or ""),
                "type": str(metadata.get("type") or "project"),
                "body": body.strip(),
            })
        return records

    # -- Memory Recall --

    def _select_relevant_memories(self, messages: list, max_items: int = 5) -> list[str]:
        """Select memories relevant to current context using keyword matching."""
        records = self._list_memory_files()
        if not records:
            return []

        # Get recent user messages as query
        query = self._recent_user_text(messages)
        if not query:
            return []

        # Simple keyword-based selection
        words = set(re.findall(r"[a-z0-9_]{3,}|[\u4e00-\u9fff]{2,}", query.lower()))
        ranked = []
        for record in records:
            catalog_text = f"{record['name']} {record['description']}".lower()
            score = sum(word in catalog_text for word in words)
            if score:
                ranked.append((score, record["filename"]))

        ranked.sort(key=lambda x: (-x[0], x[1]))
        return [filename for _, filename in ranked[:max_items]]

    def _recent_user_text(self, messages: list, max_turns: int = 3) -> str:
        turns = []
        for msg in reversed(messages):
            content = msg.content if hasattr(msg, "content") else str(msg)
            if isinstance(content, str) and content.strip():
                turns.append(content)
            if len(turns) == max_turns:
                break
        return "\n".join(reversed(turns))[:4000]

    def _load_memories(self, messages: list) -> str:
        """Load relevant memories as JSON."""
        loaded = []
        remaining = RECALL_CHAR_LIMIT

        for filename in self._select_relevant_memories(messages):
            content = self._read_memory_file(filename)
            if not content or remaining <= 0:
                continue
            recalled = content[:remaining]
            loaded.append({"source": filename, "content": recalled})
            remaining -= len(recalled)

        return json.dumps(loaded, ensure_ascii=False, indent=2) if loaded else ""

    # -- Memory Extraction --

    def _extract_memories(self, messages: list) -> int:
        """Extract durable knowledge from conversation. In production, this would call LLM."""
        # For now, this is a placeholder. Real implementation would:
        # 1. Get recent dialogue
        # 2. Call LLM to extract memories
        # 3. Validate and store
        return 0

    def _maybe_consolidate(self) -> int:
        """Consolidate memories when store grows large. In production, this would call LLM."""
        records = self._list_memory_files()
        if len(records) < CONSOLIDATE_THRESHOLD:
            return 0
        # Placeholder for consolidation logic
        return 0
