<template>
	<Dialog
		v-model="visible"
		:options="{ title: __('Trascrizione + Debrief'), size: '4xl' }"
	>
		<template #body-content>
			<div v-if="loading" class="text-ink-gray-5 text-sm">{{ __('Caricamento…') }}</div>
			<div v-else-if="payload" class="grid grid-cols-5 gap-4">
				<!-- Left: transcript (read-only chat) -->
				<div class="col-span-3 border rounded-md overflow-hidden flex flex-col h-[70vh]">
					<ChatSession
						class="flex-1"
						:scenarioName="payload.session.scenario"
						:persona="persona"
						:turns="payload.turns"
						:status="payload.session.status"
						readOnly
					/>
				</div>

				<!-- Right: debrief summary -->
				<div class="col-span-2 space-y-3 max-h-[70vh] overflow-y-auto pr-2">
					<div v-if="payload.debrief">
						<div class="text-xs uppercase text-ink-gray-5 mb-1">{{ __('Punteggio') }}</div>
						<div class="text-3xl font-semibold text-ink-gray-9">
							{{ Math.round(payload.debrief.overall_score || 0) }}
							<span class="text-sm text-ink-gray-5">/100</span>
							<Badge
								class="ml-2 align-middle"
								:label="payload.debrief.passed ? __('Superata') : __('Non superata')"
								:theme="payload.debrief.passed ? 'green' : 'orange'"
							/>
						</div>

						<section v-if="payload.debrief.criterion_scores?.length" class="mt-4">
							<div class="text-xs font-semibold text-ink-gray-9 mb-1">
								{{ __('Criteri') }}
							</div>
							<ul class="space-y-1 text-xs">
								<li
									v-for="c in payload.debrief.criterion_scores"
									:key="c.criterion_name"
									class="flex justify-between"
								>
									<span>{{ c.criterion_name }}</span>
									<span class="text-ink-gray-5">
										{{ c.score }} / {{ c.max_score || 10 }}
									</span>
								</li>
							</ul>
						</section>

						<section v-if="payload.debrief.improvements?.length" class="mt-4">
							<div class="text-xs font-semibold text-ink-gray-9 mb-1">
								{{ __('Aree di miglioramento') }}
							</div>
							<ul class="text-xs list-disc list-inside text-ink-gray-7">
								<li v-for="(imp, i) in payload.debrief.improvements" :key="i">
									{{ imp.title }}
								</li>
							</ul>
						</section>

						<!-- Instructor review -->
						<section class="mt-4">
							<div class="text-xs font-semibold text-ink-gray-9 mb-1">
								{{ __('Nota docente') }}
							</div>
							<textarea
								v-model="reviewDraft"
								rows="4"
								class="w-full rounded-md border border-outline-gray-2 p-2 text-sm"
								:placeholder="__('Aggiungi un commento privato per lo studente.')"
							></textarea>
							<div class="flex justify-end mt-2">
								<Button
									variant="solid"
									size="sm"
									:loading="savingReview"
									:disabled="!reviewDraft.trim()"
									@click="onSaveReview"
								>
									{{ __('Salva nota') }}
								</Button>
							</div>
						</section>
					</div>
					<div v-else class="text-sm text-ink-gray-5">
						{{ __('Debrief non disponibile per questa sessione.') }}
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Badge, Button, Dialog, createResource, toast } from 'frappe-ui'
import ChatSession from '@/oslms/components/simulations/ChatSession.vue'

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	sessionId: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'review-saved'])

const visible = computed({
	get: () => props.modelValue,
	set: (v) => emit('update:modelValue', v),
})

const payload = ref(null)
const loading = ref(false)
const reviewDraft = ref('')
const savingReview = ref(false)

const persona = computed(() => {
	const raw = payload.value?.session?.generated_persona
	if (!raw) return null
	try { return JSON.parse(raw) } catch { return null }
})

const loadRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.get_transcript',
	makeParams() {
		return { session_id: props.sessionId }
	},
	onSuccess(data) {
		payload.value = data
		reviewDraft.value = data?.debrief?.instructor_review || ''
	},
	onError(e) {
		toast.error(e.messages?.[0] || __('Caricamento trascrizione fallito'))
	},
})

watch(
	() => [props.sessionId, visible.value],
	([id, open]) => {
		if (open && id) {
			loading.value = true
			loadRes.submit().finally(() => { loading.value = false })
		}
	},
	{ immediate: true },
)

const reviewRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.instructor_review_debrief',
	method: 'POST',
})

async function onSaveReview() {
	if (!reviewDraft.value.trim()) return
	savingReview.value = true
	try {
		await reviewRes.submit({ session_id: props.sessionId, review: reviewDraft.value })
		toast.success(__('Nota salvata.'))
		emit('review-saved')
	} catch (e) {
		toast.error(e.messages?.[0] || __('Salvataggio fallito'))
	} finally {
		savingReview.value = false
	}
}
</script>
