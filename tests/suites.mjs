const node = (...args) => [process.execPath, ...args]
const python = (...args) => ['python', ...args]
const buildWeb = node('scripts/build-web.mjs')

export const suites = {
  'agent-protocol': [python('-B', 'tests/engine/agent-protocol.py')],
  'agent-return': [
    buildWeb,
    python('tests/engine/agent-task-return.py'),
    node('tests/desktop/agent-task-return-desktop.mjs'),
  ],
  'agent-simulation': [node('tests/acceptance/agent-simulation.mjs')],
  'ai-batch': [
    buildWeb,
    node('tests/desktop/ai-batch-desktop.mjs'),
  ],
  'ai-live': [node('tests/desktop/ai-live-desktop.mjs')],
  'ai-style': [
    node('--test', 'tests/node/ai-style.test.cjs', 'tests/node/internal-ai.test.cjs'),
    node('tests/desktop/ai-style-desktop.mjs'),
  ],
  'api': [
    node(
      '--test',
      '--test-concurrency=1',
      'tests/node/ai-speed.test.cjs',
      'tests/node/worktree-integration.test.cjs',
      'tests/node/compact-structure.test.cjs',
      'tests/node/ai-output-normalize.test.cjs',
      'tests/node/prompt-beam.test.cjs',
      'tests/node/prompt-brief.test.cjs',
      'tests/node/ai-character-limit.test.cjs',
      'tests/node/ai-result-extract.test.cjs',
      'tests/node/ai-candidate-validator.test.cjs',
      'tests/node/selection-edit.test.cjs',
      'tests/node/api-service.test.cjs',
      'tests/node/ai-concurrency.test.cjs',
      'tests/node/frontend-ai-cancel.test.mjs',
      'tests/node/workspace-api.test.cjs',
      'tests/node/workbench-contract.test.cjs',
      'tests/node/project-standards.test.cjs',
      'tests/node/ai-input.test.cjs',
      'tests/node/ai-metrics.test.mjs',
      'tests/node/internal-ai.test.cjs',
      'tests/node/internal-skill.test.cjs',
      'tests/node/ai-component.test.mjs',
      'tests/node/engine-session.test.mjs',
    ),
  ],
  'api-desktop': [
    node('tests/desktop/api-desktop.mjs'),
    node('tests/desktop/ai-speed-desktop.mjs'),
  ],
  'architect': [
    buildWeb,
    node('tests/desktop/architect-workspace-desktop.mjs'),
    python('tests/engine/prompt-archive.py'),
  ],
  'architect-tools': [
    buildWeb,
    python('-B', 'tests/engine/architect-tools.py'),
    node('tests/desktop/architect-tools-desktop.mjs'),
  ],
  'architecture-preview': [
    buildWeb,
    node('tests/desktop/architecture-preview.mjs'),
  ],
  'architecture-workflow': [python('-B', 'tests/engine/architecture-workflow.py')],
  'building-failure-replay': [python('-B', 'tests/engine/building-failure-replay.py')],
  'asset-batches': [
    buildWeb,
    python('tests/engine/asset-batches.py'),
    node('tests/desktop/asset-batches-desktop.mjs'),
  ],
  'asset-interaction': [
    buildWeb,
    node('tests/desktop/asset-interaction-desktop.mjs'),
  ],
  'asset-libraries': [python('-B', 'tests/engine/asset-libraries.py')],
  'assets': [
    python('tests/engine/components.py'),
    python('tests/engine/structure-agent.py'),
    node('tests/desktop/asset-workspace-desktop.mjs'),
    node('tests/desktop/structure-agent-desktop.mjs'),
  ],
  'authoring-journey': [
    buildWeb,
    node('tests/desktop/authoring-journey-desktop.mjs'),
  ],
  'beam-rhythm': [python('-B', 'tests/engine/beam-rhythm.py')],
  'batches': [
    buildWeb,
    python('tests/engine/batches.py'),
    node('--test', 'tests/node/batch-links.test.cjs'),
    node('tests/desktop/batch-workspaces-desktop.mjs'),
  ],
  'building-quality': [
    buildWeb,
    python('-B', 'tests/engine/building-quality.py'),
    node('tests/desktop/building-quality.mjs'),
  ],
  'catalog': [
    python('tests/engine/catalog-nbt.py'),
    node('tests/desktop/catalog-desktop.mjs'),
  ],
  'compare': [
    buildWeb,
    python('tests/engine/model-difference.py'),
    node('--test', 'tests/node/difference-index.test.mjs'),
    node('tests/desktop/version-compare-desktop.mjs'),
  ],
  'constraints': [
    buildWeb,
    python('-B', 'tests/engine/project-constraints.py'),
    python('-B', 'tests/engine/constraint-room-layout.py'),
    node('--test', 'tests/node/project-constraints.test.cjs', 'tests/node/prompt-creation.mjs'),
    node('tests/desktop/project-constraints-desktop.mjs'),
    node('tests/desktop/constraint-room-layout-desktop.mjs'),
  ],
  'control-availability': [
    buildWeb,
    python('tests/engine/reusable-recipes.py'),
    node('tests/desktop/control-availability-desktop.mjs'),
  ],
  'curve-components': [python('-B', 'tests/engine/curve-components.py')],
  'curve-stencils': [python('-B', 'tests/engine/curve-stencils.py')],
  'curved-surface': [python('-B', 'tests/engine/curved-surface.py')],
  'desktop': [
    node('--test', 'tests/node/render-pack.test.mjs'),
    node('tests/desktop/desktop-smoke.mjs'),
  ],
  'diagnostics': [
    buildWeb,
    python('tests/engine/diagnostic-guidance.py'),
    node('tests/desktop/walk-desktop.mjs'),
    node('tests/desktop/protection-desktop.mjs'),
  ],
  'editing': [
    buildWeb,
    node('--test', 'tests/node/settings-history.test.mjs'),
    python('tests/engine/operation-history.py'),
    node('tests/desktop/operation-history-desktop.mjs'),
    node('tests/desktop/preview-toolbar-desktop.mjs'),
  ],
  'engine-session': [node('--test', 'tests/node/engine-session.test.mjs')],
  'extensions': [python('-B', 'tests/engine/extensions.py')],
  'feedback-autosave': [
    buildWeb,
    node('--test', 'tests/node/feedback-autosave.test.mjs'),
    node('tests/desktop/feedback-autosave-desktop.mjs'),
  ],
  'feedback-tasks': [
    buildWeb,
    python('tests/engine/feedback-tasks.py'),
    node('tests/desktop/feedback-tasks-desktop.mjs'),
  ],
  'fitting-shapes': [
    python('-B', 'tests/engine/fitting-shapes.py'),
    python('-B', 'tests/engine/ornament-reference.py'),
    python('-B', 'tests/engine/fine-collision-envelopes.py'),
  ],
  'generated-assets': [
    buildWeb,
    python('tests/engine/generated-assets.py'),
    node('tests/desktop/structure-agent-desktop.mjs'),
  ],
  'history': [
    buildWeb,
    python('tests/engine/building-history.py'),
    python('tests/engine/snbt-source.py'),
    node('tests/desktop/building-history-desktop.mjs'),
  ],
  'large-assembly': [python('-B', 'tests/engine/large-assembly-scale.py')],
  'library-layout': [
    buildWeb,
    node('tests/desktop/library-layout-desktop.mjs'),
    node('tests/desktop/library-journey-desktop.mjs'),
  ],
  'materialization': [python('-B', 'tests/engine/materialization.py')],
  'model-preview': [
    buildWeb,
    node('tests/desktop/working-model-render.mjs'),
    node('tests/desktop/large-assembly-desktop.mjs'),
  ],
  'model-workflow': [
    python('-B', 'tests/engine/working-model.py'),
    python('-B', 'tests/engine/large-assembly.py'),
    python('-B', 'tests/engine/large-handoff.py'),
    python('-B', 'tests/engine/scene-interfaces.py'),
    python('-B', 'tests/engine/object-scenes.py'),
  ],
  'modelling': [
    python('tests/engine/modelling-suite.py'),
    node('--test', 'tests/node/operation-parameters.test.cjs'),
  ],
  'modular': [
    python('-B', 'tests/engine/modular-objects.py'),
    python('-B', 'tests/engine/structural-members.py'),
    python('-B', 'tests/engine/window-frames.py'),
  ],
  'object-scenes': [python('-B', 'tests/engine/object-scenes.py')],
  'parametric': [
    python('-B', 'tests/engine/parametric-components.py'),
    python('-B', 'tests/engine/structure-agent.py'),
    python('-B', 'tests/engine/surface-mount.py'),
    python('-B', 'tests/engine/cylinder-patterns.py'),
    python('-B', 'tests/engine/pattern-assets.py'),
    python('-B', 'tests/engine/micro-patterns.py'),
    python('-B', 'tests/engine/fitting-shapes.py'),
    python('-B', 'tests/engine/ornament-reference.py'),
    python('-B', 'tests/engine/fine-collision-envelopes.py'),
    python('-B', 'tests/engine/micro-presets.py'),
    python('-B', 'tests/engine/pattern-integration.py'),
    python('-B', 'tests/engine/modeling-session.py'),
    python('-B', 'tests/engine/object-scenes.py'),
    python('-B', 'tests/engine/mount-batch-linkage.py'),
    python('-B', 'tests/engine/pillar-spectral.py'),
    python('-B', 'tests/engine/classical-columns.py'),
    python('-B', 'tests/engine/bitmap-topology.py'),
    python('-B', 'tests/engine/ornate-fitting.py'),
    python('-B', 'tests/engine/architectural-bay.py'),
    python('-B', 'tests/engine/compute-transforms.py'),
    python('-B', 'tests/engine/materialization.py'),
  ],
  'pattern-assets': [
    buildWeb,
    python('-B', 'tests/engine/pattern-assets.py'),
    node('tests/desktop/pattern-assets-desktop.mjs'),
  ],
  'pattern-repeat': [python('-B', 'tests/engine/pattern-repeat.py')],
  'portable': [node('tests/desktop/portable-smoke.mjs')],
  'preview-defaults': [
    buildWeb,
    node('--test', 'tests/node/app-settings.test.cjs'),
    node('tests/desktop/default-preview-desktop.mjs'),
  ],
  'product': [node('tests/acceptance/product-acceptance.mjs')],
  'production': [node('tests/desktop/production-server.mjs')],
  'project-batch': [
    buildWeb,
    python('tests/engine/project-batch.py'),
    node('tests/desktop/project-batch-desktop.mjs'),
  ],
  'project-menus': [
    buildWeb,
    node('--test', 'tests/node/project-organization.test.mjs'),
    node('tests/desktop/project-menus-desktop.mjs'),
  ],
  'project-repair': [
    buildWeb,
    python('tests/engine/project-repair.py'),
    node('tests/desktop/project-recovery-desktop.mjs'),
  ],
  'projects': [
    python('tests/engine/section-cover.py'),
    node(
      '--test',
      'tests/node/project-catalog.test.mjs',
      'tests/node/catalog-store.test.mjs',
      'tests/node/project-stages.test.mjs',
      'tests/node/camera-controls.test.mjs',
    ),
    node('tests/desktop/project-manager-desktop.mjs'),
    node('tests/desktop/project-performance.mjs'),
  ],
  'prompt-archive': [
    buildWeb,
    python('tests/engine/prompt-archive.py'),
    node('tests/desktop/prompt-archive-desktop.mjs'),
    node('tests/desktop/prompt-task-desktop.mjs'),
    node('tests/desktop/prompt-brief-desktop.mjs'),
  ],
  'protection': [
    buildWeb,
    python('tests/engine/protection-mask.py'),
    node('tests/desktop/protection-desktop.mjs'),
  ],
  'recipes': [
    buildWeb,
    python('tests/engine/reusable-recipes.py'),
    node('tests/desktop/reusable-desktop.mjs'),
  ],
  'recovery': [
    buildWeb,
    node('--test', 'tests/node/edit-session-store.test.mjs', 'tests/node/edit-session-controller.test.mjs', 'tests/node/app-settings.test.cjs'),
    node('tests/desktop/edit-session-desktop.mjs'),
    node('tests/desktop/edit-session-images-desktop.mjs'),
  ],
  'reference-views': [
    python('-B', 'tests/engine/reference-views.py'),
    python('-B', 'tests/engine/blind-review.py'),
  ],
  'retrieval': [
    buildWeb,
    python('-B', 'tests/engine/retrieval.py'),
    python('-B', 'tests/engine/web-research.py'),
    node('--test', 'tests/node/retrieval.test.cjs'),
    node('tests/desktop/retrieval-desktop.mjs'),
  ],
  'roads': [
    buildWeb,
    python('tests/engine/auto-roads.py'),
    node('tests/desktop/auto-roads-desktop.mjs'),
  ],
  'roof-curves': [python('-B', 'tests/engine/roof-curves.py')],
  'room-score': [
    buildWeb,
    python('tests/engine/room-score.py'),
    node('tests/desktop/room-score-desktop.mjs'),
  ],
  'selection-edit': [
    buildWeb,
    python('tests/engine/selection-edit.py'),
    node('--test', 'tests/node/selection-edit.test.cjs'),
    node('tests/desktop/selection-edit-desktop.mjs'),
  ],
  'studio': [
    buildWeb,
    node('--test', 'tests/node/authoring-flow.test.mjs'),
    node('tests/desktop/studio-workspace-desktop.mjs'),
    node('tests/desktop/interaction-guidance-desktop.mjs'),
  ],
  'studio-redesign': [
    buildWeb,
    node('tests/desktop/studio-redesign-desktop.mjs'),
  ],
  'test-runner': [node('--test', 'tests/node/test-suite.test.mjs')],
  'tool-effects': [
    buildWeb,
    python('tests/engine/starter-effects.py'),
    python('tests/engine/effect-assets.py'),
    node('tests/desktop/tool-effects-desktop.mjs'),
    node('tests/desktop/effect-gallery-desktop.mjs'),
  ],
  'transforms': [
    buildWeb,
    node('--test', 'tests/node/ai-component.test.mjs', 'tests/node/edit-session-store.test.mjs'),
    python('tests/engine/components.py'),
    node('tests/desktop/transform-sliders-desktop.mjs'),
  ],
  'unified-assets': [
    buildWeb,
    node('tests/desktop/unified-assets-desktop.mjs'),
  ],
  'updates': [
    buildWeb,
    node('--test', 'tests/node/updater.test.cjs'),
    node('tests/desktop/updater-desktop.mjs'),
  ],
  'walk': [
    buildWeb,
    python('tests/engine/walk-inspection.py'),
    node('tests/desktop/walk-desktop.mjs'),
  ],
  'wavelet-eave': [python('-B', 'tests/engine/wavelet-eave.py')],
  'workbench-ui': [
    buildWeb,
    node('tests/desktop/workbench-ui-desktop.mjs'),
  ],
  'workspace': [
    python('tests/engine/workspace-contracts.py'),
    node('--test', 'tests/node/workspace-resolution.cjs'),
  ],
}

export function suiteCommands(name, mode) {
  if (!Object.hasOwn(suites, name)) return undefined
  if (mode === '--prebuilt') return suites[name].filter(step => step !== buildWeb)
  if (mode === '--desktop-only') {
    return suites[name].filter(([executable, file]) =>
      executable === process.execPath && file.startsWith('tests/desktop/'))
  }
  return suites[name]
}
