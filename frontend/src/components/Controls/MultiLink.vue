<template>
	<div class="space-y-1.5">
		<FormLabel v-if="label" :label="label" :required="required" />
		<!-- OSLMS-CUSTOM: self-contained Popover + reka-ui Combobox instead of frappe-ui MultiSelect -->
		<Popover
			:show="popoverOpen"
			:matchTargetWidth="true"
			placement="bottom-start"
			@update:show="onPopoverToggle"
		>
			<template #target="{ togglePopover, isOpen }">
				<button
					type="button"
					:class="[
						triggerBaseClasses,
						triggerVariantClasses[variant],
						'min-h-7 rounded px-2 w-full justify-between text-base',
						disabled && 'cursor-not-allowed opacity-60',
					]"
					:data-state="isOpen ? 'open' : 'closed'"
					:disabled="disabled"
					@click="togglePopover"
				>
					<span class="flex min-w-0 flex-1 items-center gap-2">
						<slot name="prefix" :selected="selectedOptions" />
						<span
							class="min-w-0 flex-1 truncate text-left"
							:class="!selectedOptions.length && 'text-ink-gray-4'"
						>
							<slot
								name="summary"
								:summary="displayValue || placeholder"
								:selected="selectedOptions"
							>
								<template v-if="selectedOptions.length">{{
									defaultSummary(selectedOptions)
								}}</template>
								<template v-else>{{ placeholder }}</template>
							</slot>
						</span>
					</span>
					<ChevronDown
						class="size-4 shrink-0 text-ink-gray-4 transition-transform duration-200"
						:class="isOpen && 'rotate-180'"
					/>
				</button>
			</template>
			<template #body>
				<div
					class="rounded-lg border border-outline-gray-1 bg-surface-elevation-2 shadow-xl"
				>
					<!--
						`ignore-filter` disables reka's built-in client filtering: search
						is server-side via `reload(txt)`. `open` is hardcoded since the list
						is already mounted inside the (conditionally rendered) popover body.
					-->
					<ComboboxRoot
						v-model="value"
						multiple
						:open="true"
						:ignore-filter="true"
						class="p-2 pb-0"
						@update:modelValue="onChange"
					>
						<div
							class="flex w-full items-center justify-between gap-2 rounded bg-surface-gray-2 px-2 py-1 ring-2 ring-outline-gray-2 transition-colors hover:bg-surface-gray-3"
						>
							<ComboboxInput
								class="h-full w-full border-0 bg-transparent p-0 text-base text-ink-gray-8 placeholder:text-ink-gray-4 focus:border-0 focus:outline-0 focus:ring-0"
								:placeholder="__('Search...')"
								autocomplete="off"
								@input="onInput"
							/>
							<LoadingIndicator
								v-if="options.loading"
								class="size-4 shrink-0 text-ink-gray-5"
							/>
						</div>
						<ComboboxContent class="z-10 mt-2 overflow-hidden">
							<ComboboxViewport class="max-h-60 overflow-auto pb-1.5">
								<ComboboxEmpty
									class="px-2.5 py-1.5 text-center text-base text-ink-gray-5"
								>
									{{ __('No results found') }}
								</ComboboxEmpty>
								<ComboboxItem
									v-for="item in mergedOptions"
									:key="item.value"
									:value="item.value"
									:disabled="(item.disabled as boolean) || false"
									class="relative flex h-7 select-none items-center gap-2 rounded p-1.5 text-base leading-none text-ink-gray-7 data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[highlighted]:bg-surface-gray-3 data-[highlighted]:outline-none"
								>
									<slot name="item-prefix" :item="item" />
									<span class="min-w-0 flex-1 pr-6">
										<slot name="item-label" :item="item">
											{{ item.label }}
										</slot>
									</span>
									<ComboboxItemIndicator
										class="absolute right-1.5 inline-flex items-center justify-center"
									>
										<Check class="size-4" />
									</ComboboxItemIndicator>
								</ComboboxItem>
							</ComboboxViewport>
							<slot name="footer" :close="closePopover">
								<div
									class="mt-1 flex items-center justify-between gap-2 border-t border-outline-gray-1 px-2 py-1.5"
								>
									<Button
										variant="ghost"
										size="sm"
										:aria-label="__('Clear')"
										@click="clearAll"
									>
										{{ __('Clear') }}
									</Button>
									<Button
										v-if="props.onCreate"
										variant="ghost"
										size="sm"
										:aria-label="__(createLabel)"
										@click="handleCreate"
									>
										<template #prefix>
											<Plus class="size-4 stroke-1.5" />
										</template>
										{{ __(createLabel) }}
									</Button>
								</div>
							</slot>
						</ComboboxContent>
					</ComboboxRoot>
				</div>
			</template>
		</Popover>
	</div>
