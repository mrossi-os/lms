// Adds an "Export with Permissions" button to the Role form.
// Unlike the standard Desk export (Role record only), this downloads a JSON
// payload containing the Role plus its DocType permission matrix, ready to be
// imported via the matching button in the Role list view.
frappe.ui.form.on("Role", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("Export with Permissions"), () => {
			frappe.call({
				method: "os_lms.role_import_export.export_role",
				args: { role: frm.doc.name },
				freeze: true,
				freeze_message: __("Exporting role…"),
				callback(r) {
					if (!r.message) {
						return;
					}

					const blob = new Blob([JSON.stringify(r.message, null, 2)], {
						type: "application/json",
					});
					const url = URL.createObjectURL(blob);
					const link = document.createElement("a");
					link.href = url;
					link.download = `role-${frm.doc.name}.json`;
					document.body.appendChild(link);
					link.click();
					document.body.removeChild(link);
					URL.revokeObjectURL(url);
				},
			});
		});
	},
});
