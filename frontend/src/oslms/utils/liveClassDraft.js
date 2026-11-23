// Draft live classes: every class is saved as a draft and announced only when it is
// published (os_lms live_class_draft.py / api.publish_live_class).
import { call, toast } from 'frappe-ui'
import { createDialog } from '@/utils/dialogs'

export const LIVE_CLASS_DRAFT = 'Draft'

export const isDraftLiveClass = (cls) => cls?.status === LIVE_CLASS_DRAFT

/**
 * Ask for confirmation, then publish the class. Publishing emails the whole batch at
 * once and cannot be taken back, hence the dialog.
 *
 * `beforePublish` (optional, async) runs first — the edit form saves pending changes
 * there, so the invitation carries them; returning false stops without publishing. `onPublished` runs after a successful publish.
 */
export function confirmPublishLiveClass(
	cls,
	{ beforePublish, onPublished } = {},
) {
	let publishing = false
	createDialog({
		title: __('Publish live class'),
		message: __(
			'Publish {0}? Everyone in the batch receives the invitation email and a notification right away.',
		).format(cls.title),
		actions: [
			{
				label: __('Publish'),
				variant: 'solid',
				async onClick({ close }) {
					// A second click while the first publish runs would only be refused by
					// the server; ignore it here.
					if (publishing) return
					publishing = true
					try {
						// false: the caller could not get ready and has told the user why
						if (
							beforePublish &&
							(await beforePublish()) === false
						) {
							close()
							return
						}
						await call('os_lms.os_lms.api.publish_live_class', {
							name: cls.name,
						})
						toast.success(
							__(
								'Live class published: the invitations are on their way',
							),
						)
						close()
						onPublished?.()
					} catch (err) {
						toast.error(
							err?.messages?.[0] || err?.message || String(err),
						)
					} finally {
						publishing = false
					}
				},
			},
		],
	})
}
