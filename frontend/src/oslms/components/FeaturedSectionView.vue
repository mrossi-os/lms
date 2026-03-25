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
					class="flex items-start gap-3 border border-outline-gray-2 rounded-lg p-4 bg-surface-white hover:bg-surface-gray-7 transition-colors"
				>
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
					<div class="flex flex-col min-w-0">
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
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CheckCircle } from 'lucide-vue-next'
import * as LucideIcons from 'lucide-vue-next'

interface FeatureItem {
	id?: string
	title: string
	description?: string
	icon?: string
}

interface FeatureSection {
	id?: string
	title: string
	items: FeatureItem[]
}

const props = defineProps<{
	// Accetta sia l'array già parsato che la stringa JSON grezza
	sections: FeatureSection[] | string
}>()

// Supporta sia array che stringa JSON
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

const getIconComponent = (iconName: string) => {
	if (!iconName) return null
	return (LucideIcons as any)[iconName] ?? null
}
</script>
