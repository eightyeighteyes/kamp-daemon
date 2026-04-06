/**
 * Extension discovery.
 *
 * Scans two locations for packages that declare the "kamp-extension" keyword:
 *   1. <appPath>/extensions/  — first-party extensions bundled with the app
 *   2. <appPath>/node_modules/ — installed npm extensions
 *
 * A package qualifies when its package.json has "kamp-extension" in `keywords`
 * and its declared entry point (`main`) exists on disk.
 */

import { app } from 'electron'
import { readdirSync, readFileSync, existsSync } from 'fs'
import { join, resolve } from 'path'
import type { ExtensionInfo } from '../shared/kampAPI'

function scanDir(dir: string): ExtensionInfo[] {
  if (!existsSync(dir)) return []

  const results: ExtensionInfo[] = []

  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue

    const pkgPath = join(dir, entry.name, 'package.json')
    if (!existsSync(pkgPath)) continue

    try {
      const pkg = JSON.parse(readFileSync(pkgPath, 'utf8')) as {
        name?: string
        displayName?: string
        keywords?: string[]
        main?: string
      }

      if (!Array.isArray(pkg.keywords) || !pkg.keywords.includes('kamp-extension')) continue

      const mainFile = pkg.main ?? 'index.js'
      const entryPath = resolve(dir, entry.name, mainFile)
      if (!existsSync(entryPath)) continue

      // Read code here in the main process (which has fs access) so the
      // renderer never needs a file:// import — it loads via a Blob URL instead.
      const code = readFileSync(entryPath, 'utf8')

      results.push({
        id: pkg.name ?? entry.name,
        name: pkg.displayName ?? pkg.name ?? entry.name,
        code
      })
    } catch {
      // Skip packages with malformed package.json.
    }
  }

  return results
}

export function discoverExtensions(): ExtensionInfo[] {
  const appPath = app.getAppPath()
  // First-party extensions ship alongside the app.
  const builtinDir = join(appPath, 'extensions')
  // Installed npm extensions live in node_modules.
  const nodeModulesDir = join(appPath, 'node_modules')

  return [...scanDir(builtinDir), ...scanDir(nodeModulesDir)]
}
