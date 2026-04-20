---
id: TASK-168
title: >-
  eliminate keychain dialog after app updates via Developer ID provisioning
  profile
status: To Do
assignee: []
created_date: '2026-04-20 21:30'
labels: []
dependencies:
  - TASK-167
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Background

TASK-167 fixed "dialog on every launch" by replacing keyring's delete+recreate with SecItemUpdate, which preserves the item ACL. However, the Login Keychain still uses binary-hash ACLs — each new PyInstaller build changes the `kamp` daemon binary's hash, so macOS treats it as a new application after every release and prompts again.

The permanent fix is to use `kSecUseDataProtectionKeychain: True` in `kamp_core/macos_keychain.py`. The Data Protection Keychain uses the app's code-signing identity (team ID + bundle ID) instead of binary hashes, so the ACL survives updates. This requires:

1. The `keychain-access-groups` entitlement in the app bundle
2. A **Developer ID Application provisioning profile** that includes the Keychain Sharing capability — without it, `keychain-access-groups` is a restricted entitlement and `taskgated` kills the process at launch (the crash TASK-167 encountered)

## Developer Portal steps (manual — must be done before any code changes)

### 1. Enable Keychain Sharing on the App ID

1. Sign in to [developer.apple.com](https://developer.apple.com) → **Certificates, Identifiers & Profiles** → **Identifiers**
2. Find the App ID for `com.kamp.app` (or create it if absent)
3. Under **Capabilities**, enable **Keychain Sharing**
4. Add one keychain group: `com.kamp.app` (without team prefix — Apple prepends it automatically)
5. Save

### 2. Create a Developer ID Application provisioning profile

1. Go to **Profiles** → click **+**
2. Under **Distribution**, select **Developer ID Application**
3. Select the `com.kamp.app` App ID configured above
4. Select the **Developer ID Application** certificate (the one used to sign Kamp releases)
5. Click **Generate**, then **Download** — save as e.g. `KampDeveloperID.provisionprofile`

### 3. Place the profile in the repo

Put the downloaded `.provisionprofile` file somewhere in the repo (e.g. `kamp_ui/build/KampDeveloperID.provisionprofile`) and reference it in `kamp_ui/electron-builder.yml` (or equivalent config) via the `provisioningProfile` field under `mac`. Check whether to gitignore it or commit it (profiles are not secret, but they do expire annually).

## Code changes (after portal steps are done)

### `kamp_core/macos_keychain.py`
Re-add `kSecUseDataProtectionKeychain=True` to all three functions (`get_password`, `set_password`, `delete_password`) and re-add `KeyringEntitlementError` / `_ERR_SEC_MISSING_ENTITLEMENT` for dev-build fallback.

### `kamp_ui/build/entitlements.mac.plist`
Re-add:
```xml
<key>keychain-access-groups</key>
<array>
    <string>$(AppIdentifierPrefix)com.kamp.app</string>
</array>
```
`$(AppIdentifierPrefix)` is expanded by `codesign` to `TEAMID.` automatically.

### `kamp_core/library.py`
Re-add the `_mac_kc_entitlement_missing` flag and `_KeyringEntitlementError` fallback (for unsigned dev builds that lack the entitlement). This was the code that existed on the TASK-167 branch before the entitlement was removed. The git history on `task-167-data-protection-keychain` has a working reference implementation.

### One-time migration
Users upgrading from the Login Keychain version will have existing items stored without `kSecUseDataProtectionKeychain`. The Data Protection Keychain is a separate namespace — `get_password` with the flag set will NOT find items created without it. A migration block in `get_session` is needed: if DPC returns None, check the Login Keychain (via `keyring.get_password`), and if found, write to DPC and delete the Login Keychain copy. This migration ran once per item and was already implemented on the TASK-167 branch.

## Verification

1. Build and sign the app with the provisioning profile embedded
2. Launch — confirm no Keychain dialog (Data Protection Keychain items don't trigger per-app dialogs)
3. Simulate an update: rebuild with the same signing identity but a new binary. Re-launch — confirm no dialog
4. `security find-generic-password -s kamp` should show the item in the data-protection keychain, not the login keychain
5. Dev (unsigned) build should fall back gracefully to Login Keychain with `SecItemUpdate` (TASK-167 behavior)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Developer portal: App ID com.kamp.app has Keychain Sharing enabled with group com.kamp.app
- [ ] #2 Developer portal: Developer ID Application provisioning profile downloaded and referenced in electron-builder config
- [ ] #3 Signed build launches with no Keychain dialog — including on first launch after an app update
- [ ] #4 Dev (unsigned) build falls back to Login Keychain without crashing
- [ ] #5 All tests pass
<!-- AC:END -->
