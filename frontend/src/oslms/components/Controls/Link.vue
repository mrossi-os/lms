<template>
	<div class="os-link">
		<Link ref="inner" v-bind="$attrs" :onCreate="onCreate">
			<!-- Forward every (scoped) slot the caller passes, so this stays a
			     faithful drop-in for the base control. -->
			<template v-for="(_, name) in $slots" #[name]="slotProps">
				<slot :name="name" v-bind="slotProps ?? {}" />
			</template>
		</Link>
	</div>
</template>

<script setup lang="ts">
/*
 * Custom pass-through wrapper around the upstream <Link> control.
 *
 * Purpose: let us restyle the Link (via the `.os-link` hook below) WITHOUT
 * editing components/Controls/Link.vue, which is upstream-maintained and would
 * otherwise conflict on every merge.
 *
 * Everything passes straight through: v-model, doctype, label, variant, etc.
 * flow via v-bind="$attrs"; slots are forwarded; the inner control's public
 * methods (e.g. reload(), used via a template ref in BatchForm) are re-exposed.
 *
 * `onCreate` is the one prop we declare explicitly — with the same signature as
 * the base control — so inline `:onCreate="(value, close) => …"` handlers at
 * call sites keep their type inference (a propless wrapper would make them
 * implicitly `any`). Keep this signature in sync with Controls/Link.vue.
 *
 * Usage: import this file as `Link` — call sites only change the import path,
 * the <Link ... /> markup stays identical.
 */
import { ref } from 'vue'
import Link from '@/components/Controls/Link.vue'

type CreateHandler = (value: string | null, close?: () => void) => void

defineProps<{ onCreate?: CreateHandler }>()

defineOptions({ inheritAttrs: false })

const inner = ref<{ reload: (txt?: string) => void } | null>(null)

defineExpose({
	reload: (txt: string = ''): void => inner.value?.reload(txt),
})
</script>

<style scoped>
/*
 * Custom styling hook. The visible input/button lives deep inside frappe-ui's
 * Combobox, so reach it with :deep(). Fill in your colors here.
 *
 * Example (uncomment + adjust):
 * .os-link :deep([role='combobox']),
 * .os-link :deep(input) {
 *   background-color: var(--surface-base);
 *   border-color: var(--outline-gray-2);
 *   color: var(--ink-base);
 * }
 */
</style>
