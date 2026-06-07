# Building & releasing `lunch-roulette`

This repo **is** the plugin: `.claude-plugin/plugin.json` sits at the root, alongside `agents/`, `commands/`, and `skills/`. Building a release means bundling that tree into a single installable file for Claude Cowork.

## What a `.plugin` is

A `.plugin` is just a **ZIP archive with the `.plugin` extension**. Claude Cowork recognizes it as an installable plugin only when the manifest is at the **archive root**:

```
lunch-roulette.plugin   (a zip)
├── .claude-plugin/
│   └── plugin.json      ← manifest at the ROOT of the archive
├── agents/
├── commands/
├── skills/
└── LICENSE
```

Two things make or break it:

- **Extension is `.plugin`, not `.zip`.** Cowork's install flow keys off the extension; a `.zip` is treated as a plain download, not a plugin.
- **The manifest must be at the archive root** — `.claude-plugin/plugin.json` at the top, with every component directory (`agents/`, `commands/`, `skills/`) beside it. It must **not** be nested under a `lunch-roulette/` (or any) subdirectory. Only `plugin.json` lives in `.claude-plugin/`; everything else sits at the plugin root.

Because the repo root already is the plugin root, a no-prefix `git archive` produces exactly this structure. (Official structure rules: [Plugins reference — plugin structure](https://code.claude.com/docs/en/plugins-reference#plugin-structure).)

## Build the `.plugin`

Run from the **repo root**. The version in the filename should match `version` in `.claude-plugin/plugin.json`:

```bash
git archive --format=zip -o lunch-roulette-v0.5.0.plugin HEAD
```

Why `git archive` (and **no** `--prefix`):

- It packs **tracked files only** at the committed state — no `.git`, no `__pycache__`, no `_*/` scratch dirs, no local cruft. (The skill's `_work/` runtime dir and other `_*/` dirs are gitignored, so they're excluded automatically.)
- **Dev-only files are excluded via `.gitattributes` `export-ignore`** (`CLAUDE.md`, `BUILD.md`). This is **required**: Claude Desktop's plugin validator runs in **strict** mode (warnings = errors), and a `CLAUDE.md` at the plugin root is a warning that becomes a hard *"Plugin validation failed"* (it blocked the v0.5.0 upload). `git archive` honors `export-ignore`, so the build command above stays exactly the same and the output is clean. **Verify** after building that `CLAUDE.md` is **not** in the archive (see below).
- `--format=zip` makes a real zip; renaming the output to `.plugin` is all Cowork needs.
- Omitting `--prefix` keeps `.claude-plugin/` at the archive root. Adding `--prefix=lunch-roulette/` would bury the manifest one level down (`lunch-roulette/.claude-plugin/plugin.json`) and Cowork would not see an installable plugin — that was the old, broken build.

This is the reproducible equivalent of zipping the plugin directory's *contents* by hand (`cd <plugin-dir> && zip -r out.plugin . -x "*.DS_Store" "*__pycache__*"`), which is how the bundle was first built and verified in a live Cowork session.

`*.plugin` (and `*.zip`) are gitignored — **do not commit the build artifact.**

## Verify the archive

Confirm the manifest is at the root and the expected files are present:

```bash
unzip -l lunch-roulette-v0.5.0.plugin | grep -E 'claude-plugin|SKILL.md|lunch-messenger|lunch.md|LICENSE'
```

You want `.claude-plugin/plugin.json` listed at the **top level** (not under `lunch-roulette/...`), plus `agents/lunch-messenger.md`, `commands/lunch.md`, `skills/lunch-roulette/SKILL.md`, and `LICENSE`. Spot-check the full listing with `unzip -l lunch-roulette-v0.5.0.plugin` if anything looks off.

A quick sanity check that nothing scratch leaked in:

```bash
unzip -l lunch-roulette-v0.5.0.plugin | grep -E '__pycache__|/_|\.git/' || echo "clean"
```

## How Cowork installs it

A `.plugin` becomes installable when it lands in a Cowork **session's outputs directory** — Cowork renders it as a card with an **Install** button (it does not show raw zip contents). Installing adds the skill, the `/lunch` command, and the tool-locked `lunch-messenger` agent. Out of band, you can also install a `.plugin` via the Cowork **Plugins → Upload** dialog in Claude Desktop.

> Note: installation lives in the host (Cowork / Claude Desktop) UI, not in this repo. The build here only produces the artifact; getting an Install button is a property of where the `.plugin` is placed, not of the build command.

## Release flow

1. **Bump the version.** Edit `version` in `.claude-plugin/plugin.json`, and update the version references in `README.md` (the **Status** line and the `## Building` command) and `CLAUDE.md` (the *Package the plugin* command). Merge that via PR (`main` is branch-protected).
2. **Tag the release** on the merged commit:
   ```bash
   git tag v0.5.0
   git push origin v0.5.0
   ```
3. **Build the artifact** from the tag (clean checkout recommended):
   ```bash
   git archive --format=zip -o lunch-roulette-v0.5.0.plugin v0.5.0
   ```
4. **Verify** it (see above), then **attach the `.plugin` to a GitHub Release** for `v0.5.0`:
   ```bash
   gh release create v0.5.0 lunch-roulette-v0.5.0.plugin \
     --title "v0.5.0" --notes "..."
   # or, on an existing release:
   gh release upload v0.5.0 lunch-roulette-v0.5.0.plugin
   ```

Keep the filename version, the git tag, and `plugin.json`'s `version` in lockstep.
