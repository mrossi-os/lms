<template>
	<div class="icon-picker" ref="pickerRef">
		<div class="text-xs text-ink-gray-5 mb-1">{{ label }}</div>

		<!-- Trigger button -->
		<button
			type="button"
			class="flex items-center gap-2 w-full border border-outline-gray-2 rounded-md px-3 py-1.5 bg-surface-white hover:bg-surface-gray-1 transition-colors text-sm text-ink-gray-7"
			@click="toggleDropdown"
		>
			<component
				v-if="selectedIcon"
				:is="selectedIcon.component"
				class="w-4 h-4 text-ink-gray-7 shrink-0"
			/>
			<span v-else class="w-4 h-4 shrink-0 flex items-center justify-center">
				<Smile class="w-4 h-4 text-ink-gray-4" />
			</span>
			<span class="flex-1 text-left truncate">
				{{ selectedIcon ? selectedIcon.name : __('Seleziona icona') }}
			</span>
			<ChevronDown
				class="w-3.5 h-3.5 text-ink-gray-4 shrink-0 transition-transform duration-150"
				:class="{ 'rotate-180': isOpen }"
			/>
		</button>

		<!-- Dropdown -->
		<Transition name="dropdown">
			<div
				v-if="isOpen"
				class="absolute z-50 mt-1 w-72 bg-surface-white border border-outline-gray-2 rounded-lg shadow-lg overflow-hidden"
			>
				<!-- Search -->
				<div class="p-2 border-b border-outline-gray-1">
					<div
						class="flex items-center gap-2 bg-surface-gray-1 rounded-md px-2.5 py-1.5"
					>
						<Search class="w-3.5 h-3.5 text-ink-gray-4 shrink-0" />
						<input
							ref="searchRef"
							v-model="searchQuery"
							type="text"
							:placeholder="__('Cerca icona...')"
							class="flex-1 bg-transparent text-sm text-ink-gray-7 placeholder-ink-gray-4 outline-none"
						/>
						<button
							v-if="searchQuery"
							@click="searchQuery = ''"
							class="text-ink-gray-4 hover:text-ink-gray-6"
						>
							<X class="w-3 h-3" />
						</button>
					</div>
				</div>

				<!-- Clear selection -->
				<div
					v-if="modelValue"
					class="px-3 py-1.5 border-b border-outline-gray-1"
				>
					<button
						type="button"
						class="text-xs text-ink-gray-5 hover:text-ink-red-3 flex items-center gap-1 transition-colors"
						@click="clearSelection"
					>
						<X class="w-3 h-3" />
						{{ __('Rimuovi icona') }}
					</button>
				</div>

				<!-- Icons grid -->
				<div class="p-2 max-h-56 overflow-y-auto">
					<div v-if="filteredIcons.length" class="grid grid-cols-8 gap-1">
						<button
							v-for="icon in filteredIcons"
							:key="icon.name"
							type="button"
							:title="icon.name"
							class="w-8 h-8 flex items-center justify-center rounded-md hover:bg-surface-gray-2 transition-colors"
							:class="{
								'bg-surface-gray-3 ring-1 ring-outline-gray-3':
									modelValue === icon.name,
							}"
							@click="selectIcon(icon)"
						>
							<component :is="icon.component" class="w-4 h-4 text-ink-gray-7" />
						</button>
					</div>
					<div v-else class="py-6 text-center text-xs text-ink-gray-4">
						{{ __('Nessuna icona trovata') }}
					</div>
				</div>
			</div>
		</Transition>
	</div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import {
	Search,
	X,
	ChevronDown,
	Smile,
	// General
	Home,
	User,
	Users,
	Settings,
	Bell,
	Mail,
	Phone,
	Calendar,
	Clock,
	Star,
	Heart,
	Bookmark,
	Flag,
	Tag,
	Hash,
	Link,
	// Actions
	Plus,
	Minus,
	Check,
	Edit,
	Trash2,
	Copy,
	Download,
	Upload,
	Share2,
	Send,
	RefreshCw,
	RotateCcw,
	ZoomIn,
	ZoomOut,
	// Navigation
	ArrowLeft,
	ArrowRight,
	ArrowUp,
	ArrowDown,
	ChevronLeft,
	ChevronRight,
	ChevronUp,
	Menu,
	MoreHorizontal,
	MoreVertical,
	// Media
	Play,
	Pause,
	Square,
	SkipBack,
	SkipForward,
	Volume2,
	VolumeX,
	Camera,
	Image,
	Video,
	Music,
	Mic,
	Headphones,
	// Files
	File,
	FileText,
	Folder,
	FolderOpen,
	Paperclip,
	Archive,
	// Communication
	MessageSquare,
	MessageCircle,
	AtSign,
	Globe,
	Wifi,
	// Business
	Briefcase,
	Building,
	CreditCard,
	DollarSign,
	TrendingUp,
	TrendingDown,
	BarChart,
	PieChart,
	ShoppingCart,
	Package,
	// Education
	BookOpen,
	Book,
	GraduationCap,
	Award,
	Trophy,
	Target,
	Lightbulb,
	Brain,
	Pencil,
	ClipboardList,
	// Tech
	Code,
	Terminal,
	Database,
	Server,
	Monitor,
	Smartphone,
	Laptop,
	Cpu,
	HardDrive,
	Layers,
	GitBranch,
	Bug,
	// Nature & misc
	Sun,
	Moon,
	Cloud,
	Zap,
	Flame,
	Droplets,
	Leaf,
	Map,
	MapPin,
	Compass,
	Navigation,
	Rocket,
	Plane,
	// Shapes
	Circle,
	Square as SquareIcon,
	Triangle,
	Hexagon,
	Diamond,
	// Status
	AlertCircle,
	AlertTriangle,
	Info,
	CheckCircle,
	XCircle,
	Lock,
	Unlock,
	Shield,
	Eye,
	EyeOff,
} from 'lucide-vue-next'

