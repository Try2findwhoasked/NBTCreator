param([string]$OutputDirectory = 'dist/portable')

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

npm.cmd run package:portable -- --out $OutputDirectory
npm.cmd run test:portable -- --archive-dir $OutputDirectory

$env:NBTCREATOR_TEST_EXE = Join-Path (Resolve-Path -LiteralPath $OutputDirectory).Path 'NBTCreator-win32-x64/NBTCreator.exe'
Remove-Item Env:NBTCREATOR_PYTHON -ErrorAction SilentlyContinue
npm.cmd run test:desktop
node tests/desktop/updater-desktop.mjs
npm.cmd run test:api-desktop
node tests/desktop/protection-desktop.mjs
node tests/desktop/walk-desktop.mjs
node tests/desktop/prompt-archive-desktop.mjs
node tests/desktop/mesh-scheduling-desktop.mjs
node tests/desktop/workspace-api-desktop.mjs
node tests/desktop/feedback-tasks-desktop.mjs
node tests/desktop/batch-workspaces-desktop.mjs
node tests/desktop/selection-edit-desktop.mjs
node tests/desktop/retrieval-desktop.mjs
node tests/desktop/agent-task-return-desktop.mjs
