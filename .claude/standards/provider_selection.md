# Provider Selection Standard

**Domain:** Weather Data Provider Selection Logic

## Decision Matrix

**Reference:** `docs/reference/decision_matrix.md`

Provider selection follows documented rules based on:
- **Location:** Geographic coordinates
- **Data needs:** Required weather parameters
- **Availability:** API uptime and rate limits
- **Accuracy:** Provider strength in region

## Current Providers

### MET Norway
- **Region:** Norway, Nordic countries, European mountains
- **Strengths:** High-resolution mountain weather, precipitation
- **Weaknesses:** Limited global coverage
- **Use when:** Location in Scandinavia or European Alps

### Open-Meteo
- **Region:** Global
- **Strengths:** Regional model selection (ICON-D2, AROME), free tier
- **Weaknesses:** Limited historical data
- **Use when:** Need specific regional model or global coverage

### DWD MOSMIX (Planned)
- **Region:** Germany, Central Europe
- **Strengths:** Official DWD forecasts, detailed parameters
- **Weaknesses:** Complex XML format, Germany-focused
- **Use when:** Location in Germany or Central Europe

## Selection Algorithm

```
1. Check location coordinates
2. Determine region (Scandinavia / Central Europe / Global)
3. Select primary provider based on region
4. Define fallback provider(s)
5. Validate provider supports required parameters
```

## Fallback Strategy

**Always define fallback chain:**

```
Primary: MET Norway (for GR20 in Corsica)
  ↓ (if unavailable)
Fallback 1: Open-Meteo (AROME France)
  ↓ (if unavailable)
Fallback 2: Open-Meteo (ICON-EU)
```

## Required Parameters

All providers MUST supply:
- Temperature
- Precipitation
- Wind speed/direction
- Cloud cover (for risk assessment)

**Nice to have:**
- CAPE (for thunderstorm risk)
- Visibility
- Snow depth

## Provider Integration Rules

### 1. Adapter Pattern

Each provider needs:
- Provider-specific adapter class
- DTO for provider response (in API contract)
- Normalization to standard DTO
- Error handling for API failures

### 2. Rate Limiting

Respect provider limits:
- MET Norway: User-Agent required, no hard limit
- Open-Meteo: 10,000 calls/day (free tier)
- MOSMIX: Hourly updates, download full file

### 3. Caching

Cache responses to reduce API calls:
- Cache duration: 1 hour (weather data changes)
- Cache key: location + timestamp + provider
- Invalidate on error (don't serve stale data)

### 4. Error Handling

Handle provider failures:
- Timeout (10 seconds max)
- HTTP errors (4xx, 5xx)
- Invalid response (missing fields)
- Rate limit exceeded

**Action on failure:**
1. Log error with provider name
2. Try fallback provider
3. If all fail → notify user (email/log)

## Configuration

Provider selection configurable via:

```ini
[provider]
# Primary provider
primary = met_norway

# Fallback chain (comma-separated)
fallbacks = open_meteo_arome, open_meteo_icon

# Provider-specific settings
[provider.met_norway]
timeout = 10
user_agent = Gregor-Zwanziger/1.0

[provider.open_meteo]
model = arome_france
timeout = 10
```

## Adding New Provider

When adding new provider:
1. Document in decision matrix
2. Define DTO in API contract
3. Create adapter class
4. Add to fallback chain
5. Test with real API calls (no mocks!)
6. Update provider selection logic

## Testing

Provider tests MUST:
- Use real API calls (no mocks!)
- Test primary + all fallbacks
- Simulate failure scenarios
- Verify normalization to standard DTO
- Check rate limit handling

## References

- Decision Matrix: `docs/reference/decision_matrix.md`
- API Contract: `docs/reference/api_contract.md`
- Architecture: `docs/features/architecture.md`
