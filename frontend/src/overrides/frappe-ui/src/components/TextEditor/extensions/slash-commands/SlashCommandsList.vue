<!--
  Override of frappe-ui's TextEditor SlashCommandsList.vue via the
  osOverrideTheme Vite plugin. Changes from upstream:
    1. The slash-command title is wrapped in __() (titles come hardcoded in
       English from slash-commands-extension.ts).
    2. Imports repointed at the originals in node_modules (bare relative imports
       would resolve inside src/overrides and 404).
  Keep in sync with node_modules/.../slash-commands/SlashCommandsList.vue after
  any upstream frappe-ui bump.
-->
<template>
  <SuggestionList
    ref="suggestionList"
    :items="props.items"
    :command="(item) => onItemSelect(item as CommandItem)"
    container-class="min-w-48"
    item-class="h-7"
    :show-no-results="true"
  >
    <template #default="{ item }">
      <component :is="item.icon" v-if="item.icon" class="mr-2 h-4 w-4" />
      <div v-else class="mr-2 h-4 w-4"></div>
      <span>{{ __(item.title) }}</span>
    </template>
  </SuggestionList>
</template>

<script setup lang="ts">
import { ref, type PropType } from 'vue'
import SuggestionList from '../../../../../../../../node_modules/frappe-ui/src/components/TextEditor/extensions/suggestion/SuggestionList.vue'
import type { Editor, Range } from '@tiptap/core'
import type { CommandItem } from '../../../../../../../../node_modules/frappe-ui/src/components/TextEditor/extensions/slash-commands/slash-commands-extension'

const props = defineProps({
  items: {
    type: Array as PropType<CommandItem[]>,
    required: true,
  },
  editor: {
    type: Object as PropType<Editor>,
    required: true,
  },
  range: {
    type: Object as PropType<Range>,
    required: true,
  },
  command: {
    type: Function as PropType<(item: CommandItem) => void>,
    required: true,
  },
  query: String,
})

const suggestionList = ref<InstanceType<typeof SuggestionList> | null>(null)

const onItemSelect = (item: CommandItem) => {
  if (item) {
    props.command(item)
  }
}

const onKeyDown = ({ event }: { event: KeyboardEvent }) => {
  return suggestionList.value?.onKeyDown({ event }) ?? false
}

defineExpose({
  onKeyDown,
})
</script>
