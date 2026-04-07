---
id: TASK-22
title: Extension settings UI
status: In Progress
assignee:
  - Claude
created_date: '2026-03-29 03:12'
updated_date: '2026-04-07 21:54'
labels:
  - feature
  - ui
  - 'estimate: side'
milestone: m-2
dependencies: []
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add a settings UI where users can view installed extensions, enable/disable them, and configure per-extension settings. Extensions declare their settings schema in their manifest; the host renders the settings form.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Settings screen lists all installed extensions with name, version, and enabled state
- [x] #2 User can enable/disable extensions from the UI
- [x] #3 Per-extension settings are rendered from the extension's declared schema
- [x] #4 Settings changes take effect without requiring an app restart
- [x] #5 First load of a community extension shows a permission prompt listing its declared permissions; the extension only loads after explicit user approval
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Implementation Plan

### Files changed
- `kamp_ui/src/shared/kampAPI.ts` — added `ExtensionSettingSchema` type; added `version` and `settings?` to `ExtensionInfo`; added `settings?` API to `KampAPI`
- `kamp_ui/src/main/extensions.ts` — reads `version` and `kamp.settings` schema from package.json; validates schema entries
- `kamp_ui/src/renderer/src/hooks/useExtensionState.ts` (new) — localStorage-backed state for disabled set, approved/denied sets, per-extension setting values
- `kamp_ui/src/renderer/src/components/ExtensionPermissionPrompt.tsx` (new) — permission approval modal for Phase 2 community extensions
- `kamp_ui/src/renderer/src/components/PreferencesDialog.tsx` — added tab bar (General | Extensions); Extensions tab renders ExtensionsPanel with per-extension rows (toggle, badge, Configure drawer)
- `kamp_ui/src/renderer/src/App.tsx` — wired useExtensionState; filters disabled extensions; routes Phase 2 through approved/denied/pending sets; shows permission prompt queue; passes settings API to Phase 1 extensions with the 'settings' permission
- `kamp_ui/src/renderer/src/assets/main.css` — tab bar, toggle switch, extension rows, phase badge, configure drawer, empty state, permission prompt dialog

### Key design decisions
- **Enable/disable**: disabling marks the id in localStorage; takes effect on next load (reload badge shown). Enabling an extension that was disabled re-triggers the load effect because `disabledIds` is in the effect dependency array.
- **Per-extension settings (AC#4)**: values live in localStorage; `KampAPI.settings.get(key)` reads directly from the store at any time — no restart required. Only available when the extension declares the `'settings'` permission.
- **Permission prompt (AC#5)**: Phase 2 extensions not yet in approved/denied sets go into a pending queue. App shows one prompt at a time via `permissionQueue[0]`. Approve → extension loads in its iframe; Deny → skipped, not prompted again.
- **Settings schema**: extensions declare `kamp.settings` in package.json as an array of `{key, label, type, options?, default?, hint?}`. The host renders `text`, `number`, `boolean` (toggle), and `select` field types.
<!-- SECTION:PLAN:END -->
