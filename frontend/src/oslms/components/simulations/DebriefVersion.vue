<template>
	<!-- One version of a simulation report (the AI's or the teacher's) as the
	     student reads it: score, criteria, strengths, improvements, comment. -->
	<div>
		<div
			v-if="version.overall_score != null"
			class="border border-outline-gray-2 rounded-md p-5 mb-6 card"
		>
			<div class="text-3xl font-semibold text-ink-gray-9 tabular-nums">
				{{ Math.round(version.overall_score) }}
				<span class="text-sm font-normal text-ink-gray-5">/100</span>
			</div>
			<div v-if="scoreNote" class="mt-1 text-xs text-ink-gray-5">
				{{ scoreNote }}
			</div>
		</div>

		<section v-if="version.criterion_scores?.length" class="mb-6">
			<h2 class="text-base font-semibold text-ink-gray-9 mb-3">
				{{ __('Criteri') }}
			</h2>
			<ul class="space-y-2">
				<li
					v-for="c in version.criterion_scores"
					:key="c.criterion_name"
					class="border border-outline-gray-2 rounded-md p-3 card"
				>
					<div class="flex items-baseline justify-between gap-3">
						<span class="text-sm font-medium text-ink-gray-9">
							{{ c.criterion_name }}
						</span>
						<span
							class="text-sm font-semibold text-ink-gray-9 tabular-nums whitespace-nowrap"
						>
							{{ c.score
							}}<span class="font-normal text-ink-gray-5">
								/ {{ c.max_score || 10 }}</span
							>
						</span>
					</div>
					<div class="mt-2 h-1.5 bg-surface-gray-2 rounded-full overflow-hidden">
						<div
							class="h-full bg-surface-blue-3"
							:style="{ width: `${barWidth(c)}%` }"
						></div>
					</div>
					<div v-if="c.note" class="text-xs text-ink-gray-7 mt-2">
						{{ c.note }}
					</div>
				</li>
			</ul>
		</section>

		<section v-if="version.strengths?.length" class="mb-6">
			<h2 class="text-base font-semibold text-ink-gray-9 mb-3">
				{{ __('Punti di forza') }}
			</h2>
			<ul class="space-y-2">
				<li
					v-for="(s, i) in version.strengths"
					:key="i"
					class="border border-outline-green-2 bg-surface-green-1 rounded-md p-3 text-sm"
				>
					<div class="font-medium text-ink-gray-9">{{ s.title }}</div>
					<div v-if="s.detail" class="text-xs text-ink-gray-5 mt-1">
						{{ s.detail }}
					</div>
					<blockquote
						v-if="s.quote"
						class="text-xs italic mt-2 border-l-2 border-outline-green-3 pl-2"
					>
						"{{ s.quote }}"
					</blockquote>
				</li>
			</ul>
		</section>

		<section v-if="version.improvements?.length" class="mb-6">
			<h2 class="text-base font-semibold text-ink-gray-9 mb-3">
				{{ __('Aree di miglioramento') }}
			</h2>
			<ul class="space-y-2">
				<li
					v-for="(imp, i) in version.improvements"
					:key="i"
					class="card-failure text-sm"
				>
					<div class="font-medium text-ink-gray-9">{{ imp.title }}</div>
					<div v-if="imp.detail" class="text-xs text-ink-gray-5 mt-1">
						{{ imp.detail }}
					</div>
					<blockquote
						v-if="imp.quote"
						class="text-xs italic mt-2 border-l-2 border-outline-orange-3 pl-2"
					>
						"{{ imp.quote }}"
					</blockquote>
					<div v-if="imp.suggestion" class="text-xs text-ink-gray-9 mt-2">
						<span class="font-medium">{{ __('Suggerimento') }}:</span>
						{{ imp.suggestion }}
					</div>
				</li>
			</ul>
		</section>

		<section v-if="version.comment" class="mb-6">
			<h2 class="text-base font-semibold text-ink-gray-9 mb-3">
				{{ __('Commento del docente') }}
			</h2>
			<div
				class="text-sm border border-outline-gray-2 rounded-md p-3 bg-surface-gray-1 card text-ink-gray-9 whitespace-pre-wrap"
			>
				{{ version.comment }}
			</div>
		</section>
	</div>
</template>

<script setup>
defineProps({
	version: { type: Object, required: true },
	scoreNote: { type: String, default: '' },
})

function barWidth(c) {
	const ratio = Number(c.score) / Number(c.max_score || 10)
	return Math.max(0, Math.min(100, ratio * 100))
}
</script>
