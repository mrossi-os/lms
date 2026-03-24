# os_lms/utils/lesson_parser.py

import json
from typing import Any
from .video_transcriber import VideoTranscriber


class LessonContentParser:

    def __init__(self, lesson):
        """
        lesson:
        """
        self.lesson = lesson
        self.blocks: list[dict] = self._decode_content(
            "content"
        ) + self._decode_content("instructor_content")

    # ------------------------------------------------------------------
    # Decode
    # ------------------------------------------------------------------

    def _decode_content(self, attribute: str) -> list[dict]:
        """Read lesson attribute and extract block."""
        raw = getattr(self.lesson, attribute, None)

        if not raw:
            return []

        if isinstance(raw, list):
            return raw

        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed.get("blocks", [])
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass

        return []

    # ------------------------------------------------------------------
    # Block type dispatcher
    # ------------------------------------------------------------------

    def _parse_block(self, block: dict) -> str:
        """Dispatch each block to the correct handler based on its type."""
        block_type = block.get("type", "")
        data = block.get("data", {})

        handlers = {
            "paragraph": self._parse_paragraph,
            "header": self._parse_header,
            "list": self._parse_list,
            "quote": self._parse_quote,
            "code": self._parse_code,
            "image": self._parse_image,
            "embed": self._parse_embed,
        }

        handler = handlers.get(block_type, self._parse_unknown)
        return handler(data)

    # ------------------------------------------------------------------
    # Handlers for each type
    # ------------------------------------------------------------------

    def _parse_paragraph(self, data: dict) -> str:
        return data.get("text", "")

    def _parse_header(self, data: dict) -> str:
        level = data.get("level", 1)
        text = data.get("text", "")
        return f"[H{level}] {text}"

    def _parse_list(self, data: dict) -> str:
        items = data.get("items", [])
        return "\n".join(f"- {item}" for item in items)

    def _parse_quote(self, data: dict) -> str:
        text = data.get("text", "")
        caption = data.get("caption", "")
        result = f'"{text}"'
        if caption:
            result += f" — {caption}"
        return result

    def _parse_code(self, data: dict) -> str:
        # you may choose to exclude code from text extraction
        return data.get("code", "")

    def _parse_image(self, data: dict) -> str:
        # images have no text, but we can extract the caption
        return data.get("caption", "")

    def _parse_embed(self, data: dict) -> str:
        provider = data.get("service", "")
        source = data.get("embed", "")
        caption = data.get("caption", "")

        if not source or not provider:
            return caption

        transcriber = VideoTranscriber()
        text = transcriber.transcribe(provider, source)

        return caption + " " + text

    def _parse_unknown(self, data: dict) -> str:
        return data.get("text", "")

    def extract_text(self, separator: str = "\n\n") -> str:
        """
        Iterate all blocks, extract text and return it
        as a single string joined by `separator`.
        """
        parts = []
        body = getattr(self.lesson, "body", "")
        if body is not None:
            parts.append(body)

        for block in self.blocks:
            text = self._parse_block(block)
            if text and text.strip():
                parts.append(text.strip())
        return separator.join(parts)
