import requests
import frappe
from urllib.parse import urlparse
import re


class VimeoTranscriber:

    def __init__(self):
        self.__apiKey = None

    @property
    def _apiKey(self) -> str:
        if self.__apiKey is None:
            settings = frappe.get_single("LMSA Settings")
            self.__apiKey = settings.vimeo_api_key
        return self.__apiKey

    def transcript(self, id: str) -> str:
        api_key = self._apiKey
        if not api_key:
            return ""

        # Ottieni i sottotitoli disponibili
        resp = requests.get(
            f"https://api.vimeo.com/videos/{id}/texttracks",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        tracks = resp.json()

        content = ""
        # Scarica il testo di una traccia
        for track in tracks["data"]:
            vtt_url = track["link"]
            vtt = requests.get(vtt_url).text
            content += self._extract_text_from_vtt(vtt) + "\n "
        return content

    def _extract_text_from_vtt(self, content: str) -> str:
        # Rimuove header WEBVTT
        content = re.sub(r"WEBVTT.*?\n\n", "", content, flags=re.DOTALL)
        content = re.sub(
            r"\d{2}:\d{2}:\d{2}\.\d{3}\s-->\s\d{2}:\d{2}:\d{2}\.\d{3}.*\n", "", content
        )
        content = re.sub(r"^\d+\s*$", "", content, flags=re.MULTILINE)
        content = re.sub(r"<[^>]+>", "", content)
        content = re.sub(r"\n{2,}", "\n", content).strip()
        return content

    @staticmethod
    def extract_id(value: str) -> str:
        parsed = urlparse(value)
        parts = [p for p in parsed.path.split("/") if p]
        return parts[-1] if parts else None
