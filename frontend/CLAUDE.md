# frontend/CLAUDE.md

## Component Override System (`osOverrideTheme` Vite plugin)

The `osOverrideTheme` Vite plugin (defined in `frontend/vite.config.js`) enables overriding Vue components from `node_modules` (e.g. `frappe-ui`) without forking the package. To override a component:

1. Identify the component's path relative to `node_modules/` (e.g. `frappe-ui/src/components/Button.vue`).
2. Create a file at the same relative path under `frontend/src/overrides/` (e.g. `frontend/src/overrides/frappe-ui/src/components/Button.vue`).
3. The plugin will automatically resolve imports to the override instead of the original.

The plugin runs with `enforce: 'pre'` and only intercepts relative `.vue` imports that resolve inside `node_modules/`.
