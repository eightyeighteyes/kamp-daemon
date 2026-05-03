export function revealInFinderLabel(): string {
  const p = window.electron.process.platform
  if (p === 'darwin') return '↗ Reveal in Finder'
  if (p === 'win32') return '↗ Show in Explorer'
  return '↗ Show in Files'
}
