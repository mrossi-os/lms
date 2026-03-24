# os_lms/utils/video_transcriber.py

import re
from os_lms.os_lms.doctype.lmsa_transcript_cache.lmsa_transcript_cache import (
    generate_uid,
)
import frappe
from .transcriber.youtube import YoutubeTranscriber
from .transcriber.vimeo import VimeoTranscriber


class VideoTranscriber:

    def transcribe(self, provider: str, id: str) -> str:
        cache = self._from_cache(provider, id)
        if cache is not None:
            return cache

        text = ""
        if provider == "youtube":
            text = self._from_youtube(id)
        if provider == "vimeo":
            text = self._from_vimeo(id)

        self._save_cache(provider, id, text)
        return ""

    def _from_cache(self, provider: str, id: str) -> str:
        cache = frappe.db.get_value(
            "LMSA Transcript Cache",
            {"name_key": generate_uid(provider, id)},
            ["transcript"],
            as_dict=True,
        )
        if not cache:
            return None
        print(f"Found cache for video {id}")
        return cache.transcript

    def _save_cache(self, provider: str, id: str, text: str):
        doc = frappe.get_doc(
            {
                "doctype": "LMSA Transcript Cache",
                "video_id": id,
                "source": provider,
                "video_title": "",
                "transcript": text,
                "name_key": generate_uid(provider, id),
            }
        )
        doc.insert()

    def _from_youtube(self, id: str) -> str:
        transcriber = YoutubeTranscriber()
        text = transcriber.transcript(id)
        return text

    def _from_vimeo(self, id: str) -> str:
        transcriber = VimeoTranscriber()
        text = transcriber.transcript(id)
        return text
