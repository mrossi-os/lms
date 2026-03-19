<template>
	<div class="pr-5 md:pr-10 pb-5 mb-5 space-y-5 border-b">
		<div class="text-lg font-semibold text-ink-gray-9">
			{{ __('Sezioni Feature') }}
		</div>
		<div class="text-sm text-ink-gray-5">
			{{
				__(
					'Crea sezioni con badge per descrivere cosa imparerà lo studente, le certificazioni, ecc.',
				)
			}}
		</div>

		<!-- Sezioni -->
		<div
			v-for="(section, sIndex) in sections"
			:key="section.id"
			class="border border-outline-gray-7 rounded-lg overflow-hidden"
		>
			<!-- Header sezione -->
			<div
				class="flex items-center gap-3 px-4 py-3 bg-surface-gray-7 border-b border-outline-gray-7"
			>
				<FormControl
					v-model="section.title"
					:placeholder="__('Nome sezione...')"
					class="flex-1"
					@input="onChanged"
				/>
				<button
					type="button"
					class="text-ink-gray-4 hover:text-ink-red-3 transition-colors shrink-0"
					@click="removeSection(sIndex)"
				>
					<Trash2 class="w-4 h-4" />
				</button>
			</div>

			<!-- Badge della sezione -->
			<div class="p-4 space-y-4">
				<div
					v-if="section.items.length"
					class="grid grid-cols-1 md:grid-cols-3 gap-3"
				>
					<div
						v-for="(item, iIndex) in section.items"
						:key="item.id"
						class="relative border border-outline-gray-2 rounded-lg p-3 card space-y-2"
					>
						<button
							type="button"
							class="absolute top-2 right-2 text-ink-gray-4 hover:text-ink-red-3 transition-colors"
							@click="removeItem(sIndex, iIndex)"
						>
							<X class="w-3.5 h-3.5" />
						</button>

						<!-- Anteprima -->
						<div
							class="flex items-center gap-2 pb-2 border-b border-outline-gray-1"
						>
							<div
								class="w-7 h-7 rounded-md bg-surface-gray-2 flex items-center justify-center shrink-0"
							>
								<component
									v-if="item.icon && getIconComponent(item.icon)"
									:is="getIconComponent(item.icon)"
									class="w-4 h-4 text-ink-gray-6"
								/>
								<CheckCircle v-else class="w-4 h-4 text-ink-gray-4" />
							</div>
							<span class="text-xs text-ink-gray-5 truncate">
								{{ item.title || __('Badge senza titolo') }}
							</span>
						</div>

						<IconPicker
							v-model="item.icon"
							:label="__('Icona')"
							@update:modelValue="onChanged"
						/>
						<FormControl
							v-model="item.title"
							:label="__('Titolo')"
							:required="true"
							@input="onChanged"
						/>
						<FormControl
							v-model="item.description"
							type="textarea"
							:rows="2"
							:label="__('Descrizione')"
							@input="onChanged"
						/>
					</div>
				</div>

				<!-- Empty state badge -->
				<div
					v-else
					class="border border-dashed border-outline-gray-2 rounded-lg py-5 text-center"
				>
					<div class="text-xs text-ink-gray-4">
						{{ __('Nessun badge in questa sezione') }}
					</div>
				</div>

				<!-- Aggiungi badge -->
				<Button
					v-if="section.items.length < 9"
					variant="ghost"
					@click="addItem(sIndex)"
				>
					<template #prefix>
						<Plus class="w-3.5 h-3.5" />
					</template>
					{{ __('Aggiungi Badge') }}
				</Button>
				<div v-else class="text-xs text-ink-gray-4 flex items-center gap-1">
					<Info class="w-3 h-3" />
					{{ __('Massimo 9 badge per sezione') }}
				</div>
			</div>
		</div>

		<!-- Empty state sezioni -->
		<div
			v-if="!sections.length"
			class="border border-dashed border-outline-gray-2 rounded-lg py-8 text-center"
		>
			<LayoutGrid class="w-8 h-8 text-ink-gray-3 mx-auto mb-2" />
			<div class="text-sm text-ink-gray-5">
				{{ __('Nessuna sezione aggiunta') }}
			</div>
			<div class="text-xs text-ink-gray-4 mt-0.5">
				{{ __('Crea una sezione e aggiungi i badge') }}
			</div>
		</div>

		<!-- Aggiungi sezione -->
		<Button variant="outline" @click="addSection">
			<template #prefix>
				<Plus class="w-4 h-4" />
			</template>
			{{ __('Aggiungi Sezione') }}
		</Button>
	</div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { FormControl, Button } from 'frappe-ui'
import { X, Plus, Info, LayoutGrid, CheckCircle, Trash2 } from 'lucide-vue-next'
import * as LucideIcons from 'lucide-vue-next'
import IconPicker from '@/oslms/components/IconPicker.vue'

// ─── Props & Emits ────────────────────────────────────────────────────────────
//
// modelValue è il doc di courseResource — lo stesso passato da CourseForm.
// Leggiamo doc.feature_sections (JSON string) e lo scriviamo indietro.
//

const props = defineProps({
	modelValue: {
		type: Object,
		required: true,
	},
})

const emit = defineEmits(['update:modelValue', 'dirty'])

// ─── Stato locale ─────────────────────────────────────────────────────────────

const sections = ref([])

// Quando il doc cambia (es. dopo reload), aggiorna lo stato locale
watch(
	() => props.modelValue?.name,
	() => {
		const raw = props.modelValue?.feature_sections
		try {
			// Unescape HTML entities prima di parsare
			const unescaped = raw
				? raw.replace(/&quot;/g, '"').replace(/&amp;/g, '&')
				: null
			sections.value = unescaped ? JSON.parse(unescaped) : []
		} catch {
			sections.value = []
		}
	},
	{ immediate: true },
)

// ─── Sync al parent ───────────────────────────────────────────────────────────

const onChanged = () => {
	if (props.modelValue) {
		props.modelValue.feature_sections = JSON.stringify(sections.value)
	}
	emit('dirty')
}

// ─── Utils ────────────────────────────────────────────────────────────────────

const generateId = () => Math.random().toString(36).substring(2, 10)

const getIconComponent = (iconName) => {
	if (!iconName) return null
	return LucideIcons[iconName] ?? null
}

// ─── Sezioni ─────────────────────────────────────────────────────────────────

const addSection = () => {
	sections.value.push({ id: generateId(), title: '', items: [] })
	onChanged()
}

const removeSection = (sIndex) => {
	sections.value.splice(sIndex, 1)
	onChanged()
}

// ─── Badge ────────────────────────────────────────────────────────────────────

const addItem = (sIndex) => {
	if (sections.value[sIndex].items.length >= 9) return
	sections.value[sIndex].items.push({
		id: generateId(),
		title: '',
		description: '',
		icon: '',
	})
	onChanged()
}

const removeItem = (sIndex, iIndex) => {
	sections.value[sIndex].items.splice(iIndex, 1)
	onChanged()
}
</script>
