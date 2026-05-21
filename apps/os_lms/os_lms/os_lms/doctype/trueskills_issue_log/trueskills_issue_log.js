frappe.ui.form.on("TrueSkills Issue Log", {
	refresh(frm) {
		if (frm.is_new()) return;

		const state = frm.doc.state;
		const indicator_map = {
			pending: "orange",
			needs_retry: "orange",
			issued: "green",
			failed: "red",
		};
		const color = indicator_map[state] || "gray";
		frm.page.set_indicator(__(state), color);

		if (state === "failed" || state === "needs_retry") {
			frm.add_custom_button(__("Retry emission"), () => {
				frappe.confirm(
					__(
						"This creates a NEW TrueSkills Issue Log and re-attempts the certificate emission. The current log is preserved for audit. Continue?"
					),
					() => {
						frappe
							.call({
								method: "os_lms.os_lms.trueskills.api.retry_emission",
								args: { issue_log: frm.doc.name },
							})
							.then((r) => {
								const result = r.message || {};
								if (result.ok) {
									frappe.show_alert({
										message: __("Retry queued."),
										indicator: "green",
									});
								} else {
									frappe.msgprint({
										title: __("Retry failed"),
										indicator: "red",
										message: result.error || __("Unknown error"),
									});
								}
							});
					}
				);
			});
		}
	},
});
