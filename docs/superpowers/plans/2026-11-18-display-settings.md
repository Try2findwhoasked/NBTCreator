# Display Settings Implementation Plan

> **For agentic workers:** Steps use checkbox syntax for tracking. The current agent executes these steps natively in this chat.

**Goal:** Replace the loose display popover with the approved compact groups and direct overlay switches.

**Architecture:** Reparent existing renderer controls in `studio-workspace.js`; keep the walk and protection modules as the owners of overlay state. Synchronize new quick switches through UI events and keep the detailed inspection panels intact.

**Tech Stack:** Electron renderer JavaScript, CSS, Playwright desktop tests.

**Spec:** `docs/superpowers/specs/2026-11-18-display-settings-design.md`

## Global Constraints

- Keep Host/Origin checks, source hashes, separate manual export, and real thumbnail confirmation intact.
- Use project mise tasks for build and verification; keep Python outside the renderer.

## Review Focus

- A quick switch must not run a path check or claim a path result exists.
- Protection conflicts must still turn on visible conflict markers despite the default-off setting.
- Switching to image mode must not expose 3D-only controls.
- A small viewport must keep the popover and controls inside the screen.
- Existing detailed panels must reflect quick-switch changes and vice versa.

### Task 1: Group the display controls

**Files:** Modify `assets/viewer/src/studio-workspace.js`, `assets/viewer/src/studio-design.css`.

- [ ] Reparent the existing quality, layer, cut, and selection controls into labelled groups.
- [ ] Add image-mode-only thumbnail content and a compact action row for detailed checks.
- [ ] Verify the display menu with the viewport desktop test at 1200 and 900 pixels.

### Task 2: Synchronize auxiliary overlays

**Files:** Modify `assets/viewer/src/walk-view.js`, `assets/viewer/src/protection-view.js`, `assets/viewer/src/studio-workspace.js`; extend focused desktop tests.

- [ ] Expose walk and protection visibility state to the quick switches without moving the authoritative controls.
- [ ] Make player-path visibility unavailable before a valid result; retain explicit path checking.
- [ ] Verify toggle, refresh, conflict, and image/3D mode transitions.

### Task 3: Final verification and package

**Files:** Update the user guide and version files after focused tests.

- [ ] Run `mise exec -- npm run build:web`, relevant desktop tests, `mise run ui:test`, and `mise exec -- npm run doctor`.
- [ ] Build the previously requested 3.4.2 portable package and run packaged smoke checks.
- [ ] Inspect the final diff and deliver the ZIP path and SHA256.
