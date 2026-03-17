<template>
	<div v-if="items.length" class="mt-10">
		<div class="text-xl font-semibold text-ink-gray-9 mb-4">
			{{ __('Cosa Imparerai') }}
		</div>
		<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
			<div
				v-for="(item, index) in items"
				:key="index"
				class="flex items-start gap-3 border border-outline-gray-2 rounded-lg p-4 bg-surface-white hover:bg-surface-gray-1 transition-colors"
			>
				<!-- Icona/emoji -->
				<component
					v-if="item.icon && getIconComponent(item.icon)"
					:is="getIconComponent(item.icon)"
					class="flex-shrink-0 flex items-center justify-center w-5 h-5 text-ink-gray-6"
				/>
				<div
					v-else
					class="flex-shrink-0 w-9 h-9 flex items-center justify-center bg-surface-gray-2 rounded-md"
				>
					<CheckCircle class="w-5 h-5 text-ink-gray-5" />
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
</template>

<script setup lang="ts">
import { CheckCircle } from 'lucide-vue-next'
import * as LucideIcons from 'lucide-vue-next'

const getIconComponent = (iconName: string) => {
	if (!iconName) return null
	return (LucideIcons as any)[iconName] ?? null
}
interface LearningItem {
	title: string
	description?: string
	icon?: string
}

const props = defineProps<{
	items: LearningItem[]
}>()
</script>
