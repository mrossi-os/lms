// Opens a course completion certificate, choosing between the internal LMS
// Print Format PDF and the TrueSkills openbadge image.
//
// When a course issues via TrueSkills the openbadge replaces the internal PDF
// entirely: the "Get Certificate" / "View Certificate" actions and the profile
// certificate list open the badge PNG inline in a new tab. Because emission is
// asynchronous (enqueued on LMS Certificate creation), the badge may not be
// ready at click time — this composable pre-opens a tab, shows a spinner via
// `opening`, polls the issuance status, then navigates the tab to the image.
// Errors and a slow-issuance timeout surface as toasts.
import { ref } from 'vue'
import { call, toast } from 'frappe-ui'

const POLL_INTERVAL_MS = 1500
const POLL_MAX_ATTEMPTS = 20 // ~30s before giving up

function pdfUrl(name, template) {
	return (
		`/api/method/frappe.utils.print_format.download_pdf?doctype=LMS+Certificate` +
		`&name=${encodeURIComponent(name)}&format=${encodeURIComponent(
			template,
		)}&pdf_generator=chrome`
	)
}

function delay(ms) {
	return new Promise((resolve) => setTimeout(resolve, ms))
}

// Map stable TrueSkills error codes to learner-facing messages.
function trueskillErrorMessage(code) {
	const map = {
		missing_fiscal_id: __(
			'Codice fiscale mancante nel profilo. Contatta l\'amministrazione per emettere il certificato.',
		),
		invalid_recipient: __(
			'Dati del destinatario incompleti. Contatta l\'amministrazione.',
		),
		invalid_template_id: __(
			'Template del certificato non valido. Contatta l\'amministrazione.',
		),
		service_unavailable: __(
			'Il servizio certificati non è al momento disponibile. Riprova più tardi.',
		),
	}
	return map[code] || __('Impossibile aprire il certificato. Riprova più tardi.')
}

export function useCertificateViewer() {
	// True while an async open is in flight — bind to a button spinner.
	const opening = ref(false)

	function openLoadingTab() {
		// Open synchronously within the click gesture so popup blockers allow it;
		// navigate it once the artifact is ready (or close it on failure).
		const win = window.open('', '_blank')
		if (win) {
			win.document.write(
				`<!doctype html><meta charset="utf-8"><title>${__('Certificato')}</title>` +
					`<body style="margin:0;display:flex;height:100vh;align-items:center;` +
					`justify-content:center;font-family:system-ui,sans-serif;color:#555">` +
					`${__('Generazione del certificato in corso…')}</body>`,
			)
		}
		return win
	}

	function navigate(win, url) {
		if (win) win.location.href = url
		else window.open(url, '_blank')
	}

	function fail(win, err) {
		if (win) win.close()
		const code = err?.message
		if (code === 'timeout') {
			toast.error(
				__(
					'Il certificato sta impiegando più tempo del previsto. Riprova tra poco.',
				),
			)
		} else {
			toast.error(trueskillErrorMessage(code))
		}
	}

	async function openBadgeImage(win, trueskillId) {
		const params = new URLSearchParams({
			certificate_id: String(trueskillId),
			file_format: 'image',
		})
		const res = await fetch(
			`/api/method/os_lms.os_lms.trueskills.api.download?${params.toString()}`,
		)
		if (!res.ok) throw new Error('download_failed')
		const buf = await res.arrayBuffer()
		// Force image/png so the browser renders it inline instead of downloading.
		const blobUrl = URL.createObjectURL(new Blob([buf], { type: 'image/png' }))
		navigate(win, blobUrl)
	}

	async function pollUntilIssued(lmsCertificate) {
		for (let i = 0; i < POLL_MAX_ATTEMPTS; i++) {
			await delay(POLL_INTERVAL_MS)
			const status = await call(
				'os_lms.os_lms.trueskills.api.get_issue_status',
				{ lms_certificates: [lmsCertificate] },
			)
			const s = status?.[lmsCertificate]
			if (s?.issued && s.trueskill_id) return s
			if (s?.state === 'failed') throw new Error(s.error || 'failed')
		}
		throw new Error('timeout')
	}

	// Resolve a TrueSkills badge to the open tab, polling if not yet issued.
	// `status` may already carry the issuance state (avoids the first poll).
	async function handleTrueskill(win, lmsCertificate, status) {
		let s = status
		if (!s?.issued) {
			if (s?.state === 'failed') throw new Error(s.error || 'failed')
			if (s?.state === 'unavailable')
				throw new Error(s.error || 'service_unavailable')
			s = await pollUntilIssued(lmsCertificate)
		}
		await openBadgeImage(win, s.trueskill_id)
	}

	// Course flow: ensure the certificate exists, then open the right artifact.
	// Used by the "Get Certificate" and "View Certificate" buttons.
	async function openCourseCertificate(course) {
		if (!course || opening.value) return
		opening.value = true
		const win = openLoadingTab()
		try {
			const data = await call(
				'os_lms.os_lms.trueskills.api.get_course_certificate',
				{ course },
			)
			if (data.mode === 'trueskill') {
				await handleTrueskill(win, data.lms_certificate, data)
			} else {
				navigate(win, pdfUrl(data.lms_certificate, data.template))
			}
		} catch (err) {
			fail(win, err)
		} finally {
			opening.value = false
		}
	}

	// Existing-certificate flow (profile list): `status` is the pre-loaded bulk
	// TrueSkills status for this certificate (undefined for internal/batch certs).
	async function openIssuedCertificate({ name, template, status }) {
		if (opening.value) return
		// No TrueSkills log at all → internal PDF (synchronous, keeps the gesture).
		if (!status || (!status.issued && !status.state)) {
			window.open(pdfUrl(name, template), '_blank')
			return
		}
		opening.value = true
		const win = openLoadingTab()
		try {
			await handleTrueskill(win, name, status)
		} catch (err) {
			fail(win, err)
		} finally {
			opening.value = false
		}
	}

	return { opening, openCourseCertificate, openIssuedCertificate }
}