</template>

<script setup lang="ts">
import { Button, FormLabel, LoadingIndicator, Popover, createResource } from 'frappe-ui'
// OSLMS-CUSTOM: reka-ui primitives for the self-contained multi-select
import {
	ComboboxRoot,
	ComboboxInput,
	ComboboxContent,
	ComboboxViewport,
	ComboboxEmpty,
	ComboboxItem,
	ComboboxItemIndicator,
} from 'reka-ui'
import { useDebounceFn } from '@vueuse/core'
import { ChevronDown, Plus, Check } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import type { Resource } from '@/types'

interface SelectOption {
	label: string
	value: string
	description?: string
	[key: string]: unknown
}

type CloseFn = () => void

const props = withDefaults(
	defineProps<{
		doctype: string
		filters?: Record<string, unknown>
		url?: string
		searchParams?: Record<string, unknown>
		transform?: (rows: Record<string, unknown>[]) => SelectOption[]
		extraOptions?: SelectOption[]
		label?: string
		placeholder?: string
		required?: boolean
		disabled?: boolean
		variant?: 'subtle' | 'outline' | 'ghost'
		onCreate?: (close: CloseFn) => void
		createLabel?: string
	}>(),
	{
		filters: () => ({}),
		url: 'frappe.desk.search.search_link',
		searchParams: () => ({}),
		extraOptions: () => [],
		variant: 'subtle',
		createLabel: 'Create New',
	}
)

const value = defineModel<string[]>({ default: () => [] })

const popoverOpen = ref<boolean>(false)
let loaded = false

// OSLMS-CUSTOM: theme focus/open ring on the trigger (variants lose the bg/border swap)
const triggerBaseClasses =
	'relative inline-flex items-center gap-2 text-left text-ink-gray-7 outline-none transition-[background-color,border-color,box-shadow] duration-150 focus-visible:ring-2 data-[state=open]:ring-2 ring-outline-gray-3'

const triggerVariantClasses: Record<
	NonNullable<typeof props.variant>,
	string
> = {
	subtle:
		'border border-[--surface-gray-2] bg-surface-gray-2 hover:border-outline-elevation-2 hover:bg-surface-gray-3',
	outline:
		'border border-outline-gray-2 bg-surface-base hover:border-outline-gray-3',
	ghost:
		'border border-transparent bg-transparent hover:bg-surface-gray-3 focus-within:bg-surface-gray-3',
}

function buildParams(txt: string) {
	return {
		txt,
		doctype: props.doctype,
		filters: JSON.stringify(props.filters),
		...props.searchParams,
	}
}

function toOptions(data: Record<string, unknown>[]): SelectOption[] {
	if (props.transform) return props.transform(data)
	return data.map((o) => ({
		label:
			(o.label as string) || (o.value as string) || (o.name as string) || '',
		value: (o.value as string) || (o.name as string) || '',
		description: (o.description as string) || undefined,
	}))
}

const options = createResource({
	url: props.url,
	method: 'POST',
	auto: false,
	transform: toOptions,
}) as Resource<SelectOption[] | null>

function reload(txt: string = '') {
	loaded = true
	options.update({ params: buildParams(txt) })
	options.reload()
}

// Popover has no `open` event; load the initial list the first time it opens.
function onPopoverToggle(open: boolean) {
	popoverOpen.value = open
	if (open && !loaded) reload()
}

const onQuery = useDebounceFn((txt: string) => reload(txt || ''), 300)

// OSLMS-CUSTOM: server-side search driven by the reka ComboboxInput
function onInput(event: Event) {
	onQuery((event.target as HTMLInputElement).value)
}

const emit = defineEmits<{
	(e: 'change', value: string[]): void
}>()

function onChange(val: string[]) {
	emit('change', val)
}

