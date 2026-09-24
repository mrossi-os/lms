<template>
	<SkeletonLoader v-if="loading" variant="header" />
	<header v-else class="header-frame sticky top-0 z-10 justify-between">
		<div class="flex min-w-0 flex-1 items-center gap-2">
			<template v-if="isMobile">
				<!-- OSLMS-CUSTOM: history back for viewers the parent crumb would refuse -->
				<button
					v-if="historyBack"
					type="button"
					:aria-label="__('Back')"
					class="-ms-3 shrink-0 rounded p-1.5 text-ink-gray-9 transition-colors hover:bg-surface-gray-2"
					@click="goBack"
				>
					<span class="lucide-chevron-left size-4 block" />
				</button>
				<router-link
					v-else-if="backTo"
					:to="backTo"
					:aria-label="__('Back')"
					class="-ms-3 shrink-0 rounded p-1.5 text-ink-gray-9 transition-colors hover:bg-surface-gray-2"
				>
					<span class="lucide-chevron-left size-4 block" />
				</router-link>
				<span class="min-w-0 truncate text-lg-medium text-ink-gray-9">
					{{ currentLabel }}
				</span>
			</template>
			<template v-else>
				<Breadcrumbs class="h-7 min-w-0" :items="breadcrumbs" />
				<Badge v-if="published" theme="green">{{ __('Published') }}</Badge>
			</template>
		</div>
		<div class="flex shrink-0 items-center gap-2">
			<slot name="actions" />
		</div>
	</header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'
import { Badge, Breadcrumbs } from 'frappe-ui'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import { useScreenSize } from '@/utils/composables'
import type { Breadcrumb } from '@/types'

const props = withDefaults(
	defineProps<{
		breadcrumbs: Breadcrumb[]
		published?: boolean
		loading?: boolean
		/**
		 * OSLMS-CUSTOM: the phone back button goes back in history instead of to the
		 * parent crumb; this route is the fallback when there is no history (deep link).
		 */
		historyBack?: RouteLocationRaw | null
	}>(),
	{ published: false, loading: false, historyBack: null }
)

const router = useRouter()

const goBack = () => {
	if (window.history.state?.back) router.back()
	else if (props.historyBack) router.push(props.historyBack)
}

const { isMobile } = useScreenSize()

const currentLabel = computed<string>(
	() => props.breadcrumbs[props.breadcrumbs.length - 1]?.label ?? ''
)

const backTo = computed<RouteLocationRaw | null>(
	() => props.breadcrumbs[props.breadcrumbs.length - 2]?.route ?? null
)
</script>
