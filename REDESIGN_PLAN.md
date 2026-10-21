# StoryBuilder Redesign Plan

Status: design baseline, October 21, 2026
Working branch: `redesign/simplified-writing-workflow`

## Goal

Redesign the app around the novelist's work, not around separate internal tools. The normal path from opening a book to writing and approving the next scene should be obvious, continuous, and short. Preserve working story/package logic and safeguards where possible; replace the interaction model rather than blindly discarding the existing code.

## Current-state finding

The current UI creates 16 separate sections: Talk to Builder, New Novel Assistant, Story, Canon & Rules, Change Assistant, Characters, Relationships, Locations, Story Modules, Story Planning, Story Interview, Scene Contract, Scene Planner, Current State, Writer, and Manuscript. The toolbar also exposes New/Open, Save/Save As, Validate, Sync Novel, Close, and Close & Sync Novel.

Useful capabilities are spread over those destinations. In particular, an ordinary scene currently can require separate visits to Scene Contract, Current State, and Writer. On close, the window protocol is connected to the close-and-sync path, which is surprising for a user who expects closing the window not to sync.

## Proposed application structure

### Home / Open a Novel
- New novel, open a novel, recent/last-opened novel, and clear indication of the active novel folder.
- Make the active package path visible.
- No novel-specific content should be stored in the StoryBuilder code repository.

### Write (primary workspace)
Keep the ordinary scene workflow on one page:
1. Show the active chapter/scene and concise starting context.
2. Pre-fill one editable next-scene idea from the current state, plan, canon, and unresolved threads. Do not require the author to invent text simply to continue.
3. Prepare the scene contract automatically in the background. Make detailed contract information collapsible/optional, not a compulsory separate screen.
4. Let the author edit the idea, adjust direction/boundaries, and generate prose.
5. Keep the draft, focused revision, regenerate, and acceptance actions together.
6. After acceptance, reconcile the ending state and show concise proposed changes for author review. Do not require routine JSON editing.
7. Once the scene is safely saved and the state is reconciled, prepare the following scene's editable suggestion automatically.

The author always controls the story direction and whether prose/state proposals are accepted. Never silently overwrite accepted prose or discard existing clues, knowledge, or continuity. Keep advanced state repair available without making it part of every ordinary scene.

### Story Bible
One organized destination for title/premise, canon/rules, characters, supporting people, relationships, locations, and optional story modules. Prefer plain-language forms and reviewed proposals over raw JSON during normal use.

### Plan
One destination for novel-level outline and planning, chapter/scene plans, and optional collaborative planning. Planning assists writing but must not block writing a scene when the author has not planned every detail.

### Manuscript
Read accepted prose by chapter/scene, review the story so far, and manage manuscript files without entering the generation workflow.

### Advanced tools
Validation, detailed state repair, package/module JSON, change assistant, prompt/context previews, diagnostics, and other infrequent maintenance tools should be discoverable but out of the ordinary writing path.

## Continuity and safety requirements

- Preserve the existing shared novel-package format and compatibility with LocalStoryChat.
- Current saved state, canon, author boundaries, character knowledge, clues, and accepted manuscript remain persistent and authoritative.
- Suggestions are editable proposals, never mandatory author commitments.
- State review should highlight additions, changes, removals, and evidence; omitted fields must not disappear by accident.
- Do not silently invent an unsupported fact, such as an unestablished leak.
- Explicit save and sync actions must be distinct. Closing the window must not silently sync or push a novel repository. Ask clearly when unsaved work needs attention.
- Keep StoryBuilder code changes separate from all novel repositories. In particular, never modify `Taken_at_Dusk` as a side effect of a UI test.

## Implementation approach

1. Establish this design baseline and inventory current capabilities and tests.
2. Map each existing UI feature to a proposed destination; mark duplicates and features that can become advanced actions. Do not remove a capability until its replacement is identified.
3. Implement the new app shell and a single-scene Write workspace in small, testable steps. Prefer extracting UI responsibilities from the large `storybuilder.py` over adding more workflow logic to it.
4. Preserve core package/state/generation modules where their behavior is sound; update tests whenever behavior changes.
5. Run the full suite with `python3 -m pytest -q` after meaningful changes. Test the live local-model workflow only against `The Long Way Home` in the designated test setup.
6. Test with a different genre after the writing flow stabilizes.
7. Only after the redesign is tested, merge it into `main` and delete the temporary redesign branch, leaving only `main`.

## Completion criteria

- A writer can go from an open novel to generating, revising, accepting, and preparing the next scene without manually navigating separate Scene Contract, Current State, and Writer destinations.
- The next-scene idea is prefilled, editable, and replaceable.
- Ordinary writing requires no direct JSON editing.
- Accepted prose, clues, character knowledge, and state survive transitions.
- Closing the app never triggers an unexpected sync.
- Existing tests stay green, with focused regression tests for the new workflow.
- StoryBuilder and novel repositories remain separate.


## Migration map from the current 16 sections

| Current section | New home | Treatment |
|---|---|---|
| Talk to Builder | A small “Ask Builder” action available when relevant | Combine with Change Assistant rather than a separate main section. |
| New Novel Assistant | Home / New Novel | Turn into a guided starter flow; preview and approve before creating files. |
| Story | Story Bible | Keep core metadata and premise. |
| Canon & Rules | Story Bible | Keep permanent rules plainly editable with review before saving. |
| Change Assistant | Ask Builder / Advanced | Merge with Talk to Builder; show proposed changes and require approval. |
| Characters | Story Bible | Combine core characters and supporting people in one organized editor. |
| Relationships | Story Bible | Put alongside character details so writers do not have to visit a separate section. |
| Locations | Story Bible | Put alongside canon and characters. |
| Story Modules | Story Bible / Advanced | Keep optional; expose module controls only when needed. |
| Story Planning | Plan | Keep genre, tone, conflict, themes, and open questions together. |
| Story Interview | Home setup / Story Bible | Reuse as a guided way to fill gaps, not a separate permanent destination. |
| Scene Contract | Write | Prepare automatically; expose editable details in a collapsible “Scene details” area. |
| Scene Planner | Plan | Keep collaborative planning as an optional tool; do not require it before writing. |
| Current State | Write summary / Advanced | Show concise current context in Write. Move direct state editing and full-state repair into an advanced panel. |
| Writer | Write | Make this the central workspace rather than a separate destination from the contract and state. |
| Manuscript | Manuscript | Keep as a focused reader/navigation area for accepted prose. |

## First implementation slice

Start with the user-facing Write journey, not a broad visual restyle:
1. Define a single workspace layout and a small, explicit scene status (idea ready, contract ready, draft ready, awaiting review, accepted).
2. Connect the current idea/contract controls to that workspace, hiding detailed contract fields unless expanded.
3. Put generation, focused revision, regenerate, accept, and concise ending-state review together.
4. After acceptance and reviewed state application, prefill the next editable idea and keep the cursor/workflow in Write.
5. Add explicit Save and Sync status without silently syncing on window close.

Build this slice around existing tested modules where practical. Do not delete the old UI implementation until the new path covers the functions and its tests pass. The first slice must include regression tests for idea auto-fill, correct scene targeting, preservation of existing ideas, state/clue retention, and explicit sync behavior.
