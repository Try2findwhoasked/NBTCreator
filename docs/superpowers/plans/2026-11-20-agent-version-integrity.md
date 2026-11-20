# Agent Version Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind task inputs, review, and delivery to the same verified version.

**Architecture:** Check source inputs at the engine boundary, verify managed lineage before return registration, and keep manual export separate from task completion.

**Tech Stack:** Python engine, Node CLI and viewer, unittest.

### Task 1: Task inputs and lineage

- [x] Freeze coordinates, wall mask and managed manifest in new tasks; check them during lease use and before return registration.
- [x] Verify the lease under the publication lock. Add regressions for expired workers, changed sidecars and managed ancestor returns in `tests/engine/agent-protocol.py`.

### Task 2: History and review

- [x] Preserve existing history task references when a repeated save does not provide tasks. Surface a failed history write and retry the same association, not the model return.
- [x] Verify unchanged review and approval files after moving the workspace; resolve both new relative and legacy absolute source references.

### Task 3: Manual delivery

- [x] Bind CLI export to the reviewed source and aggregate input hashes. Add a read-only input inspection command and require explicit export.
- [x] Correct generated handoff instructions and verify SNBT, tool catalog and Agent protocol regressions.

### Task status safeguards

- [x] Require attached model validation and preview evidence for production tasks; use a findings summary for read-only plans. Keep acceptance independent.
- [x] Invalidate the old lease when a replacement prompt revision is published. Prevent writes that would make a task index unreadable.

**Follow-up scope:** explicit cancellation and waiting states, separate receipt retention, pinned execution runtimes, and durable AI run checkpoints are not implemented by this patch.
