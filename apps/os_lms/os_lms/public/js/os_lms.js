// OS LMS - Custom Scripts

// The /me "Settings" box links to Frappe's Edit Profile web form, which is
// rendered without any back navigation. Inject a "back to Settings" link so
// users can return. (The Reset Password page adds its own link in its template.)
(function () {
	// The web form page ships an empty client-side message dict, so __() cannot
	// translate here; fall back to the document language for the label.
	var LABELS = { it: "Impostazioni", en: "Settings" };

	function backLabel() {
		var lang = (document.documentElement.getAttribute("lang") || "en").slice(0, 2);
		return LABELS[lang] || LABELS.en;
	}

	function addBackLink() {
		var path = window.location.pathname;
		if (path.indexOf("/update-profile") !== 0 && path.indexOf("/edit-profile") !== 0) {
			return;
		}

		// Insert inside the white header card so the link stays legible
		// regardless of the surrounding page background.
		var host =
			document.querySelector(".web-form-header") ||
			document.querySelector(".web-form-container");
		if (!host || host.querySelector(".oslms-back-link")) {
			return;
		}

		var link = document.createElement("a");
		link.href = "/me";
		link.className = "oslms-back-link";
		link.innerHTML =
			'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
			'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
			'<path d="M15 18l-6-6 6-6"/></svg>';
		link.appendChild(document.createTextNode(backLabel()));

		host.insertBefore(link, host.firstChild);
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", addBackLink);
	} else {
		addBackLink();
	}
})();
