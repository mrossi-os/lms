<template>
	<div class="space-y-3">
		<div class="text-xs text-ink-gray-5">
			{{ __('Tags') }}
		</div>

		<!-- Selected tags -->
		<div class="flex items-center flex-wrap gap-2 min-h-[32px]">
			<span
				v-for="tag in selectedTagObjects"
				:key="tag.tag_name"
				class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium text-white"
				:style="{ backgroundColor: tag.color }"
			>
				{{ tag.tag_name }}
				<button
					class="hover:opacity-70 transition-opacity"
					@click="removeTag(tag.tag_name)"
				>
					<X class="w-3 h-3" />
				</button>
			</span>
			<span v-if="!selectedTags.length" class="text-xs text-ink-gray-4 italic">
				{{ __('No tags selected') }}
			</span>
		</div>

		<div class="flex items-center gap-2">
			<!-- Add existing tag to course -->
			<Popover placement="bottom-start">
				<template #target="{ togglePopover }">
					<Button variant="outline" size="sm" @click="togglePopover()">
						<template #prefix>
							<Plus class="w-3.5 h-3.5" />
						</template>
						{{ __('Add Tag') }}
					</Button>
				</template>

				<template #body="{ close }">
					<div class="bg-surface-white border rounded-lg shadow-lg w-64 p-2">
						<FormControl
							v-model="searchQuery"
							:placeholder="__('Search tags...')"
							class="mb-2 small-form"
						/>

						<div class="max-h-48 overflow-y-auto space-y-1">
							<div
								v-for="tag in filteredAvailableTags"
								:key="tag.tag_name"
								class="flex items-center px-2 py-1.5 rounded cursor-pointer hover:bg-surface-gray-2 transition-colors gap-2"
								@click="
									() => {
										addTag(tag.tag_name)
										close()
									}
								"
							>
								<span
									class="w-3 h-3 rounded-full shrink-0"
									:style="{ backgroundColor: tag.color }"
								/>
								<span class="text-sm text-ink-gray-8">
									{{ tag.tag_name }}
								</span>
							</div>

							<div
								v-if="!filteredAvailableTags.length && !searchQuery"
								class="text-xs text-ink-gray-5 text-center py-2"
							>
								{{ __('No tags available') }}
							</div>
							<div
								v-else-if="!filteredAvailableTags.length && searchQuery"
								class="text-xs text-ink-gray-5 text-center py-2"
							>
								{{ __('No tags found') }}
							</div>
						</div>
					</div>
				</template>
			</Popover>

			<!-- Manage tags catalog -->
			<Popover placement="bottom-start">
				<template #target="{ togglePopover }">
					<Button variant="outline" size="sm" @click="togglePopover()">
						<template #prefix>
							<SettingsIcon class="w-3.5 h-3.5" />
						</template>
						{{ __('Manage Tags') }}
					</Button>
				</template>

				<template #body>
					<div class="bg-surface-white border rounded-lg shadow-lg w-fit p-3">
						<div class="text-sm font-semibold text-ink-gray-8 mb-3">
							{{ __('Manage Tags') }}
						</div>

						<!-- Create new tag -->
						<div class="flex flex-col items-center gap-2 mb-3 pb-3 border-b">
							<FormControl
								v-model="newTagName"
								:placeholder="__('New tag name')"
								class="flex-1 small-form"
								@keyup.enter="createTag()"
							/>
							<div class="flex items-center gap-1 shrink-0">
								<label
									class="w-7 h-7 rounded border border-outline-gray-2 cursor-pointer shrink-0 block"
									:style="{ backgroundColor: newTagColor }"
								>
									<input
										type="color"
										v-model="newTagColor"
										class="opacity-0 w-0 h-0 absolute"
									/>
								</label>
								<FormControl
									v-model="newTagColor"
									class="w-20 font-mono text-xs small-form"
									placeholder="#3B82F6"
								/>
								<Button
									variant="solid"
									size="sm"
									:disabled="!newTagName.trim()"
									:loading="isCreating"
									@click="createTag()"
								>
									{{ __('Save') }}
								</Button>
							</div>
						</div>

						<!-- All tags list -->
						<div class="max-h-56 overflow-y-auto space-y-1">
							<div
								v-for="tag in allTagsList"
								:key="tag.tag_name"
								class="flex items-center justify-between px-2 py-1.5 rounded hover:bg-surface-gray-2 transition-colors group"
							>
								<div class="flex items-center gap-2 flex-1 min-w-0">
									<label
										class="w-5 h-5 rounded border border-outline-gray-2 cursor-pointer shrink-0 block"
										:style="{ backgroundColor: tag.color }"
									>
										<input
											type="color"
											:value="tag.color"
											class="opacity-0 w-0 h-0 absolute"
											@change="updateTagColor(tag, $event.target.value)"
										/>
									</label>
									<span class="text-sm text-ink-gray-8 truncate">
										{{ tag.tag_name }}
									</span>
								</div>
								<button
									class="p-1 rounded hover:bg-surface-gray-3 text-ink-gray-4 hover:text-ink-red-3 opacity-0 group-hover:opacity-100 transition-all shrink-0"
									@click="confirmDeleteTag(tag)"
								>
									<Trash2 class="w-3.5 h-3.5" />
								</button>
							</div>

							<div
								v-if="!allTagsList.length"
								class="text-xs text-ink-gray-5 text-center py-3"
							>
								{{ __('No tags created yet') }}
							</div>
						</div>
					</div>
				</template>
			</Popover>
		</div>
	</div>
