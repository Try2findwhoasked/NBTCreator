param([string]$OutputDirectory = 'dist/portable')

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

npm.cmd run package:portable -- --out $OutputDirectory
node tests/run-suite.mjs portable --archive-dir $OutputDirectory
$env:NBTCREATOR_TEST_AGENT_ARCHIVE = Join-Path (Resolve-Path -LiteralPath $OutputDirectory).Path ("NBTCreator-Agent-{0}-windows-x64.zip" -f (Get-Content package.json -Raw | ConvertFrom-Json).version)
node tests/run-suite.mjs --prebuilt mcp
Remove-Item Env:NBTCREATOR_TEST_AGENT_ARCHIVE

$env:NBTCREATOR_TEST_EXE = Join-Path (Resolve-Path -LiteralPath $OutputDirectory).Path 'NBTCreator-win32-x64/NBTCreator.exe'
Remove-Item Env:NBTCREATOR_PYTHON -ErrorAction SilentlyContinue
node tests/run-suite.mjs desktop
node tests/run-suite.mjs --prebuilt mcp-desktop
node tests/run-suite.mjs --desktop-only updates
node tests/run-suite.mjs api-desktop
node tests/run-suite.mjs --desktop-only protection
node tests/run-suite.mjs --desktop-only walk
node tests/desktop/prompt-archive-desktop.mjs
node tests/desktop/mesh-scheduling-desktop.mjs
node tests/desktop/workspace-api-desktop.mjs
node tests/run-suite.mjs --desktop-only feedback-tasks
node tests/run-suite.mjs --desktop-only batches
node tests/run-suite.mjs --desktop-only selection-edit
node tests/run-suite.mjs --desktop-only retrieval
node tests/run-suite.mjs --desktop-only agent-return
