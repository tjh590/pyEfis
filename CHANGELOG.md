# Changelog
Generated on 2025-11-16.

This file summarizes all commits after upstream commit 48d2fce ("Merge pull request #258 from e100/fix_ci") up to the current HEAD on branch `new_ems_gauges`.

## Command-line and runtime behavior changes

- main.py (8b4323f): Startup readiness is now configurable via the config file under `main:`
  - `loaderKey` (string, default `ZZLOADER`): FIX DB key to probe at startup.
  - `waitForLoader` (bool, default `true`): Whether to wait for the loader key before proceeding.
  - `loaderTimeout` (float seconds, default `60`): Maximum time to wait before continuing with a warning.
  - Logs while waiting are throttled; on timeout pyEFIS continues startup instead of looping forever.
- No new CLI flags were added in this range; existing CLI options remain:
  - `--mode [test|normal]`, `--debug`, `--verbose/-v`, `--config-file`, `--log-config`.

## Configuration changes and new options

- Horizontal bar gauge (782ad0d, f307b2e): new options
  - `value_on_bar_left` (bool): render value/label area to the left of the bar.
  - `value_on_bar_left_width_percent` (float 0.05–0.5): width fraction for the left label area.
  - `show_dbkey_text` (bool): show dbkey text on the left label instead of numeric value.
  - `big_font_percent` (float): optional font size as a fraction of widget height.
  - `small_font_percent` (float): optional font size as a fraction of widget height.
- New/alternate bar implementations (85bc374, 01df9fa, dc40a1c, f3a5a46):
  - New instrument types recognized in screen configs via `type:`
    - `horizontal_bar_gauge_improved`
    - `vertical_bar_gauge_improved`
    - Also added simple variants `horizontal_bar_gauge` (existing), and new modules `horizontalBarSimple.py` / `verticalBarSimple.py` (developer-targeted).
- Buttons (cab6d33, d5f4499, ff65519, ceadbd0, 1fc341f):
  - Performance improvements by coalescing condition evaluations; new per-button config:
    - `conditions_debounce_ms` (int, default 0): coalesce updates using a single-shot timer; when 0, evaluations are immediate.
  - Conditions support for logical values now accepts both `true` (pycond) and `True` (Python) literals in YAML (ceadbd0).
  - No schema change required for existing button configs unless opting into `conditions_debounce_ms`.
- Menu auto-hide behavior moved to a GUI-thread timer (8b4323f, 6a61fad); no config key changes.
- Diagnostics overlay introduced (6dd1d76, beb30ca): `src/pyefis/diagnostics/overlay.py` added; no default config keys added in this range.

## Per-commit summary (chronological)

- 2cabc99 — update for IDE environment
  - Dev environment tweaks: `.devcontainer/devcontainer.json`, `.gitignore`.
- 3caf668 — Update devcontainer.json - run make commands manually
  - Adjust container setup; no runtime changes.
- 253145f — Update devcontainer.json for Copilot Workspace trial
  - Devcontainer updates; no runtime changes.
- 26b6826 — Only run CI on PR to master branch
  - CI workflow change in `.github/workflows/ci.yml`.
- 6a461d1 — Add more docs; resolve missing pycond package when building on Pi
  - Makefile and documentation updates; ensures `pycond` availability on Pi builds.
- 8b4323f — fix: startup readiness + clean shutdown (faster exit, fewer timer warnings)
  - main.py replaces infinite `ZZLOADER` wait with configurable readiness (`loaderKey`, `waitForLoader`, `loaderTimeout`).
  - gui/menu/weston/gauges/screenbuilder: unify shutdown, stop timers, reduce warnings/crashes.
- 6a61fad — Fix application shutdown issues and improve startup robustness
  - Further refines shutdown sequencing; non-blocking timer stops and scheduler shutdown.
- 85bc374 — improved bars #1 attempt
  - Introduces improved horizontal/vertical bar gauges and screenbuilder wiring; adds `IMPROVED_GAUGES.md`.
- 01df9fa — improved bars #2
  - Continues gauge refactors; adds simple variants modules.
- dc40a1c — improved bars #3
  - Iterates on simple bar implementations and screenbuilder hooks.
- f3a5a46 — horiz recoded to correct
  - Corrects improved bar rendering behavior.
- 0e74eb7 — testing
  - Adjustments to EGT gauge and vertical bar; test scaffolding.
- ca1a5db — testing
  - Minor fixes in `abstract.py` and vertical bar improvements.
- 5d697fb — testing
  - Updates `garmintry.py`, abstract gauge, and `teststack.py` (dev utility).
- ca76a22 — new config_inpsector app
  - Adds `tools/config_inspector.py` to analyze config composition.
- 3f801fd — additional features
  - Extends `tools/config_inspector.py`.
- 782ad0d — horizontal bars can have values on the left side
  - Adds left-label layout for horizontal bars; screenbuilder aware.
- f307b2e — add big_font/small_font percent option
  - Adds `big_font_percent` and `small_font_percent` support in horizontal bar.
- 6dd1d76 — Phase 1 diagnostics implemented (not yet tested)
  - Adds diagnostics overlay module; hooks in bar gauges.
- beb30ca — Phase2
  - Further diagnostics and gauge baseline fixes.
- 8e978eb — still performance issues
  - Performance tuning in VirtualVfr and abstract gauges; GUI adjustments.
- cab6d33 — button re-implementation (eliminate 100% CPU) - steps 1 and 2
  - Reworks button evaluation path to avoid high CPU; groundwork for debounce.
- d5f4499 — button improvements completed
  - Finalizes button coalesced evaluation; adds diagnostics counters.
- 031e777 — added button config inspector
  - Adds `tools/config_inspector_plus.py` for deeper inspection.
- 51eb965 — details on button improvement logic to reduce CPU use
  - Adds `improved-button-logic.md` documentation.
- ff65519 — some pytest trials
  - Button tests and a sample button config under `tests/data/buttons/`.
- ceadbd0 — no coalescence unless conditions_debounce_ms > 0; allow 'true' and 'True' in button YAML
  - Test data updated to reflect accepted boolean literals; debounce semantics clarified.
- 1fc341f — revert log messages back to DEBUG
  - Adjusts logging level in button module.
- 79c858f — some adjustments to correct pytest failures
  - Test adjustments for VirtualVfr and horizontal bar gauges.
- 1dc0241 — reduce jitter/improve smoothness in VirtualVfr; ensure pytest pass
  - Smooths rendering cadence and reduces jitter; test stability improvements.

## Notes

- No changes were detected to files under `config/` during this range; new configuration behaviors are introduced via code-level options and new instrument types. To use them, update your screen YAMLs and preference mappings accordingly.
- The tools `tools/config_inspector.py` and `tools/config_inspector_plus.py` can help visualize include resolution and effective configuration.

---

