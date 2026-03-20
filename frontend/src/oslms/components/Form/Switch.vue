<template>
  <Switch v-bind="$attrs" class="component-switch" />
</template>

<script setup>
import { Switch } from 'frappe-ui'

defineOptions({
  inheritAttrs: false,
})
</script>