<!--
  Full-copy override of frappe-ui's frappe/Link/Link.vue (synced with
  1.0.0-beta.29). Only diffs vs the original:
    1. search_link goes through our resourceFetcher, which narrows a DocType
       link to the LMS doctypes (see plugins/resourceFetcherPlugin.js).
    2. A DocType link shows translated labels: doctype names are interface
       labels, every other link lists records whose values must stay verbatim.
    3. Imports rewritten: osOverrideTheme does not re-route imports made BY an
       override, so relative paths would resolve inside src/overrides and 404.
  Keep this file in sync with node_modules/frappe-ui/frappe/Link/Link.vue after
  every frappe-ui bump.
-->
<template>
  <div data-slot="link" class="contents">
    <Combobox
      ref="comboboxRef"
      v-bind="$attrs"
      v-model="model"
      v-model:open="open"
      class="group !gap-1"
      :label="label"
      :description="description"
      :error="error"
      :required="required"
      :id="id"
      :options="linkOptions"
      :disabled="disabled"
      :placeholder="placeholder ?? `Search ${doctype.toLowerCase()}`"
      :loading="options.loading && !options.data"
      @update:query="handleInputChange"
      @focus="() => loadOptions('')"
    >
      <template
        v-for="(_, name) in forwardedSlots"
        #[name]="slotProps"
        :key="name"
      >
        <slot :name="name" v-bind="slotProps" />
      </template>

      <template v-if="slots.suffix" #suffix="suffixProps">
        <slot name="suffix" v-bind="suffixProps" />
      </template>
      <template v-else-if="showClear" #suffix>
        <button
          type="button"
          aria-label="Clear"
          data-slot="clear"
          class="group-hover:grid group-focus:grid group-focus-within:grid hidden size-4 place-items-center rounded-sm text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-7 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
          @click="clearValue"
          @pointerdown.stop
        >
          <span class="lucide-x size-3.5" />
        </button>
      </template>

      <template v-if="slots['item-create']" #item-create="slotProps">
        <slot name="item-create" v-bind="slotProps" />
      </template>
      <template v-else #item-create="{ query }">
        <div class="flex">
          <span class="truncate">
            Create
            <span v-if="query" class="font-medium text-ink-gray-8">
              {{ query }}
            </span>
          </span>
        </div>
      </template>
    </Combobox>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, useSlots, watch } from 'vue'
// @ts-ignore
import { Combobox, createResource, debounce } from 'frappe-ui'
import type {
  ComboboxCustomOption,
  ComboboxOption,
} from '../../../../../node_modules/frappe-ui/src/components/Combobox/types'
import type {
  LinkEmits,
  LinkExposed,
  LinkOption,
  LinkProps,
} from '../../../../../node_modules/frappe-ui/frappe/Link/types'
import { resourceFetcher } from '@/plugins/resourceFetcherPlugin'

const props = withDefaults(defineProps<LinkProps>(), {
  filters: () => ({}),
  creatable: false,
  disabled: false,
})

const model = defineModel<string | null>({ default: null })
const open = defineModel<boolean>('open', { default: false })
const comboboxRef = ref<{ focus: () => void } | null>(null)

const emit = defineEmits<LinkEmits>()

defineOptions({ inheritAttrs: false })

const slots = useSlots()

const forwardedSlots = computed(() =>
  Object.fromEntries(
    Object.entries(slots).filter(
      ([name]) => name !== 'suffix' && name !== 'item-create',
    ),
  ),
)

const options = createResource({
  url: 'frappe.desk.search.search_link',
  params: {
    doctype: props.doctype,
    txt: '',
    filters: props.filters,
  },
  method: 'POST',
  resourceFetcher: resourceFetcher,
  transform: (data: LinkOption[]): LinkOption[] =>
    data.map((doc: any) => ({
      label: doc.label || doc.value,
      value: doc.value,
      description: doc.description,
    })),
})

const createNewOption: ComboboxCustomOption = {
  type: 'custom',
  key: 'create',
  label: 'Create New',
  slot: 'create',
  condition: ({ query }: { query: string }) => Boolean(query.trim()),
  onClick: ({ query }) => emit('create', query),
}

const linkOptions = computed<ComboboxOption[]>(() => {
  let _options = options.data || []
  // A DocType link lists doctype names, which are interface labels and have
  // translations; every other link lists records, whose values are data and
  // must stay verbatim. Note the server still searches the untranslated name.
  if (props.doctype === 'DocType') {
    _options = _options.map((option: any) => ({
      ...option,
      label: __(option.label),
    }))
  }
  if (props.creatable) {
    return [..._options, createNewOption]
  }
  return _options
})

const showClear = computed(
  () => !props.disabled && !!model.value && !props.required,
)

const loadOptions = (txt: string = '') => {
  options.update({
    params: {
      txt,
      doctype: props.doctype,
      filters: props.filters,
    },
  })
  options.reload()
}

const handleInputChange = debounce((value: string) => {
  loadOptions(value || '')
}, 300)

// The last keystroke leaves a search scheduled 300ms out. Without this it
// still fires after the component is gone — a wasted request whose rejection
// has nobody left to handle it.
onBeforeUnmount(() => handleInputChange.cancel())

const clearValue = () => {
  model.value = null
  open.value = false
  comboboxRef.value?.focus()
}

watch([() => props.doctype, () => props.filters], () => loadOptions(''), {
  immediate: true,
  deep: true,
})

defineExpose<LinkExposed>({ reload: () => loadOptions('') })
</script>