</template>

<script setup>
import { ref, computed } from 'vue'
import {
	Button,
	FormControl,
	Popover,
	createResource,
	call,
	toast,
} from 'frappe-ui'
import { Plus, X, Trash2, Settings as SettingsIcon } from 'lucide-vue-next'
import { createDialog } from '@/utils/dialogs'

const $dialog = createDialog

const props = defineProps({
	modelValue: {
		type: String,
		default: '',
	},
})

const emit = defineEmits(['update:modelValue', 'dirty'])

const searchQuery = ref('')
const newTagName = ref('')
const newTagColor = ref('#3B82F6')
const isCreating = ref(false)

const selectedTags = computed(() => {
	if (!props.modelValue) return []
	return props.modelValue
		.split(', ')
		.map((t) => t.trim())
		.filter(Boolean)
})

const allTags = createResource({
	url: 'frappe.client.get_list',
	method: 'POST',
	params: {
		doctype: 'LMS OS Course Tag',
		fields: ['tag_name', 'color'],
		limit_page_length: 0,
		order_by: 'tag_name asc',
	},
	auto: true,
})

const allTagsList = computed(() => allTags.data || [])

const selectedTagObjects = computed(() => {
	if (!allTags.data) return []
	const tagMap = new Map(allTags.data.map((t) => [t.tag_name, t]))
	return selectedTags.value.map((name) => tagMap.get(name)).filter(Boolean)
})

const filteredAvailableTags = computed(() => {
	if (!allTags.data) return []
	const selected = new Set(selectedTags.value)
	let tags = allTags.data.filter((t) => !selected.has(t.tag_name))
	if (searchQuery.value) {
		const q = searchQuery.value.toLowerCase()
		tags = tags.filter((t) => t.tag_name.toLowerCase().includes(q))
	}
	return tags
})

const addTag = (tagName) => {
	const newValue = selectedTags.value.length
		? `${props.modelValue}, ${tagName}`
		: tagName
	emit('update:modelValue', newValue)
	emit('dirty')
}

const removeTag = (tagName) => {
	const newValue = selectedTags.value.filter((t) => t !== tagName).join(', ')
	emit('update:modelValue', newValue)
	emit('dirty')
}

const createTag = async () => {
	const name = newTagName.value.trim()
	if (!name) return

	isCreating.value = true
	try {
		await call('frappe.client.insert', {
			doc: {
				doctype: 'LMS OS Course Tag',
				tag_name: name,
				color: newTagColor.value,
			},
		})
		toast.success(__('Tag created'))
		newTagName.value = ''
		newTagColor.value = '#3B82F6'
		allTags.reload()
	} catch (err) {
		toast.error(err.messages?.[0] || __('Failed to create tag'))
	} finally {
		isCreating.value = false
	}
}

const updateTagColor = async (tag, newColor) => {
	try {
		await call('frappe.client.set_value', {
			doctype: 'LMS OS Course Tag',
			name: tag.tag_name,
			fieldname: 'color',
			value: newColor,
		})
		toast.success(__('Tag updated'))
		allTags.reload()
	} catch (err) {
		toast.error(err.messages?.[0] || __('Failed to update tag'))
	}
}

const confirmDeleteTag = (tag) => {
	$dialog({
		title: __('Delete tag "{0}"?').format(tag.tag_name),
		message: __('This tag will be removed from all courses.'),
		actions: [
			{
				label: __('Delete'),
				theme: 'red',
				variant: 'solid',
				onClick(close) {
					deleteTag(tag.tag_name)
					close()
				},
			},
		],
	})
}

const deleteTag = async (tagName) => {
	try {
		await call('frappe.client.delete', {
			doctype: 'LMS OS Course Tag',
			name: tagName,
		})
		toast.success(__('Tag deleted'))
		removeTag(tagName)
		allTags.reload()
	} catch (err) {
		toast.error(err.messages?.[0] || __('Failed to delete tag'))
	}
}
</script>
