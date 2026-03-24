import requests
import frappe


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

        # Scarica il testo di una traccia
        for track in tracks["data"]:
            vtt_url = track["link"]
            vtt = requests.get(vtt_url).text
            print(vtt)
        return ""
