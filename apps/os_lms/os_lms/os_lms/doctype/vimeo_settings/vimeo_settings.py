# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import requests

import frappe
from frappe.model.document import Document


_token_cache: str | None = None


class VimeoSettings(Document):
	def validate(self):
		if self.enabled and not self.test_mode and not self.access_token:
			frappe.throw(
				"Personal Access Token richiesto se l'integrazione e' abilitata in "
				"modalita' produzione. Per testare senza token, attivare 'Enable Test Mode'."
			)
		if self.test_mode and not self.test_audio_url:
			frappe.throw("Test Audio URL richiesto quando Test Mode e' attivo.")
		if self.cache_ttl_seconds < 60 or self.cache_ttl_seconds > 21600:
			frappe.msgprint(
				"Cache TTL fuori range raccomandato (60-21600 secondi). "
				"Gli URL Vimeo scadono dopo ~6 ore.",
				indicator="orange",
				alert=True,
			)
		if self.api_timeout_seconds <= 0 or self.api_timeout_seconds > 30:
			frappe.throw("API timeout deve essere tra 1 e 30 secondi.")

		global _token_cache
		_token_cache = None

	def _resolve_token(self, token: str | None = None) -> str | None:
		if token:
			return token
		if not self.name:
			return None
		try:
			return self.get_password("access_token", raise_exception=False)
		except Exception:
			return None

	@frappe.whitelist()
	def test_connection(self, token: str | None = None):
		access_token = self._resolve_token(token)
		timeout = self.api_timeout_seconds or 5

		if not access_token:
			return self._record_test_result(False, "Token non configurato")

		try:
			response = requests.get(
				"https://api.vimeo.com/me",
				headers={"Authorization": f"Bearer {access_token}"},
				timeout=timeout,
			)
		except requests.Timeout:
			return self._record_test_result(
				False, f"Impossibile raggiungere api.vimeo.com: timeout dopo {timeout}s"
			)
		except requests.RequestException as exc:
			return self._record_test_result(False, f"Impossibile raggiungere api.vimeo.com: {exc}")

		if response.status_code == 200:
			data = response.json()
			name = data.get("name", "?")
			account = data.get("account", "?")
			total = (data.get("videos") or {}).get("total", "?")
			message = f"✓ Connessione OK. Account: {name} ({account}). Video: {total}"
			return self._record_test_result(True, message)

		if response.status_code == 401:
			return self._record_test_result(False, "Token non valido o revocato")

		if response.status_code == 403:
			return self._record_test_result(
				False,
				"Token senza permessi sufficienti. Verifica gli scopes (private, video_files).",
			)

		return self._record_test_result(
			False, f"Errore API Vimeo: HTTP {response.status_code}"
		)

	def _record_test_result(self, success: bool, message: str) -> dict:
		self.last_test_result = message
		self.last_test_at = frappe.utils.now()
		self.save(ignore_permissions=False)
		frappe.db.commit()
		return {"success": success, "message": message}


def get_vimeo_token(force_refresh: bool = False) -> str:
	"""Returns the Vimeo access token with in-memory caching.

	Raises frappe.ValidationError if integration is disabled or token is missing.
	"""
	global _token_cache
	if _token_cache is not None and not force_refresh:
		return _token_cache
	settings = frappe.get_single("Vimeo Settings")
	if not settings.enabled:
		frappe.throw("Integrazione Vimeo non abilitata in Vimeo Settings")
	token = settings.get_password("access_token")
	if not token:
		frappe.throw("Token Vimeo non configurato in Vimeo Settings")
	_token_cache = token
	return token
