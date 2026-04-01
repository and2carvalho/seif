# paper-kb (Knowledge Base)

This folder stores a normalized “knowledge base” so an AI agent can continue writing without losing references (names, formulas, authors, places, and concepts).

## KB Sections (Canonical Output Schema)
- `people_and_entities`: named individuals + mythic/ancestral actors
- `places_and_ancestral_sets`: places + grouped ancestral sets
- `formulas_and_symbols`: all formulas, symbols, numeric gates (3-6-9, `phi`), and any equations as they appear
- `modules_and_pipeline_terms`: RPWP module names and pipeline terms (`Biosignature Detection`, `VFT`, `Tesla Harmonics Filter`, etc.)
- `claims_for_discussion`: claims that will become paper arguments (with “stance labels” and uncertainty notes)

## Extraction Template (Agent-Friendly)
When extracting from sources, keep:
- verbatim strings for preserved reference names
- structured “where it came from” pointers, e.g.:
  - `source: conversa.md`
  - `source: proto-writing/READM.md`

## Next Steps
- Create the first KB snapshot by extracting:
  - the RPWP module architecture
  - the consolidated bibliography seeds
  - the full formula/symbol list from the project corpus

