# Keiba Simulator (Minimal)

This is a minimal, runnable pipeline based on `SPEC_v2.7.md`.
It ingests a race PDF, extracts text if possible, builds placeholder race data,
then emits JSON outputs per race plus a summary.

## Usage

```bash
PYTHONPATH=src python -m keiba_simulator.cli path/to/race.pdf --trackdata trackdata.json
```

Outputs are written to `output/` by default.
If `pdftotext` is not installed, the pipeline still runs with placeholder data and warnings.
