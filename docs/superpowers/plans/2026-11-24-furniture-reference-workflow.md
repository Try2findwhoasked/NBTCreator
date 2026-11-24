# Furniture Reference Workflow Implementation Plan

**Goal** — Rebuild a photo-guided piece of vanilla furniture from frozen input, then reproduce its saved geometry and render.

**Architecture** — The workspace skill records image evidence and authored part recipes. A local script compiles and places the recipe through NBTCreator, saves the SNBT, reads it back and runs the texture renderer. A second invocation and comparison verify the saved evidence. A host preflight simulates an insertion against an explicitly identified source and host conditions.

**Tech stack** — Python, NBTCreator WorkingModel and component APIs, Playwright Chromium texture renderer.

- [x] Record the four papers, visible photo evidence, and limitations before encoding the first designs.
- [x] Implement strict part and recipe validation, source-bound replay, and render receipts.
- [x] Add an independently authored synthetic chair, table and cabinet. Test overlap, invalid states, support, protection, routes and replay.
- [x] Render two photo-based options in the same box and view. Re-run all examples and inspect images, file hashes and caveats.