// ─── Props & Emits ────────────────────────────────────────────────────────────

const props = defineProps<{
	modelValue: string
	label?: string
}>()

const emit = defineEmits<{
	'update:modelValue': [value: string]
}>()

// ─── Stato ───────────────────────────────────────────────────────────────────

const isOpen = ref(false)
const searchQuery = ref('')
const pickerRef = ref<HTMLElement | null>(null)
const searchRef = ref<HTMLInputElement | null>(null)

// ─── Lista icone ─────────────────────────────────────────────────────────────

const allIcons = [
	{ name: 'Home', component: Home },
	{ name: 'User', component: User },
	{ name: 'Users', component: Users },
	{ name: 'Settings', component: Settings },
	{ name: 'Bell', component: Bell },
	{ name: 'Mail', component: Mail },
	{ name: 'Phone', component: Phone },
	{ name: 'Calendar', component: Calendar },
	{ name: 'Clock', component: Clock },
	{ name: 'Star', component: Star },
	{ name: 'Heart', component: Heart },
	{ name: 'Bookmark', component: Bookmark },
	{ name: 'Flag', component: Flag },
	{ name: 'Tag', component: Tag },
	{ name: 'Hash', component: Hash },
	{ name: 'Link', component: Link },
	{ name: 'Plus', component: Plus },
	{ name: 'Minus', component: Minus },
	{ name: 'Check', component: Check },
	{ name: 'Edit', component: Edit },
	{ name: 'Trash2', component: Trash2 },
	{ name: 'Copy', component: Copy },
	{ name: 'Download', component: Download },
	{ name: 'Upload', component: Upload },
	{ name: 'Share2', component: Share2 },
	{ name: 'Send', component: Send },
	{ name: 'RefreshCw', component: RefreshCw },
	{ name: 'ArrowLeft', component: ArrowLeft },
	{ name: 'ArrowRight', component: ArrowRight },
	{ name: 'ArrowUp', component: ArrowUp },
	{ name: 'ArrowDown', component: ArrowDown },
	{ name: 'Play', component: Play },
	{ name: 'Pause', component: Pause },
	{ name: 'Camera', component: Camera },
	{ name: 'Image', component: Image },
	{ name: 'Video', component: Video },
	{ name: 'Music', component: Music },
	{ name: 'Mic', component: Mic },
	{ name: 'Headphones', component: Headphones },
	{ name: 'File', component: File },
	{ name: 'FileText', component: FileText },
	{ name: 'Folder', component: Folder },
	{ name: 'FolderOpen', component: FolderOpen },
	{ name: 'Paperclip', component: Paperclip },
	{ name: 'Archive', component: Archive },
	{ name: 'MessageSquare', component: MessageSquare },
	{ name: 'MessageCircle', component: MessageCircle },
	{ name: 'Globe', component: Globe },
	{ name: 'Wifi', component: Wifi },
	{ name: 'Briefcase', component: Briefcase },
	{ name: 'Building', component: Building },
	{ name: 'CreditCard', component: CreditCard },
	{ name: 'DollarSign', component: DollarSign },
	{ name: 'TrendingUp', component: TrendingUp },
	{ name: 'TrendingDown', component: TrendingDown },
	{ name: 'BarChart', component: BarChart },
	{ name: 'PieChart', component: PieChart },
	{ name: 'ShoppingCart', component: ShoppingCart },
	{ name: 'Package', component: Package },
	{ name: 'BookOpen', component: BookOpen },
	{ name: 'Book', component: Book },
	{ name: 'GraduationCap', component: GraduationCap },
	{ name: 'Award', component: Award },
	{ name: 'Trophy', component: Trophy },
	{ name: 'Target', component: Target },
	{ name: 'Lightbulb', component: Lightbulb },
	{ name: 'Brain', component: Brain },
	{ name: 'Pencil', component: Pencil },
	{ name: 'ClipboardList', component: ClipboardList },
	{ name: 'Code', component: Code },
	{ name: 'Terminal', component: Terminal },
	{ name: 'Database', component: Database },
	{ name: 'Server', component: Server },
	{ name: 'Monitor', component: Monitor },
	{ name: 'Smartphone', component: Smartphone },
	{ name: 'Laptop', component: Laptop },
	{ name: 'Cpu', component: Cpu },
	{ name: 'Layers', component: Layers },
	{ name: 'GitBranch', component: GitBranch },
	{ name: 'Bug', component: Bug },
	{ name: 'Sun', component: Sun },
	{ name: 'Moon', component: Moon },
	{ name: 'Cloud', component: Cloud },
	{ name: 'Zap', component: Zap },
	{ name: 'Flame', component: Flame },
	{ name: 'Leaf', component: Leaf },
	{ name: 'Map', component: Map },
	{ name: 'MapPin', component: MapPin },
	{ name: 'Compass', component: Compass },
	{ name: 'Rocket', component: Rocket },
	{ name: 'Plane', component: Plane },
	{ name: 'AlertCircle', component: AlertCircle },
	{ name: 'AlertTriangle', component: AlertTriangle },
	{ name: 'Info', component: Info },
	{ name: 'CheckCircle', component: CheckCircle },
	{ name: 'XCircle', component: XCircle },
	{ name: 'Lock', component: Lock },
	{ name: 'Unlock', component: Unlock },
	{ name: 'Shield', component: Shield },
	{ name: 'Eye', component: Eye },
	{ name: 'EyeOff', component: EyeOff },
]

