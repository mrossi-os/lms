// Copyright (c) 2026, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on("LMSA Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Test Provider Connection"), () => run_provider_test(frm));
	},
});

function run_provider_test(frm) {
	frappe.dom.freeze(__("Testing providers..."));
	frappe
		.call({
			method: "os_lms.os_lms.ai.utils.llm.api.test_providers",
		})
		.always(() => frappe.dom.unfreeze())
		.then(({ message }) => {
			if (!message) {
				frappe.msgprint({ message: __("No response from server."), indicator: "red" });
				return;
			}
			const rows = (message.results || []).map((r) => render_row(r)).join("");
			const summary = `
				<p><strong>${__("Chat provider")}:</strong> ${frappe.utils.escape_html(message.chat_provider)} &nbsp;
				<strong>${__("Debrief provider")}:</strong> ${frappe.utils.escape_html(message.debrief_provider)} &nbsp;
				<strong>${__("Default")}:</strong> ${frappe.utils.escape_html(message.default_provider)}</p>
				<p><strong>${__("Fallback order")}:</strong> ${(message.fallback_order || [])
					.map(frappe.utils.escape_html)
					.join(" → ")}</p>
			`;
			frappe.msgprint({
				title: __("Provider health check"),
				indicator: "blue",
				message: `
					${summary}
					<table class="table table-bordered">
						<thead><tr><th>${__("Provider")}</th><th>${__("Status")}</th><th>${__("Detail")}</th></tr></thead>
						<tbody>${rows}</tbody>
					</table>
				`,
			});
		})
		.catch((err) => {
			frappe.msgprint({
				title: __("Provider test failed"),
				indicator: "red",
				message: err.message || String(err),
			});
		});
}

function render_row(r) {
	const indicators = {
		ok: "green",
		invalid_auth: "orange",
		not_configured: "gray",
		error: "red",
	};
	const color = indicators[r.status] || "gray";
	return `
		<tr>
			<td><code>${frappe.utils.escape_html(r.provider)}</code></td>
			<td><span class="indicator ${color}">${__(r.status)}</span></td>
			<td>${frappe.utils.escape_html(r.detail || "")}</td>
		</tr>
	`;
}
