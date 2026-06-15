<script>
// Override that fixes the "Failed to resolve component: Button" warning emitted
// by the upstream FileUploader: it imports `Button` but never registers it in
// its Options API `components` option, so Vue 3 cannot resolve <Button> in the
// slot fallback template that ships with the component.
//
// We re-import the ORIGINAL via the dedicated Vite alias (defined in
// vite.config.js) — `import { FileUploader } from 'frappe-ui'` would loop back
// onto this override file via the osOverrideTheme plugin (infinite recursion).
import OriginalFileUploader from 'frappe-ui-fileuploader-original'
import { Button } from 'frappe-ui'

export default {
	...OriginalFileUploader,
	components: {
		...(OriginalFileUploader.components || {}),
		Button,
	},
}
</script>
