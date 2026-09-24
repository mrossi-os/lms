<template>
	<div v-if="doc" class="">
		<CollapsibleSection :label="__('Regole di Apprendimento')">
			<div class="flex flex-col gap-y-4">
				<!-- Lesson order is upstream's enforce_lesson_completion switch (CoursePublishSettings) -->
				<Switch size="sm"  v-model="doc.enforce_quiz_on_completion"
					:label="__('Blocca quiz al completamento')" :description="__(
						'Lo studente deve completare tutte le lezioni precedenti al quiz per accedervi.',
					)
						" @change="markDirty()" />
			</div>
		</CollapsibleSection>
	</div>
</template>

<script setup lang="ts">
import Switch from '@/components/Controls/BooleanSwitch.vue'
import { computed, inject, } from 'vue'
import CollapsibleSection from '@/components/CollapsibleSection.vue'
import type { CourseFormContext, } from '@/types/api'

const { resource, markDirty } = inject<CourseFormContext>('courseForm')!
const doc = computed(() => resource.doc)
</script>
