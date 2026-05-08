"""Export chronicle content to documentation systems."""

from __future__ import annotations

import json
from html import escape

from changelogagent.core.models import ChronicleEntry, NarrativeBlock
from changelogagent.summarizer.summarizer import Summarizer


class ChronicleExporter:
    """Markdown, HTML, PDF, Confluence, and Notion exports."""

    def export(self, entry: ChronicleEntry, narratives: list[NarrativeBlock], *, fmt: str) -> str | bytes | dict[str, object]:
        fmt = fmt.lower()
        if fmt in {"markdown", "html", "json"}:
            return Summarizer().export(entry, narratives, fmt=fmt)
        markdown = Summarizer().export(entry, narratives, fmt="markdown")
        if fmt == "pdf":
            return self._minimal_pdf(entry.title, markdown)
        if fmt == "confluence":
            return {
                "type": "page",
                "title": entry.title,
                "body": {"storage": {"value": self._storage_html(entry, narratives), "representation": "storage"}},
            }
        if fmt == "notion":
            return {
                "parent": {},
                "properties": {"title": {"title": [{"text": {"content": entry.title}}]}},
                "children": [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": line[:1900]}}]}} for line in markdown.splitlines() if line.strip()],
            }
        raise ValueError("fmt must be markdown, html, json, pdf, confluence, or notion")

    @staticmethod
    def _storage_html(entry: ChronicleEntry, narratives: list[NarrativeBlock]) -> str:
        paragraphs = "".join(f"<p>{escape(block.text)}</p>" for block in narratives if block.id in entry.narratives)
        return f"<h1>{escape(entry.title)}</h1><p>{escape(entry.summary)}</p>{paragraphs}"

    @staticmethod
    def _minimal_pdf(title: str, text: str) -> bytes:
        # Minimal valid-enough PDF for integrations that require a document blob.
        body = f"BT /F1 12 Tf 72 720 Td ({_pdf_escape(title)}) Tj 0 -18 Td ({_pdf_escape(text[:900])}) Tj ET"
        objects = [
            "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
            "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
            "3 0 obj << /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >> endobj",
            "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
            f"5 0 obj << /Length {len(body)} >> stream\n{body}\nendstream endobj",
        ]
        payload = "%PDF-1.4\n" + "\n".join(objects) + "\ntrailer << /Root 1 0 R >>\n%%EOF\n"
        return payload.encode("latin-1", "replace")


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").replace("\n", " ")
