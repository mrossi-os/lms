<template>
	<div v-if="sections.length" class="mt-10 space-y-8">
		<div v-for="(section, sIndex) in sections" :key="section.id || sIndex">
			<!-- Titolo sezione -->
			<div class="text-xl font-semibold text-ink-gray-9 mb-4">
				{{ section.title }}
			</div>

			<!-- Badge della sezione -->
			<div
				v-if="section.items?.length"
				class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3"
			>
				<div
					v-for="(item, iIndex) in section.items"
					:key="item.id || iIndex"
					class="flex flex-col border rounded-lg p-4 bg-surface-white hover:bg-surface-gray-7 transition-colors"
				>
					<div class="flex items-start gap-3">
						<!-- Icona Lucide -->
						<div
							class="flex-shrink-0 w-9 h-9 flex items-center justify-center bg-surface-gray-2 rounded-md"
						>
							<component
								v-if="item.icon && getIconComponent(item.icon)"
								:is="getIconComponent(item.icon)"
								class="w-5 h-5 text-ink-gray-6"
							/>
							<CheckCircle v-else class="w-5 h-5 text-ink-gray-5" />
						</div>

						<!-- Testo -->
						<div class="flex flex-col min-w-0 flex-1">
							<span class="text-sm font-semibold text-ink-gray-9 leading-5">
								{{ item.title }}
							</span>
							<span
								v-if="item.description"
								class="text-xs text-ink-gray-6 leading-4 mt-0.5"
							>
								{{ item.description }}
							</span>
						</div>
					</div>

					<!-- Download -->
					<a
						v-if="getFileUrl(item.file)"
						:href="getFileUrl(item.file)"
						target="_blank"
						download
						class="flex items-center gap-1.5 mt-3 pt-3 border-t border-outline-gray-1 text-xs text-ink-gray-5 hover:text-ink-gray-8 transition-colors"
					>
						<Download class="w-3.5 h-3.5 shrink-0" />
						<span class="truncate">{{ getFileName(item.file) }}</span>
					</a>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { createResource } from 'frappe-ui'
import { CheckCircle, Download } from 'lucide-vue-next'
import * as LucideIcons from 'lucide-vue-next'

interface FeatureItem {
	id?: string
	title: string
	description?: string
	icon?: string
	file?: string
}

interface FeatureSection {
	id?: string
	title: string
	items: FeatureItem[]
}

const props = defineProps<{
	sections: FeatureSection[] | string
}>()

const sections = computed<FeatureSection[]>(() => {
	if (!props.sections) return []
	if (typeof props.sections === 'string') {
		try {
			return JSON.parse(props.sections)
		} catch {
			return []
		}
	}
	return props.sections
})

// Mappa file name -> { file_url, file_name }
const fileUrls = ref<Record<string, string>>({})
const fileDisplayNames = ref<Record<string, string>>({})

const fileNames = computed(() => {
	const names: string[] = []
	for (const section of sections.value) {
		for (const item of section.items || []) {
			if (item.file && !fileUrls.value[item.file]) {
				names.push(item.file)
			}
		}
	}
	return names
})

const filesResource = createResource({
	url: 'frappe.client.get_list',
	method: 'POST',
	params: {
		doctype: 'File',
		filters: { name: ['in', fileNames.value] },
		fields: ['name', 'file_name', 'file_url'],
		limit_page_length: 0,
	},
	auto: false,
	onSuccess: (
		data: Array<{ name: string; file_name: string; file_url: string }>,
	) => {
		for (const f of data) {
			fileUrls.value[f.name] = f.file_url
			fileDisplayNames.value[f.name] = f.file_name
		}
	},
})

watch(
	fileNames,
	(names) => {
		if (names.length) {
			filesResource.update({
				params: {
					doctype: 'File',
					filters: { name: ['in', names] },
					fields: ['name', 'file_name', 'file_url'],
					limit_page_length: 0,
				},
			})
			filesResource.reload()
		}
	},
	{ immediate: true },
)

const getFileUrl = (fileName?: string) => {
	if (!fileName) return ''
	return fileUrls.value[fileName] || ''
}

const getFileName = (fileName?: string) => {
	if (!fileName) return ''
	return fileDisplayNames.value[fileName] || fileName
}

const getIconComponent = (iconName: string) => {
	if (!iconName) return null
	return (LucideIcons as any)[iconName] ?? null
}
</script>
