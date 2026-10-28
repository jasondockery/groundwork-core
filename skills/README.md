# Skills

This directory holds the skills this repository opts into from
[Compass](https://github.com/jasondockery/compass), plus two local ones. The
selected names are in [`compass.skills.json`](../compass.skills.json); Compass
always adds its required core. The projection is receipt-bound: run
`node .compass/check-projection.mjs` to verify it, and re-project from a
validated Compass release instead of editing these files. `.agents/skills` and
`.claude/skills` are the generated discovery adapters for the Compass skills.

The repository's own skills are [docs-alignment](docs-alignment/SKILL.md) and
[command-efficiency](command-efficiency/SKILL.md). Groundwork Core owns shared
operational Markdown, skills specific to that guidance, and project scaffolds.
Installer procedures stay in their environment repositories.
