<template>
	<div class="flex gap-4 p-4">
		<div class="flex flex-col gap-4 flex-1 min-w-0">
			<div class="flex items-center justify-between">
				<span class="text-sm" :class="stateClass">{{ stateLabel }}</span>
				<span v-if="state === 'connected'" class="font-mono text-sm">
					{{ formattedRemaining }}
				</span>
			</div>

			<div
				ref="scroller"
				class="flex flex-col gap-2 overflow-y-auto"
				style="max-height: 50vh"
			>
				<div
					v-for="(turn, i) in transcript"
					:key="i"
					class="rounded-md px-3 py-2 text-sm"
					:class="
						turn.role === 'user'
							? 'self-end bg-gray-100'
							: 'self-start bg-blue-50'
					"
				>
					{{ turn.text }}
				</div>
			</div>

			<div class="flex gap-2">
				<Button v-if="state === 'idle'" variant="solid" @click="onStart">
					{{ __('Start voice session') }}
				</Button>
				<Button
					v-else-if="['connecting', 'connected'].includes(state)"
					theme="red"
					variant="solid"
					@click="onStop"
				>
					{{ __('End session') }}
				</Button>
				<template v-else-if="state === 'error'">
					<Button variant="solid" @click="onStart">
						{{ __('Retry') }}
					</Button>
					<Button variant="subtle" @click="emit('ended')">
						{{ __('Close') }}
					</Button>
				</template>
			</div>
		</div>
		<aside
			v-if="studentBrief"
			class="hidden md:block w-72 shrink-0 overflow-y-auto border border-outline-gray-2 rounded-md p-3 bg-surface-gray-1"
			style="max-height: 60vh"
		>
			<div class="text-sm font-semibold text-ink-gray-9 mb-2">
				{{ __('Il tuo compito') }}
			</div>
			<div class="whitespace-pre-wrap text-sm text-ink-gray-7">
				{{ studentBrief }}
			</div>
		</aside>
	</div>
</template>

<script setup>
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Button, createResource } from 'frappe-ui'
import { useRealtimeSession } from '../../composables/useRealtimeSession'

const props = defineProps({ sessionId: { type: String, required: true } })
const emit = defineEmits(['ended'])

const router = useRouter()
const { state, transcript, remainingSeconds, sessionId, start, stop } =
	useRealtimeSession()
const scroller = ref(null)

const studentBrief = ref('')
const sessionRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.get_session',
	method: 'GET',
	makeParams: () => ({ session_id: props.sessionId }),
	onSuccess: (data) => {
		studentBrief.value = data?.session?.student_brief || ''
	},
})
sessionRes.reload()

const stateLabel = computed(
	() =>
		({
			idle: __('Ready'),
			connecting: __('Connecting…'),
			connected: __('Live'),
			closed: __('Ended'),
			error: __('Connection error'),
		}[state.value] || state.value)
)
const stateClass = computed(() =>
	state.value === 'error'
		? 'text-red-600'
		: state.value === 'connected'
		? 'text-green-600'
		: 'text-gray-500'
)
const formattedRemaining = computed(() => {
	const s = remainingSeconds.value
	return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(
		s % 60
	).padStart(2, '0')}`
})

async function onStart() {
	await start(props.sessionId)
}

async function onStop() {
	await stop('completed')
}

// Navigate to debrief when the session closes — covers both manual stop and
// timer-triggered auto-stop. Also emits 'ended' so the parent can clean up.
watch(state, (s) => {
	if (s === 'closed' && sessionId.value) {
		router.push({
			name: 'SimulationDebrief',
			params: { sessionId: sessionId.value },
		})
		emit('ended')
	}
})

// Ensure mic tracks are released even if the dialog is dismissed mid-session.
onUnmounted(() => {
	if (state.value !== 'closed' && state.value !== 'idle') {
		stop('abandoned')
	}
})

watch(
	() => transcript.value.length,
	async () => {
		await nextTick()
		if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
	}
)
</script>
