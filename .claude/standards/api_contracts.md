# API Contracts Standard

**Domain:** Gregor Zwanziger Weather Data

## Single Source of Truth

**ALL** data transfer objects (DTOs) and data formats MUST comply with:
```
docs/reference/api_contract.md
```

## Rules

### 1. No Schema Drift

When adding new fields or modifying DTOs:
1. **Update contract FIRST** in `docs/reference/api_contract.md`
2. Get user approval
3. THEN implement in code

**NEVER** implementDTO changes without contract update!

### 2. Contract Components

The API contract defines:
- **Provider DTOs:** Weather data from external APIs
- **Normalized DTOs:** Internal standardized format
- **Report DTOs:** Output format for channels
- **Field Types:** Required, optional, nullable
- **Value Ranges:** Valid ranges for numeric fields
- **Enums:** Allowed categorical values

### 3. Validation

All code that creates or consumes DTOs MUST:
- Validate against contract
- Fail fast on invalid data
- Log contract violations

### 4. Testing

DTO tests MUST:
- Cover all fields defined in contract
- Test boundary conditions
- Verify enum values
- Check nullable handling

### 5. Documentation

When changing DTOs:
- Document WHY in contract
- Add migration notes if breaking change
- Update examples

## Common Violations to Avoid

❌ **Don't:**
- Add fields to code without updating contract
- Skip optional fields in contract
- Use different field names in different layers
- Ignore contract during refactoring

✅ **Do:**
- Reference contract in code comments
- Use contract as spec for implementation
- Keep contract and code in sync
- Review contract during code reviews

## Example Reference in Code

```python
# DTO must comply with docs/reference/api_contract.md
# Section: Normalized Weather Data DTO
class NormalizedWeatherData:
    location: str          # Required per contract
    timestamp: datetime    # Required per contract
    temperature_c: float   # Required per contract
    precipitation_mm: float | None  # Optional per contract
```

## Enforcement

Contract compliance is checked by:
- Manual review during spec approval
- Type hints in code
- Validation tests
- Integration tests with real data

## When to Update Contract

Update contract when:
- Adding new provider (new provider DTO)
- Adding new channel (new report DTO)
- Enhancing normalized data (new fields)
- Changing field types or ranges

Always update contract BEFORE code!
