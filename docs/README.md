


# Documentation – Gregor Zwanzig

This folder contains all specifications, contracts, and background docs for the project.

## Start Here
- 👉 Begin with [`context/00_index.md`](./context/00_index.md) for the high-level overview.
- Use [`architecture.md`](./architecture.md) for the system design.
- Refer to [`api_contract.md`](./api_contract.md) for data structures and schema contracts.

## Other Key Docs
- [`decision_matrix.md`](./decision_matrix.md) → Rules for forecast source selection (MET vs MOSMIX).
- [`sms_format.md`](./sms_format.md) → Compact SMS format specification (≤160 chars).
- [`renderer_email_spec.md`](./renderer_email_spec.md) → Email renderer specification.
- [`debug_format.md`](./debug_format.md) → Debug output format rules.
- [`symbol_mapping.md`](./symbol_mapping.md) → Weather symbol normalization.

## Notes
- All docs are written to be **Cursor-ready**.
- Specs and rules are the single source of truth; implementation must follow them.