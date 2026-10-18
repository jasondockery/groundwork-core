---
name: docs-alignment
description: Audit or update Groundwork documentation so it stays aligned with AI_THESIS.md, especially after broad docs changes, new tool pages, onboarding edits, or changes that might drift toward terminal tooling as an end in itself.
---

# Docs Alignment

Use this local skill when auditing or editing Groundwork Core's active Markdown
guidance. Read `README.md` and `docs/README.md` for current scope. The learning
curriculum remains in the original Groundwork repo; imported HTML here is
historical reference and is not a publishing input for this task.

## Required Source

Read `AI_THESIS.md` first. It is the canonical north star. Do not copy its text into other docs or agent files; reference it and keep changes aligned with it.

## Audit Checklist

For every affected page, classify it:

- **Workflow**: teaches how a human directs, supervises, verifies, or learns with agents.
- **Interface**: teaches a chosen tool such as tmux, Neovim, Raycast, Anybox, VS Code, or a browser.
- **Foundation**: teaches durable basics such as shell, Git, files, paths, testing, or security.
- **Reference**: cheat sheet, command catalog, glossary, installed list, or troubleshooting.

Then check:

1. Interface pages explain how the tool helps a human direct, inspect, or verify agent-assisted work.
2. Foundation pages say why the basics matter in an AI-native workflow.
3. Tool choices are presented as options, not purity tests.
4. Workflow and why come before keystrokes, flags, packages, and config details.
5. Pages meet readers where they are, assuming nothing about background: terms defined once and a first successful path for those who need it, a skimmable fast path (workflow, why, config) for readers who already know the basics, and the overview -> quick wins -> substantial practice progression respected.
6. Page titles, social titles, nav labels, and compact UI copy use calm product punctuation such as `Page · Groundwork`; avoid em dashes, double hyphens, and hyphen runs as generic separators outside literal command syntax.
7. Existing useful learner content is preserved unless the user explicitly asks to remove it.
8. Learner-facing pages follow the Teaching Structure below: concrete story before abstraction, interleaved try-it-now drills, terms defined at first use, destructive-sounding defaults disarmed with precision, resource ladders instead of piles.

## Teaching Structure

How Groundwork pages teach (decided 2026-07-09, first applied on `docs/git.html`):

1. **Concrete before abstract (concreteness fading).** Open with a true, specific story the reader already participates in — Groundwork itself, the page they are reading, a repo they cloned — and derive the general model from the story. Prefer real public referents ("Jason's laptop") over role words ("the maintainer") until the role has been defined.
2. **Explain, show, try — interleaved.** Every concept section ends with a short "Try it now" drill exercising exactly what was just taught, on something the reader already has. Never bunch drills into one Practice block at the end of a page: practice that is not adjacent to the concept does not happen.
3. **Define terms at first use, in-sentence,** then use them freely ("Jason, who created and maintains Groundwork (in Git terms, its maintainer)").
4. **Precision disarms fear.** Any default, flag, or command that sounds destructive (prune, force, hard, clean) must state exactly what it does and does not touch, adjacent to where it appears — including an explicit "never your X".
5. **Resource lists are ladders, not piles.** Order external resources by reader level (first hour → second stage → reference), say who each rung is for, and never lead with the most authoritative source just because it is authoritative.

## Discoverability

Keep active Markdown guides linked from `docs/README.md` and the root README
where useful. Keep shared policy here and platform installation commands in the
environment repo. Review relative links and externally sourced technical claims.

This repo has no site generator or Groundwork validator. Site discovery artifacts
belong to the repository that owns the published curriculum; use that owner's
workflow only when a separate task authorizes curriculum changes.

## Change Pattern

Prefer small edits:

1. Strengthen the lead paragraph or first callout.
2. Add one AI-native bridge paragraph where the tool's purpose is unclear.
3. Move or reword over-prescriptive claims into optional/tool-choice language.
4. Link current Markdown guides and `AI_THESIS.md` when they reduce drift.
5. Run `git diff --check`, verify affected local links resolve, and inspect
   commands against the owning platform repo and current upstream documentation.
   State manual or device-dependent checks separately; do not claim a nonexistent
   automated site build.

Report pages changed, the alignment issue fixed, and validation results.
