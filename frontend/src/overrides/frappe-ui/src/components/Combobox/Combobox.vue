<template>
  <Combobox
    ref="inner"
    v-bind="$attrs"
    :empty-text="translatedEmptyText"
    :placeholder="translatedPlaceholder"
  >
    <template v-for="(_, name) in $slots" #[name]="slotProps">
      <slot :name="name" v-bind="slotProps ?? {}" />
    </template>
  </Combobox>
</template>

<script setup>
// Wrap-style override (same pattern as Switch / TextEditor): the only change
// from upstream is that the empty-state text and the placeholder go through __(). Since
// 1.0.0-beta.29 that text is the `emptyText` prop (default 'No results'), so the
// ORIGINAL component is used as-is and upstream fixes arrive with every bump.
//
// The original is imported via the dedicated Vite alias (vite.config.js):
// `import { Combobox } from 'frappe-ui'` would be re-routed by osOverrideTheme
// back onto this file, causing infinite render recursion.
import Combobox from 'frappe-ui-combobox-original'
import { computed, ref, useAttrs } from 'vue'

defineOptions({ inheritAttrs: false })

const attrs = useAttrs()
const inner = ref(null)

const translatedEmptyText = computed(() =>
  __(attrs.emptyText ?? attrs['empty-text'] ?? 'No results'),
)

// Same for the placeholder: callers usually pass an already translated one
// (__() of Italian text returns it unchanged); the frappe-ui default is English.
const translatedPlaceholder = computed(() =>
  __(attrs.placeholder ?? 'Select option'),
)

// Keep the component's public methods reachable through a ref on the wrapper.
defineExpose({
  clear: () => inner.value?.clear(),
  focus: () => inner.value?.focus(),
})
</script>
