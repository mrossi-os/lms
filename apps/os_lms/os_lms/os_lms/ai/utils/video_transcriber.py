# os_lms/utils/video_transcriber.py

import re
from os_lms.os_lms.doctype.lmsa_transcript_cache.lmsa_transcript_cache import (
    generate_uid,
)
import frappe


class VideoTranscriber:

    def transcribe(self, provider: str, id: str) -> str:
        if provider == "youtube":
            return self._from_youtube(id, "it")
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

    def _from_youtube(self, id: str, language: str) -> str:
        """
        Estrae la trascrizione dai sottotitoli YouTube.
        Non scarica l'audio — usa i sottotitoli già disponibili.
        languages: lista di lingue preferite, es. ["it", "en"]
        """
        cache = self._from_cache("youtube", id)
        if cache is not None:
            return cache

        from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound

        print(f"Load transcript from youtube video {id}")

        text = ""
        fetched_transcript = []
        try:
            ytt_api = YouTubeTranscriptApi()
            fetched_transcript = ytt_api.fetch(id, languages=[language])

        except NoTranscriptFound:
            print(f"No transcripiton found for video {id} in {language} check default")
            fetched_transcript = ytt_api.fetch(id)

        if hasattr(fetched_transcript, "snippets") and isinstance(
            fetched_transcript.snippets, list
        ):
            for snippet in fetched_transcript.snippets:
                text += " " + snippet.text
        text = text.strip()
        self._save_cache("youtube", id, text)
        return text
