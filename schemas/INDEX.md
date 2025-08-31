

# Schemas Index – Gregor Zwanzig

This folder contains JSON schemas that define the structure of normalized data.

---

## Available Schemas
- `normalized_timeseries.schema.json` → Contract for normalized forecast timeseries (see `docs/api_contract.md`).

---

## Usage
- All DTOs must validate against the schemas before being accepted.
- Validation is enforced in tests using `pytest` and `jsonschema`.

### Example Validation (pytest)
```python
import json
import jsonschema
from pathlib import Path

def test_normalized_timeseries_schema():
    schema = json.loads(Path("schemas/normalized_timeseries.schema.json").read_text())
    sample = json.loads(Path("fixtures/analyzer/input_series.json").read_text())
    jsonschema.validate(instance=sample, schema=schema)
```

---

## Notes
- Schemas are the **single source of truth** for data structures.
- If a schema changes, update fixtures and implementation accordingly.