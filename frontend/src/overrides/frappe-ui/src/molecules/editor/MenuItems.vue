<template>
  <MenuItems v-bind="$attrs" :items="translateItems(items)" />
</template>

<script setup>
// Wrap-style override of frappe-ui's new editor MenuItems (frappe-ui/editor),
// the renderer shared by every menu of the new Editor: fixed toolbar, bubble,
// floating and table menus. The item labels come from frappe-ui in English
// with no translation hook, so this wrapper hands the ORIGINAL component
// translated copies of the items. It runs at render time (not in a computed
// or at module load) so labels follow the translations once they are loaded.
//
// The original is imported via the dedicated Vite alias (vite.config.js):
// a relative import would be re-routed by osOverrideTheme back onto this file.
import MenuItems from 'frappe-ui-menuitems-original'

defineOptions({ inheritAttrs: false })

defineProps({
  items: { type: Array, required: true },
})

function translateItem(item) {
  if (item.type === 'separator') return item
  if (item.type === 'group') {
    return {
      ...item,
      label: __(item.label),
      items: item.items.map(translateItem),
    }
  }
  const translated = { ...item, label: __(item.label) }
  if (item.getLabel) {
    translated.getLabel = (editor) => __(item.getLabel(editor))
  }
  return translated
}

function translateItems(items) {
  return items.map(translateItem)
}
</script>
