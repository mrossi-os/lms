// Copyright (c) 2026, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on("Vimeo Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Test Connection"), () => {
			const token = frm.doc.access_token;
			frm.call({
				doc: frm.doc,
				method: "test_connection",
				args: { token: token && !token.startsWith("*") ? token : null },
				freeze: true,
				freeze_message: __("Testing Vimeo connection..."),
			}).then((r) => {
				const result = r.message || {};
				const indicator = result.success ? "green" : "red";
				frappe.show_alert({ message: result.message || __("No response"), indicator });
				frm.reload_doc();
			});
		});
	},
});
