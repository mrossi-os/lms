<template>
	<div class="flex h-screen w-screen">
		<!-- OSLMS-CUSTOM: elite theme hook; its CSS is gone, so the overlay div is inert -->
		<div class="bg-gradient-overlay"></div>
		<!-- OSLMS-CUSTOM: sidebar wrapper without upstream border/background (elite theme) -->
		<div class="h-full">
			<AppSidebar />
		</div>
		<div class="flex-1 flex flex-col h-full overflow-auto bg-surface-base">
			<slot />
		</div>
		<!-- OSLMS-CUSTOM: floating AI coach/tutor buttons on every page -->
		<AiFixedButtons />
	</div>
</template>
<script setup>
import AppSidebar from '@/components/Sidebar/AppSidebar.vue'
// OSLMS-CUSTOM: os_lms floating AI buttons
import AiFixedButtons from '@/oslms/components/AiFixedButtons.vue'
</script>
