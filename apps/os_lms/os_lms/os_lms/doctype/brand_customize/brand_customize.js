// Copyright (c) 2026, ELITE and contributors
// For license information, please see license.txt

const EXPORT_VERSION = 1;

frappe.ui.form.on("Brand Customize", {
	refresh(frm) {
		frm.add_custom_button(__("Export"), () => export_brand_settings(frm), __("Actions"));
		frm.add_custom_button(__("Import"), () => import_brand_settings(frm), __("Actions"));
		frm.add_custom_button(__("Reset Colors"), () => reset_colors(frm), __("Actions"));
		add_clear_icons(frm);
	},
});

// Color fieldnames only (theme and layout-only fields are excluded).
function get_color_fieldnames(frm) {
	return frm.meta.fields.filter((df) => df.fieldtype === "Color").map((df) => df.fieldname);
}

// Injects the clear-button styles once (needed for :hover, which inline styles can't do).
function ensure_clear_styles() {
	if (document.getElementById("brand-clear-styles")) return;
	const style = document.createElement("style");
	style.id = "brand-clear-styles";
	style.textContent = `
		.brand-clear-btn {
			display: inline-flex;
			align-items: center;
			justify-content: center;
			width: 20px;
			height: 20px;
			padding: 0;
			margin-left: 6px;
			border: 1px solid var(--border-color, #d1d8dd);
			border-radius: var(--border-radius, 6px);
			background: var(--control-bg, #f4f5f6);
			color: var(--ink-gray-6, #74808b);
			font-size: 13px;
			line-height: 1;
			cursor: pointer;
			vertical-align: middle;
			transition: background .15s, color .15s, border-color .15s;
		}
		.brand-clear-btn:hover {
			background: var(--surface-gray-3, #e8eaed);
			color: var(--ink-gray-8, #374151);
			border-color: var(--gray-400, #c0c6cc);
		}
		.brand-clear-btn:active { transform: scale(0.92); }
	`;
	document.head.appendChild(style);
}

// Adds a small "✕" button next to each Color field's label to clear that single value.
function add_clear_icons(frm) {
	ensure_clear_styles();
	for (const fieldname of get_color_fieldnames(frm)) {
		const field = frm.get_field(fieldname);
		const label = field && field.$wrapper && field.$wrapper.find(".clearfix").first();
		if (!label || !label.length || label.find(".brand-clear-btn").length) continue;

		const btn = $(
			`<button type="button" class="brand-clear-btn" title="${__("Clear value")}">✕</button>`
		);
		btn.on("click", () => frm.set_value(fieldname, ""));
		label.append(btn);
	}
}

function reset_colors(frm) {
	const color_fields = get_color_fieldnames(frm);
	frappe.confirm(
		__("This will clear all {0} colors. Continue?", [color_fields.length]),
		() => {
			for (const fieldname of color_fields) frm.set_value(fieldname, "");
			frappe.show_alert({ message: __("Colors cleared. Save to apply."), indicator: "orange" });
		}
	);
}

// Fieldnames that actually hold a value (skips Section/Column Break and other
// layout-only fieldtypes), so the export stays in sync as colors are added.
function get_data_fieldnames(frm) {
	return frm.meta.fields
		.filter((df) => !frappe.model.no_value_type.includes(df.fieldtype))
		.map((df) => df.fieldname);
}

function export_brand_settings(frm) {
	const data = {};
	for (const fieldname of get_data_fieldnames(frm)) {
		data[fieldname] = frm.doc[fieldname] ?? null;
	}

	const payload = {
		doctype: frm.doctype,
		version: EXPORT_VERSION,
		exported_on: frappe.datetime.now_datetime(),
		data,
	};

	const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
	const url = URL.createObjectURL(blob);
	const link = document.createElement("a");
	link.href = url;
	link.download = "brand-customize.json";
	document.body.appendChild(link);
	link.click();
	document.body.removeChild(link);
	URL.revokeObjectURL(url);
}

function import_brand_settings(frm) {
	const input = document.createElement("input");
	input.type = "file";
	input.accept = "application/json,.json";
	input.onchange = () => {
		const file = input.files && input.files[0];
		if (!file) return;

		const reader = new FileReader();
		reader.onload = () => {
			let payload;
			try {
				payload = JSON.parse(reader.result);
			} catch (e) {
				frappe.msgprint({
					title: __("Import Failed"),
					message: __("The selected file is not valid JSON."),
					indicator: "red",
				});
				return;
			}
			apply_brand_settings(frm, payload);
		};
		reader.readAsText(file);
	};
	input.click();
}

function apply_brand_settings(frm, payload) {
	// Accept both the wrapped export format and a flat fieldname -> value object.
	const data = payload && typeof payload.data === "object" ? payload.data : payload;
	if (!data || typeof data !== "object") {
		frappe.msgprint({
			title: __("Import Failed"),
			message: __("The file does not contain any brand settings."),
			indicator: "red",
		});
		return;
	}

	const valid = new Set(get_data_fieldnames(frm));
	const to_apply = Object.entries(data).filter(([fieldname]) => valid.has(fieldname));
	const skipped = Object.keys(data).filter((fieldname) => !valid.has(fieldname));

	if (!to_apply.length) {
		frappe.msgprint({
			title: __("Import Failed"),
			message: __("No matching brand settings were found in the file."),
			indicator: "red",
		});
		return;
	}

	frappe.confirm(
		__("This will overwrite the current brand settings with {0} value(s) from the file. Continue?", [
			to_apply.length,
		]),
		() => {
			for (const [fieldname, value] of to_apply) {
				frm.set_value(fieldname, value ?? "");
			}

			let message = __("Imported {0} setting(s). Review and Save to apply.", [to_apply.length]);
			if (skipped.length) {
				message += "<br>" + __("Ignored unknown field(s): {0}", [
					skipped.map(frappe.utils.escape_html).join(", "),
				]);
			}
			frappe.msgprint({
				title: __("Import Complete"),
				message,
				indicator: "green",
			});
		}
	);
}
