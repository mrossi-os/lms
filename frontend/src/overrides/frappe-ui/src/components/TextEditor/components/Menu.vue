<!--
  Override of frappe-ui's TextEditor Menu.vue via the osOverrideTheme Vite
  plugin. Menu.vue is the shared renderer for the fixed toolbar (and its
  dropdowns, e.g. the table menu). The ONLY changes from upstream are:
    1. Every visible button/option label + tooltip is wrapped in __() so the
       hardcoded English labels from commands.js become translatable.
    2. The Popover import is repointed at the original file in node_modules
       (a bare relative import would resolve inside src/overrides and 404).
  Keep this file in sync with
  node_modules/frappe-ui/src/components/TextEditor/components/Menu.vue after any
  upstream frappe-ui bump.
-->
<template>
  <div class="inline-flex bg-surface-base p-1">
    <div class="inline-flex items-center gap-1.5">
      <template
        v-for="(button, index) in buttons"
        :key="button?.label || button?.type || `btn-${index}`"
      >
        <template
          v-if="button && (!button.condition || button.condition(editor))"
        >
          <div
            class="h-4 w-[2px] border-l"
            v-if="button && button.type === 'separator'"
          ></div>
          <div class="shrink-0" v-else-if="button && button.map">
            <Popover>
              <template #target="{ togglePopover }">
                <button
                  class="rounded p-1 text-base-medium text-ink-gray-8 transition-colors"
                  @click="togglePopover"
                  :class="
                    getActiveButton(button)
                      ? 'bg-surface-gray-3'
                      : 'hover:bg-surface-gray-2'
                  "
                >
                  <component
                    v-if="(getActiveButton(button) || button[0]).icon"
                    :is="(getActiveButton(button) || button[0]).icon"
                    class="h-4 w-4"
                  />
                  <span v-else>
                    {{ __((getActiveButton(button) || button[0]).label) }}
                  </span>
                </button>
              </template>
              <template #body="{ close }">
                <ul
                  class="p-1.5 mt-2 rounded-lg bg-surface-elevation-2 shadow-2xl ring-1 ring-black ring-opacity-5 focus:outline-none"
                >
                  <li
                    v-for="option in button"
                    v-show="option.condition ? option.condition(editor) : true"
                  >
                    <component
                      v-if="option.component"
                      :is="option.component || 'div'"
                      v-bind="{ editor }"
                    >
                      <template v-slot="componentSlotProps">
                        <button
                          class="w-full h-7 rounded px-2 text-base flex items-center gap-2 hover:bg-surface-gray-3"
                          :class="
                            option.isDisabled?.(editor) &&
                            'opacity-50 pointer-events-none'
                          "
                          @click="
                            () => {
                              if (componentSlotProps?.onClick)
                                componentSlotProps.onClick(option)
                              else if (option.action) onButtonClick(option)

                              close()
                            }
                          "
                          :title="__(option.label)"
                        >
                          <component
                            v-if="option.icon"
                            :is="option.icon"
                            class="h-4 w-4"
                          />
                          <span
                            class="whitespace-nowrap text-ink-gray-7"
                            v-if="option.label"
                          >
                            {{ __(option.label) }}
                          </span>
                        </button>
                      </template>
                    </component>
                    <button
                      v-else
                      class="w-full h-7 rounded px-2 text-base flex items-center gap-2 hover:bg-surface-gray-3"
                      :class="
                        option.isDisabled?.(editor) &&
                        'opacity-50 pointer-events-none'
                      "
                      @click="
                        () => {
                          if (!option.action) return
                          onButtonClick(option)
                          close()
                        }
                      "
                    >
                      <component
                        v-if="option.icon"
                        :is="option.icon"
                        class="size-4 flex-shrink-0 text-ink-gray-6"
                      />
                      <span
                        v-if="option.label"
                        class="whitespace-nowrap text-ink-gray-7"
                        >{{ __(option.label) }}</span
                      >
                    </button>
                  </li>
                </ul>
              </template>
            </Popover>
          </div>
          <button
            v-else-if="!button.component"
            class="flex rounded text-ink-gray-8 transition-colors focus-within:ring-0"
            :class="[
              buttons.length > 1 ? 'p-1' : 'p-1.5 border',
              button.isDisabled?.(editor) && 'opacity-50 pointer-events-none',
              button.isActive?.(editor)
                ? 'bg-surface-gray-3'
                : 'hover:bg-surface-gray-2',
              button.class,
            ]"
            @click="onButtonClick(button)"
            :title="__(button.label || button.text)"
          >
            <component v-if="button.icon" :is="button.icon" class="h-4 w-4" />
            <span
              class="inline-block h-4 min-w-[1rem] text-sm leading-4"
              v-else-if="button.text"
            >
              {{ __(button.text) }}
            </span>
            <span
              class="inline-block h-4 min-w-[1rem] text-sm leading-4"
              v-else-if="button.label"
            >
              {{ __(button.label) }}
            </span>
          </button>
          <Suspense v-else-if="button.component">
            <component :is="button.component || 'div'" v-bind="{ editor }">
              <template v-slot="componentSlotProps">
                <button
                  class="flex rounded p-1 text-ink-gray-8 transition-colors"
                  :class="[
                    button.isDisabled?.(editor) &&
                      'opacity-50 pointer-events-none',
                    button.isActive?.(editor) || componentSlotProps?.isActive
                      ? 'bg-surface-gray-3'
                      : 'hover:bg-surface-gray-2',
                    button.class,
                  ]"
                  @click="
                    componentSlotProps?.onClick
                      ? componentSlotProps.onClick(button)
                      : onButtonClick(button)
                  "
                  :title="__(button.label)"
                >
                  <component
                    v-if="button.icon"
                    :is="button.icon"
                    class="h-4 w-4"
                  />
                  <span
                    class="inline-block h-4 min-w-[1rem] text-sm leading-4"
                    v-else
                  >
                    {{ __(button.text) }}
                  </span>
                </button>
              </template>
            </component>
            <template #fallback>
              <button
                class="flex rounded p-1 text-ink-gray-8 transition-colors"
                :class="[
                  button.isDisabled?.(editor) &&
                    'opacity-50 pointer-events-none',
                  'hover:bg-surface-gray-2',
                  button.class,
                ]"
                @click="onButtonClick(button)"
                :title="__(button.label)"
              >
                <component
                  v-if="button.icon"
                  :is="button.icon"
                  class="h-4 w-4"
                />
                <span
                  class="inline-block h-4 min-w-[1rem] text-sm leading-4"
                  v-else
                >
                  {{ __(button.text) }}
                </span>
              </button></template
            >
          </Suspense>
        </template>
      </template>
    </div>
  </div>
</template>
<script setup>
import Popover from '../../../../../../../node_modules/frappe-ui/src/components/Popover/Popover.vue'
import { inject } from 'vue'

const props = defineProps({
  buttons: Array,
})
const editor = inject('editor')

const onButtonClick = (button) => {
  button.action(editor.value)
}
const getActiveButton = (group) => {
  return group.find((b) => b.isActive?.(editor.value))
}
</script>
