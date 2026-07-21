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

// The Edit Profile web form renders the "Profile Picture" (user_image) field
// with Frappe's stock "Attach Image" control: it shows the file URL as a link
// with no obvious upload button, and the image itself is only visible on hover.
// Replace that control's input area with a clearer widget — an always-visible
// preview, an Upload/Change button and a Remove button — while writing the
// value straight back into the web form so its own Save button persists it.
(function () {
	// The web form ships an empty client-side message dict, so __() cannot
	// translate here; fall back to the document language like the back link.
	var LABELS = {
		// Frappe ships no Italian translation for the "Profile Picture" field
		// label (every other field on the form is translated), and __() cannot
		// help with a string absent from the page message dict — translate it
		// here with the same lang map the back link uses.
		label: { it: "Foto profilo", en: "Profile Picture" },
		upload: { it: "Carica immagine", en: "Upload image" },
		change: { it: "Cambia immagine", en: "Change image" },
		remove: { it: "Elimina", en: "Remove" },
		empty: { it: "Nessuna immagine", en: "No image" },
	};

	function t(key) {
		var lang = (document.documentElement.getAttribute("lang") || "en").slice(0, 2);
		var entry = LABELS[key] || {};
		return entry[lang] || entry.en || key;
	}

	function onProfilePage() {
		var path = window.location.pathname;
		return path.indexOf("/update-profile") === 0 || path.indexOf("/edit-profile") === 0;
	}

	function getField() {
		return window.frappe && frappe.web_form && frappe.web_form.fields_dict
			? frappe.web_form.fields_dict.user_image
			: null;
	}

	function currentValue() {
		var wf = window.frappe && frappe.web_form;
		return (wf && wf.doc && wf.doc.user_image) || "";
	}

	function enhance(field) {
		var wrapper = field.$wrapper && field.$wrapper.get(0);
		if (!wrapper || wrapper.querySelector(".oslms-avatar-field")) {
			return;
		}

		// Hide the stock control (URL link + Attach/Clear/Reload buttons). The
		// value still lives on the field object and drives the web form's Save.
		var nativeInput = wrapper.querySelector(".control-input-wrapper");
		if (nativeInput) {
			nativeInput.style.display = "none";
		}

		// Translate the field label (untranslated by Frappe for Italian).
		var labelEl = wrapper.querySelector(".control-label");
		if (labelEl) {
			labelEl.textContent = t("label");
		}

		var container = document.createElement("div");
		container.className = "oslms-avatar-field";
		container.innerHTML =
			'<div class="oslms-avatar-preview"></div>' +
			'<div class="oslms-avatar-actions">' +
			'<button type="button" class="btn btn-default btn-sm oslms-avatar-upload"></button>' +
			'<button type="button" class="btn btn-default btn-sm oslms-avatar-remove"></button>' +
			"</div>";
		(wrapper.querySelector(".form-group") || wrapper).appendChild(container);

		var preview = container.querySelector(".oslms-avatar-preview");
		var uploadBtn = container.querySelector(".oslms-avatar-upload");
		var removeBtn = container.querySelector(".oslms-avatar-remove");
		removeBtn.textContent = t("remove");

		function render() {
			var url = currentValue();
			if (url) {
				preview.innerHTML = '<img alt="" />';
				preview.querySelector("img").setAttribute("src", url);
				uploadBtn.textContent = t("change");
				removeBtn.style.display = "";
			} else {
				preview.innerHTML = '<span class="oslms-avatar-placeholder"></span>';
				preview.querySelector(".oslms-avatar-placeholder").textContent = t("empty");
				uploadBtn.textContent = t("upload");
				removeBtn.style.display = "none";
			}
		}

		// Keep the field value and the web form doc in sync. Setting the doc
		// value directly matters for removal: get_values() drops empty values,
		// so an empty string on the doc is what makes Save clear the image
		// (the backend also deletes the previously attached file).
		//
		// IMPORTANT: do NOT call field.set_input() here. On this web form the
		// Attach Image control's make_input() never populated its $input/$value,
		// so ControlAttach.set_input() falls into its `else` branch and does
		// `this.$wrapper.html(...)`, wiping the entire field wrapper — including
		// our injected widget — and replacing it with a bare link that shows the
		// raw file URL instead of the image. Save reads field.value (get_value)
		// and frappe.web_form.doc.user_image, both set below, so set_input is
		// not needed for persistence — only destructive here.
		function apply(url) {
			var value = url || null;
			field.value = value;
			if (window.frappe && frappe.web_form && frappe.web_form.doc) {
				frappe.web_form.doc.user_image = value || "";
			}
			if (window.frappe && frappe.web_form && frappe.web_form.make_form_dirty) {
				frappe.web_form.make_form_dirty();
			}
			render();
		}

		uploadBtn.addEventListener("click", function () {
			new frappe.ui.FileUploader({
				allow_multiple: false,
				make_attachments_public: 1,
				restrictions: { allowed_file_types: ["image/*"] },
				on_success: function (file) {
					if (file && file.file_url) {
						apply(file.file_url);
					}
				},
			});
		});

		removeBtn.addEventListener("click", function () {
			apply("");
		});

		render();
	}

	function init() {
		if (!onProfilePage()) {
			return;
		}
		var tries = 0;
		var timer = setInterval(function () {
			tries += 1;
			var field = getField();
			if (field && field.$wrapper && field.$wrapper.get(0)) {
				clearInterval(timer);
				enhance(field);
			} else if (tries > 120) {
				// Give up after ~18s; the web form never rendered the field.
				clearInterval(timer);
			}
		}, 150);
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
