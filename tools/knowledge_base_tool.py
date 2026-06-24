"""Custom local knowledge-base search tool for CrewAI."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Type

from pydantic import BaseModel, Field

try:
    from crewai.tools import BaseTool
except ImportError:  # Supports older CrewAI installations.
    from crewai_tools import BaseTool


class KnowledgeBaseSearchInput(BaseModel):
    """Input schema for the local knowledge-base search."""

    query: str = Field(
        ...,
        description="The customer issue, ticket category, or policy topic to search for.",
    )


class KnowledgeBaseSearchTool(BaseTool):
    """Search support_policies.md without using the web."""

    name: str = "Local Knowledge Base Search"
    description: str = (
        "Searches the local knowledge/support_policies.md file and returns "
        "the most relevant support policy sections."
    )
    args_schema: Type[BaseModel] = KnowledgeBaseSearchInput
    knowledge_base_path: str = str(
        Path(__file__).resolve().parents[1] / "knowledge" / "support_policies.md"
    )

    def _run(self, query: str) -> str:
        """Return the most relevant policy sections for the search query."""
        path = Path(self.knowledge_base_path)

        if not path.exists():
            return f"Knowledge base file not found at: {path}"

        content = path.read_text(encoding="utf-8")
        sections = self._split_markdown_sections(content)

        if not sections:
            return "No policy sections were found in the knowledge base."

        query_terms = self._extract_terms(query)
        scored_sections = []

        for title, body in sections:
            section_text = f"{title} {body}".lower()
            score = sum(1 for term in query_terms if term in section_text)
            scored_sections.append((score, title, body))

        # Return the two best matches. If scores tie at zero, this still gives
        # the agent useful local policy context rather than failing silently.
        best_matches = sorted(scored_sections, key=lambda item: item[0], reverse=True)[:2]

        formatted_matches = []
        for score, title, body in best_matches:
            formatted_matches.append(
                f"## {title}\nRelevance score: {score}\n{body.strip()}"
            )

        return "\n\n".join(formatted_matches)

    @staticmethod
    def _split_markdown_sections(content: str) -> list[tuple[str, str]]:
        """Split the Markdown knowledge base into heading-based sections."""
        sections: list[tuple[str, str]] = []
        current_title = "General"
        current_lines: list[str] = []

        for line in content.splitlines():
            if line.startswith("## "):
                if current_lines:
                    sections.append((current_title, "\n".join(current_lines)))
                current_title = line.replace("## ", "", 1).strip()
                current_lines = []
            elif not line.startswith("# "):
                current_lines.append(line)

        if current_lines:
            sections.append((current_title, "\n".join(current_lines)))

        return sections

    @staticmethod
    def _extract_terms(query: str) -> set[str]:
        """Extract simple keyword terms for beginner-friendly local search."""
        stop_words = {
            "about",
            "after",
            "also",
            "and",
            "are",
            "but",
            "can",
            "for",
            "from",
            "have",
            "her",
            "him",
            "his",
            "how",
            "into",
            "issue",
            "message",
            "need",
            "not",
            "our",
            "she",
            "that",
            "the",
            "their",
            "this",
            "ticket",
            "was",
            "with",
            "you",
            "your",
        }
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]+", query.lower())
        return {word for word in words if len(word) > 2 and word not in stop_words}
