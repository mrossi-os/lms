<!--
  Override of frappe-ui's TextEditor LinkPopup.vue via the osOverrideTheme Vite
  plugin. Changes from the upstream component:
    1. Link anchor's text color: `text-ink-gray-700` -> `text-ink-gray-9`.
    2. Action tooltips translated (upstream hardcodes English).
  Keep this file in sync with
  node_modules/frappe-ui/src/components/TextEditor/components/LinkPopup.vue after
  any upstream frappe-ui bump.
-->
<template>
  <div
    class="p-2 w-72 flex items-center gap-2 bg-surface-base shadow-xl rounded"
  >
    <TextInput
      v-if="edit"
      ref="input"
      type="text"
      class="w-full"
      placeholder="https://example.com"
      v-model="_href"
      @keydown.enter="submitLink"
      @keydown.esc="$emit('close')"
    />
    <a
      v-else
      class="text-ink-gray-9 underline text-sm flex-1 truncate pl-1"
      :title="_href"
      :href="_href"
      target="_blank"
    >
      {{ _href }}
    </a>
    <div class="shrink-0 flex items-center gap-1.5 ml-auto">
      <template v-if="edit">
        <Button
          @click="submitLink"
          :tooltip="__('Conferma')"
          :icon="LucideCheck"
          variant="subtle"
        />
        <Button
          @click="props.href ? (edit = false) : $emit('updateHref', '')"
          :tooltip="__('Annulla')"
          :icon="LucideX"
          variant="subtle"
        />
      </template>
      <template v-else>
        <Button
          @click="copyLink"
          :tooltip="__('Copia')"
          :icon="LucideCopy"
          variant="subtle"
        />
        <Button
          @click="edit = true"
          :tooltip="__('Modifica')"
          :icon="LucidePencil"
          variant="subtle"
        />
        <Button
          :tooltip="__('Rimuovi')"
          variant="subtle"
          @click="$emit('updateHref', '')"
          :icon="Link2Off"
        />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, useTemplateRef, nextTick } from 'vue'
import { Button, TextInput } from 'frappe-ui'
import LucideCopy from '~icons/lucide/copy'
import LucideCheck from '~icons/lucide/check'
import LucidePencil from '~icons/lucide/pencil'
import LucideX from '~icons/lucide/x'
import Link2Off from '~icons/lucide/link-2-off'
import { isValidUrl } from '../../../../../../../node_modules/frappe-ui/src/utils/url-validation'

// LinkPopup is mounted by the Link extension through its OWN createApp()
// (node_modules/.../extensions/link/link-extension.ts) — a detached Vue app
// that does NOT inherit the main app's globalProperties.__. A bare `__()` in
// the template compiles to `_ctx.__`, which is undefined in that app instance
// → "u.__ is not a function". Bind the always-available global `window.__`
// (set once at boot in main.js) so the template resolves it regardless of app
// context.
const __ = window.__

const props = defineProps<{
  href: string
}>()

const emit = defineEmits<{
  (e: 'updateHref', href: string): void
  (e: 'close'): void
}>()

const _href = ref(props.href)
const input = useTemplateRef('input')
const edit = ref(!props.href)

const submitLink = () => {
  if (_href.value === '' || isValidUrl(_href.value)) {
    emit('updateHref', _href.value)
  }
}

const copyLink = async () => {
  if (_href.value) await navigator.clipboard.writeText(_href.value)
}

onMounted(async () => {
  await nextTick()
  if (input.value?.el) {
    input.value.el.focus()
    input.value.el.select()
  }
})
</script>
