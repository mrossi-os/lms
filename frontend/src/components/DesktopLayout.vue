<template>
	<div class="flex h-screen w-screen">
		<div class="bg-gradient-overlay"></div>
		<div class="h-full">
			<AppSidebar />
		</div>
		<div class="flex-1 flex flex-col h-full overflow-auto app-content-main">
			<slot />
		</div>
	</div>
</template>
<script setup>
import AppSidebar from '@/components/Sidebar/AppSidebar.vue'
</script>