function closePopover() {
	popoverOpen.value = false
}

function handleCreate() {
	props.onCreate?.(closePopover)
}

// Saved values need labels before the dropdown is ever opened: the search
// endpoint only returns query hits, so resolve them by name up front.
const resolved = ref<Map<string, SelectOption>>(new Map())

// Values this control has asked the endpoint to resolve. Anything else in the
// response is a search hit, not a resolution, and must not be treated as one.
const requested = new Set<string>()

const titleLookup = createResource({
	url: props.url,
	method: 'POST',
	auto: false,
	transform: toOptions,
	onSuccess: (rows: SelectOption[]) => {
		const next = new Map(resolved.value)
		for (const o of rows) {
			if (o.value && requested.has(o.value)) next.set(o.value, o)
		}
		resolved.value = next
	},
}) as Resource<SelectOption[] | null>

const mergedOptions = computed<SelectOption[]>(() => {
	const seen = new Set<string>()
	const out: SelectOption[] = []
	for (const o of options.data || []) {
		if (seen.has(o.value)) continue
		seen.add(o.value)
		out.push(o)
	}
	for (const o of props.extraOptions) {
		if (seen.has(o.value)) continue
		seen.add(o.value)
		out.push(o)
	}
	for (const o of resolved.value.values()) {
		if (seen.has(o.value)) continue
		seen.add(o.value)
		out.push(o)
	}
	// Last resort so a selection is never invisible: show the raw docname
	// for values the endpoint could not resolve.
	if (!titleLookup.loading) {
		for (const v of value.value) {
			if (seen.has(v)) continue
			seen.add(v)
			out.push({ label: v, value: v })
		}
	}
	return out
})

function resolveMissing(vals: string[]): void {
	const known = new Set<string>([
		...(options.data || []).map((o) => o.value),
		...props.extraOptions.map((o) => o.value),
		...resolved.value.keys(),
	])
	// Only fire for names we have never asked about; a name that was requested
	// but never came back (deleted/inaccessible doc) must not re-trigger a lookup
	// on every value change.
	const fresh = (vals || []).filter(
		(v) => v && !known.has(v) && !requested.has(v)
	)
	if (!fresh.length) return
	fresh.forEach((v) => requested.add(v))
	// Resolve everything still outstanding, not just the fresh names, so a
	// superseded in-flight request never drops names asked for earlier.
	const outstanding = [...requested].filter((v) => !resolved.value.has(v))
	titleLookup.update({
		params: {
			...buildParams(''),
			// Search endpoints spell "give me these exact docnames" differently and
			// Frappe drops kwargs a method does not declare, so send both spellings:
			// `filters` is honoured by frappe.desk.search.search_link, `names` by
			// lms.lms.api.search_users_by_role. Sending only `filters` degenerates
			// into an empty-txt search on the latter, which returns arbitrary rows.
			//
			// Resolution pins exact docnames, so props.filters is deliberately NOT
			// spread in: a caller filter like `published: 1` would wrongly drop a
			// selected value that no longer matches, leaving it labelled by docname.
			filters: JSON.stringify({ name: ['in', outstanding] }),
			names: JSON.stringify(outstanding),
			page_length: outstanding.length,
		},
	})
	titleLookup.reload()
}

watch(value, (vals) => resolveMissing(vals || []), { immediate: true })

const optionByValue = computed<Map<string, SelectOption>>(() => {
	const map = new Map<string, SelectOption>()
	mergedOptions.value.forEach((o) => map.set(o.value, o))
	return map
})

// OSLMS-CUSTOM: trigger summary computed here (MultiSelect used to provide it)
// Resolve currently selected values to full option objects (falling back to a
// bare {label,value} when an option hasn't been loaded yet) for the trigger.
const selectedOptions = computed<SelectOption[]>(() =>
	(value.value || []).map(
		(v) => optionByValue.value.get(v) || { label: v, value: v }
	)
)

const displayValue = computed<string>(() =>
	defaultSummary(selectedOptions.value)
)

function defaultSummary(selected: { label: string }[]) {
	return selected.map((o) => o.label).join(', ')
}

// OSLMS-CUSTOM: Clear footer action (MultiSelect used to provide it)
function clearAll() {
	value.value = []
	onChange([])
}

defineExpose({ reload, options, optionByValue })
</script>
