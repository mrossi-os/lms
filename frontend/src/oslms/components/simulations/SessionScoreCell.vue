<template>
	<!-- A session's score in the instructor reports: the published teacher
	     score, otherwise the AI's indicative one, with the AI's beside a
	     teacher score so the correction shows. -->
	<span v-if="session.score !== null && session.score !== undefined">
		<span class="font-medium tabular-nums">{{ Math.round(session.score) }}</span>
		<span class="ml-1 text-xs text-ink-gray-5">
			<template v-if="session.score_source === 'teacher'">
				{{ __('docente') }}
				<template v-if="session.ai_score !== null && session.ai_score !== undefined">
					· {{ __('AI {0}').format(Math.round(session.ai_score)) }}
				</template>
			</template>
			<template v-else>{{ __('indicativo') }}</template>
		</span>
	</span>
	<span v-else class="text-ink-gray-5">—</span>
</template>

<script setup>
defineProps({
	session: { type: Object, required: true },
})
</script>
