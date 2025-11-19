# pyEfis Config Explorer

Interactive viewer for a normalized snapshot of the pyEfis configuration.

## 1) Generate the normalized JSON

From the repository root run:

```bash
python3 tools/config_normalizer.py \
  --config config/default.yaml \
  --base config \
  --out tools/cfg_explorer/normalized_config.json
```

Optional: define symbols to evaluate `disabled:` conditions (omitted = treat all as enabled):

```bash
python3 tools/config_normalizer.py --config config/default.yaml \
  --define BUTTONS=true --define SOME_FLAG=false \
  --out tools/cfg_explorer/normalized_config.json
```

Eg. if --define BUTTONS=false then the output file is `tools/cfg/explorer/normalized_config_BUTTONS_false.json`.
Multiple --define can be used on the command line.

What the normalizer does:
* Merges `preferences.yaml` and `preferences.yaml.custom` (if present)
* Applies `preferences.styles` and gauge-specific overrides (`preferences.gauges`) to instruments
* Resolves include files (mapping + relative paths) and rescales nested include instrument positions
* Expands `ganged_*` instruments to individual child instruments, preserving group provenance
* Computes headless geometry (grid, spans, move/shrink/justify, aspect ratios)
* Honors `disabled:` expressions only when `--define` symbols are provided (supports `VAR` and `not VAR`)
* Annotates exact overlapping duplicate instruments (no auto-fix) with a `duplicates` count
* Extracts buttons from `config/buttons/*.yaml` (id, type, label, dbkey, conditions, actions, symbols)
* Emits provenance per instrument (source file, include chain, ganged parent, group, preference key, family vs concrete type)
* Produces a preferences block including raw merged preferences and implicit defaults (type ratios)

Output: `tools/cfg_explorer/normalized_config.json`

## 2) Open the explorer

Open `tools/cfg_explorer/index.html` (double‑click). Use the file picker to load the generated `normalized_config.json` (or --define file).

On initial load a placeholder Makerplane logo is shown until you select a screen.

## 3) Panels & Features

Sidebar panels:
* Screens – All discovered screen YAMLs. Click to view expanded instruments and geometry.
* Includes – Non‑screen include files: usage count, locations, and parsed content.
* Preferences – Raw merged preference keys plus implicit defaults (ratios).
* Buttons – All parsed buttons with label fallback (YAML `label` → `text` → filestem). Click for a readable condition/action summary.

Details & preview:
* Details pane shows structured info (buttons) or raw JSON (other items).
* SVG geometry preview: 1200×800 coordinate space, rectangles sized by grid + ratio fitting.
* Duplicate overlaps highlighted (red stroke, tooltip with duplicate count).
* Toggle labels checkbox to annotate each rectangle with type/group.
* Mouse wheel zooms (+/−), left-click and drag pans and Fit actions adjust viewBox without altering logical geometry.
* Draggable vertical splitter resizes preview vs. details. Active immediately.

## 4) Geometry specifics
Aspect ratios applied:
* vertical_bar* → 1:0.35
* horizontal_bar* → 1:2
* arc_gauge → 1:2
* airspeed / altimeter / HSI / other round → 1:1

Ganged instruments:
* Horizontal vs vertical layout gap calculations mirrored from runtime logic
* Per‑group `gap` percentages shrink available dimension before placing children
* Preference overrides can change concrete type per child (family vs concrete recorded)

Includes:
* Nested includes rescaled by span proportions; include chains preserved in provenance
* Each non‑screen include entry lists where it was referenced

Disabled evaluation:
* Only performed if at least one `--define` is provided
* Supports `disabled: VAR` and `disabled: not VAR` ie --define VAR={true or false}
* When no defines are given all instruments are rendered (even conditionally disabled ones)

## 5) Buttons parsing
For each button YAML:
* Collect `id`, `label`, `type`, `dbkey`
* Gather each condition: `when`, extracted uppercase symbols, actions, continue flag
* Provenance includes source file

## 6) Troubleshooting
Nothing loads after selecting a file:
* Confirm the file is a recent `normalized_config.json`
* Check browser console for JSON parse errors

Buttons panel empty:
* Ensure YAMLs exist under `config/buttons/` and have basic keys

Geometry looks off:
* Verify spans and margins in screen YAML
* Confirm aspect ratio expectations for the instrument type

---
Generated data is read‑only; edits must be made in source YAMLs then re‑normalized.
