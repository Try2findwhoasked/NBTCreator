$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

$probeRoot = Join-Path $PWD ('build/ci-model-delivery-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $probeRoot | Out-Null
Write-Output "Model delivery evidence: $probeRoot"

node tests/run-suite.mjs projects
node --test tests/node/backend-result.test.mjs tests/node/mesh-scheduling.test.mjs
node tests/desktop/mesh-scheduling-desktop.mjs
python tests/engine/render-runtime.py
python tests/engine/feedback-index.py
node tests/node/feedback-evidence.mjs
python tests/engine/standalone-openings.py
python tests/engine/standalone-pipeline.py --output (Join-Path $probeRoot 'standalone')
python tests/engine/candidate-validation.py
node .agents/skills/minecraft-nbt-modeler/assets/viewer/test-candidate-validation.mjs --output (Join-Path $probeRoot 'candidate-browser')
node --test tests/node/workspace-api.test.cjs
node tests/node/task-cancel.mjs --output (Join-Path $probeRoot 'task-cancel')
python .agents/skills/minecraft-nbt-modeler/scripts/fixtures/run.py check_collision_fixtures.py --output (Join-Path $probeRoot 'collision.json')
python .agents/skills/minecraft-nbt-modeler/scripts/fixtures/run.py check_refine_fixtures.py --output (Join-Path $probeRoot 'refine')
python .agents/skills/minecraft-nbt-modeler/scripts/fixtures/run.py check_web_revision_fixtures.py --output (Join-Path $probeRoot 'web-revision')
