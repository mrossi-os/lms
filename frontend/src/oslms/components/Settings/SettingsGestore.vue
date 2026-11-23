<template>
	<!-- Manager settings panel ("Impostazioni gestore") for Gestore and administrators.
	     Same shell as components/Settings/Settings.vue; the tabs come from oslms/utils/settingsTabs.js. -->
	<SettingsDialog v-model="show" v-model:tab="activeTab" size="5xl">
		<template #title>{{ __('Manager Settings') }}</template>
		<SettingsSidebar>
			<SettingsNavGroup
				v-for="group in tabs"
				:key="tabKey(group)"
				:label="group.hideLabel ? undefined : group.label"
			>
				<template #label>
					<span class="text-p-xs-medium text-ink-gray-5">
						{{ group.label }}
					</span>
				</template>
				<SettingsNavItem
					v-for="item in group.items"
					:key="tabKey(item)"
					:value="tabKey(item)"
				>
					<template #prefix>
						<!-- os_lms tabs name lucide-vue-next components; lucide-* class names render as a span -->
						<component
							v-if="lucideIcons[item.icon]"
							:is="lucideIcons[item.icon]"
							class="size-4 shrink-0 stroke-1.5 text-ink-gray-7"
						/>
						<span v-else :class="[item.icon, 'size-4 shrink-0 text-ink-gray-7']" />
					</template>
					<span class="text-p-sm text-ink-gray-7">{{ __(item.label) }}</span>
				</SettingsNavItem>
			</SettingsNavGroup>
		</SettingsSidebar>
		<SettingsContent v-if="data.doc" id="settings-gestore-modal">
			<SettingsPanel
				v-for="item in items"
				:key="tabKey(item)"
				:value="tabKey(item)"
				class="p-8 overflow-x-auto overflow-y-auto"
			>
				<component
					v-if="item.template"
					:is="item.template"
					v-bind="panelProps(item)"
				/>
				<SettingDetails
					v-else
					:sections="item.sections"
					:label="item.label"
					:description="item.description"
					:data="data"
				/>
			</SettingsPanel>
		</SettingsContent>
	</SettingsDialog>
</template>
<script setup>
import {
	SettingsContent,
	SettingsDialog,
	SettingsNavGroup,
	SettingsNavItem,
	SettingsPanel,
	SettingsSidebar,
	createDocumentResource,
} from 'frappe-ui'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as lucideIcons from 'lucide-vue-next'
import { useSettings } from '@/stores/settings'
import SettingDetails from '@/components/Settings/SettingDetails.vue'
import {
	applyTabConditions,
	buildGestoreSettingsTabs,
} from '@/oslms/utils/settingsTabs'

const show = defineModel()
const activeTab = ref('')
const settingsStore = useSettings()

// Tells openSettings the manager panel exists (it is not mounted on a phone).
onMounted(() => {
	settingsStore.isGestoreSettingsMounted = true
})
onBeforeUnmount(() => {
	settingsStore.isGestoreSettingsMounted = false
})

const data = createDocumentResource({
	doctype: 'LMS Settings',
	name: 'LMS Settings',
	fields: ['*'],
	cache: 'LMS Settings',
	auto: true,
})

// Built inside a computed so __() labels re-evaluate once translations load.
const tabs = computed(() => applyTabConditions(buildGestoreSettingsTabs()))

const tabKey = (item) => item.key || item.label

const items = computed(() => tabs.value.flatMap((group) => group.items))

// Same props as Settings.vue: Branding and TrueSkills receive their field
// sections, Members owns dialogs of its own and needs to close the panel.
const panelProps = (item) => ({
	label: item.label,
	description: item.description,
	...(['Branding', 'TrueSkills API'].includes(item.key)
		? { sections: item.sections }
		: {}),
	...(item.key === 'Members'
		? { 'onUpdate:show': (val) => (show.value = val), show: show.value }
		: {}),
})

watch(show, () => {
	if (show.value) {
		// Deep links (openSettings) match the stable key.
		const stored = items.value.find(
			(item) => item.key === settingsStore.activeTab,
		)
		activeTab.value = tabKey(stored || items.value[0])
	} else {
		activeTab.value = ''
		settingsStore.isGestoreSettingsOpen = false
	}
})
</script>
