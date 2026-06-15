<template>
  <TextEditor v-bind="$attrs" class="os-editor-wrapper" />
</template>

<script setup>
// Import the ORIGINAL frappe-ui TextEditor via the dedicated Vite alias
// (defined in vite.config.js). We must NOT `import { TextEditor } from 'frappe-ui'`
// here: the osOverrideTheme plugin would re-route that import back onto THIS
// override file, causing infinite render recursion. The alias points straight
// at the real component file, bypassing the plugin.
//
// We only add a stable `os-editor-wrapper` marker class to the editor root (same
// approach as the Switch override) so the elite theme can style the editor — most
// notably the fixed-menu toolbar (`.rounded-t-lg`) — without forking the whole
// component. No extra wrapper <div> is added, so layout at the ~19 call sites is
// untouched.
import TextEditor from 'frappe-ui-texteditor-original'

defineOptions({
  inheritAttrs: false,
})
</script>
