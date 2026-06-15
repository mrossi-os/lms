<template>
  <Switch v-bind="$attrs" class="component-switch" />
</template>

<script setup>
// Import the ORIGINAL frappe-ui Switch via the dedicated Vite alias
// (defined in vite.config.js). We must NOT `import { Switch } from 'frappe-ui'`
// here: the osOverrideTheme plugin would re-route that import back onto THIS
// override file, causing infinite render recursion. The alias points straight
// at the real component file, bypassing the plugin.
import Switch from 'frappe-ui-switch-original'

defineOptions({
  inheritAttrs: false,
})
</script>