// ─── Computed ─────────────────────────────────────────────────────────────────

const filteredIcons = computed(() => {
	if (!searchQuery.value) return allIcons
	const q = searchQuery.value.toLowerCase()
	return allIcons.filter((icon) => icon.name.toLowerCase().includes(q))
})

const selectedIcon = computed(() => {
	if (!props.modelValue) return null
	return allIcons.find((icon) => icon.name === props.modelValue) ?? null
})

// ─── Metodi ───────────────────────────────────────────────────────────────────

const toggleDropdown = () => {
	isOpen.value = !isOpen.value
	if (isOpen.value) {
		searchQuery.value = ''
		nextTick(() => searchRef.value?.focus())
	}
}

const selectIcon = (icon: { name: string; component: any }) => {
	emit('update:modelValue', icon.name)
	isOpen.value = false
}

const clearSelection = () => {
	emit('update:modelValue', '')
	isOpen.value = false
}

// Chiudi cliccando fuori
const handleClickOutside = (e: MouseEvent) => {
	if (pickerRef.value && !pickerRef.value.contains(e.target as Node)) {
		isOpen.value = false
	}
}

onMounted(() => document.addEventListener('mousedown', handleClickOutside))
onBeforeUnmount(() =>
	document.removeEventListener('mousedown', handleClickOutside),
)
</script>

<style scoped>
.icon-picker {
	position: relative;
}

.dropdown-enter-active,
.dropdown-leave-active {
	transition:
		opacity 0.12s ease,
		transform 0.12s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
	opacity: 0;
	transform: translateY(-4px);
}
</style>
