import frappe
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
from urllib.parse import urlparse, parse_qs


class YoutubeTranscriber:

    def __init__(self, api: YouTubeTranscriptApi = None):
        self.api = api or YouTubeTranscriptApi()
        self.logger = frappe.logger("os_lmsa", allow_site=True)

    def transcript(self, id: str, language: str = "it") -> str:
        """
        Extract transcript from YouTube subtitles.
        Does not download audio — uses available captions.
        """
        self.logger.info(f"Fetching transcript for video {id} (language={language})")
        text = self._transcript(id, language)
        if not text:
            self.logger.info(
                f"No transcript found for video {id} with language={language}, retrying without language"
            )
            text = self._transcript(id)
        if text:
            self.logger.info(f"Transcript fetched for video {id} ({len(text)} chars)")
        else:
            self.logger.warning(f"No transcript available for video {id}")
        return text if text is not None else ""

    def _transcript(self, id: str, language: str | None = "it") -> str | None:
        fetched_transcript = []
        try:
            if language:
                fetched_transcript = self.api.fetch(id, languages=[language])
            else:
                fetched_transcript = self.api.fetch(id)
        except NoTranscriptFound:
            return None

        text = ""
        if hasattr(fetched_transcript, "snippets") and isinstance(
            fetched_transcript.snippets, list
        ):
            for snippet in fetched_transcript.snippets:
                text += " " + snippet.text
        return text.strip()

    @staticmethod
    def extract_id(value: str) -> str:
        parsed = urlparse(value)
        # https://youtu.be/V4Pzs5wLKh0
        if parsed.netloc in ("youtu.be",):
            return parsed.path.lstrip("/").split("?")[0]
        if parsed.netloc in ("www.youtube.com", "youtube.com"):

            # /watch?v=VIDEO_ID
            if parsed.path == "/watch":
                params = parse_qs(parsed.query)
                return params.get("v", [None])[0]

            # /embed/VIDEO_ID
            if parsed.path.startswith("/embed/"):
                return parsed.path.split("/embed/")[1].split("?")[0]

        return None
