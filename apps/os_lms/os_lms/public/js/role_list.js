// Adds an "Import with Permissions" button to the Role list view.
// Reads a JSON file produced by the "Export with Permissions" button and
// recreates the Role together with its DocType permission matrix.
frappe.listview_settings["Role"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Import with Permissions"), () => {
			const input = document.createElement("input");
			input.type = "file";
			input.accept = ".json,application/json";

			input.onchange = (event) => {
				const file = event.target.files && event.target.files[0];
				if (!file) {
					return;
				}

				const reader = new FileReader();
				reader.onload = (loaded) => {
					let payload;
					try {
						payload = JSON.parse(loaded.target.result);
					} catch (e) {
						frappe.msgprint({
							title: __("Invalid file"),
							message: __("The selected file is not valid JSON."),
							indicator: "red",
						});
						return;
					}

					frappe.call({
						method: "os_lms.role_import_export.import_role",
						args: { data: JSON.stringify(payload) },
						freeze: true,
						freeze_message: __("Importing role…"),
						callback(r) {
							if (!r.message) {
								return;
							}

							frappe.show_alert(
								{
									message: __("Role {0} imported ({1} permissions, {2} skipped)", [
										r.message.role,
										r.message.applied_count,
										r.message.skipped_count,
									]),
									indicator: "green",
								},
								7
							);

							if (r.message.skipped_count) {
								const rows = r.message.skipped
									.map((s) => `<li>${frappe.utils.escape_html(s.doctype || "?")} — ${s.reason}</li>`)
									.join("");
								frappe.msgprint({
									title: __("Skipped permissions"),
									message: `<ul>${rows}</ul>`,
									indicator: "orange",
								});
							}

							listview.refresh();
						},
					});
				};

				reader.readAsText(file);
			};

			input.click();
		});
	},
};
