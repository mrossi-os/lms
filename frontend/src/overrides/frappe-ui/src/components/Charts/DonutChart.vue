<template>
	<DonutChart v-bind="$attrs" :config="config" />
</template>

<script setup>
// OSLMS-CUSTOM: DonutChart override, series colors from Brand Customize
// Wraps the ORIGINAL frappe-ui DonutChart through the frappe-ui-donutchart-original Vite
// alias (importing it from 'frappe-ui' here would make osOverrideTheme route
// the import back onto this file). When the page passes no colors and the brand
// sets chart colors (--os-chart-1..5), they are handed to ECharts; otherwise the
// config goes through unchanged. See src/oslms/utils/brandChartColors.ts.
import { computed } from 'vue'
import DonutChart from 'frappe-ui-donutchart-original'
import { withBrandChartColors } from '@/oslms/utils/brandChartColors'

defineOptions({ inheritAttrs: false })

const props = defineProps({
	config: { type: Object, required: true },
})

const config = computed(() => withBrandChartColors(props.config))
</script>
