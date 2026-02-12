# User Story: SMS-Berichte für Weitwanderer

**Status:** open
**Created:** 2026-02-01
**Epic:** Multi-Channel Report Delivery

## Story

Als Weitwanderer auf dem GR20
möchte ich Wetterberichte per SMS erhalten
damit ich auch ohne Internet-Zugang Wetterinfos bekomme

## Acceptance Criteria

- [ ] User kann Telefonnummer in config.ini konfigurieren
- [ ] Reports werden per SMS gesendet wenn channel=sms
- [ ] SMS-Nachrichten sind ≤160 Zeichen
- [ ] Kritische Wetterdaten werden priorisiert im kompakten Format
- [ ] Fehlgeschlagene Sends werden mit Exponential Backoff wiederholt
- [ ] SMS-Versand funktioniert auch bei schwachem Signal (Retry-Logic)

## Feature Breakdown

### P0 Features (Must Have - MVP)

#### Feature 1: SMS Channel Integration
- **Category:** Channel
- **Scoping:** 3-4 files, ~150 LOC, Medium complexity
- **Dependencies:** None
- **Roadmap Status:** Added to ACTIVE-roadmap.md
- **Feature Brief:** `features/EXAMPLE-sms-channel-integration.md`

**Acceptance:**
- [ ] Kann SMS via Gateway API senden (MessageBird)
- [ ] Authentifizierung korrekt
- [ ] Gibt Success/Failure Status zurück
- [ ] Real E2E Test: SMS senden + Delivery Status prüfen

**Files:**
- `src/channels/sms_sender.py` (NEW)
- `src/channels/sms_config.py` (NEW)
- `src/app/config.py` (MODIFIED)
- `tests/tdd/test_sms_sender.py` (NEW)

---

#### Feature 2: SMS Compact Formatter
- **Category:** Formatter
- **Scoping:** 2 files, ~100 LOC, Simple complexity
- **Dependencies:** Feature 1 (needs channel)
- **Roadmap Status:** Added to ACTIVE-roadmap.md

**Acceptance:**
- [ ] Output ≤160 Zeichen
- [ ] Enthält: Location, Datum, Temp, Niederschlag, Wind
- [ ] Lesbares Format
- [ ] Priorisierung: Risiko > Wetter > Details

**Format Example:**
```
GR20-E3 01.02 12-18°C 5mm W20km/h RISK:Gewitter@14h
```

**Files:**
- `src/formatters/sms_formatter.py` (NEW)
- `tests/tdd/test_sms_formatter.py` (NEW)

---

#### Feature 3: SMS Channel Config
- **Category:** Config
- **Scoping:** 2 files, ~50 LOC, Simple complexity
- **Dependencies:** Feature 1, Feature 2
- **Roadmap Status:** Added to ACTIVE-roadmap.md

**Acceptance:**
- [ ] `sms` ist valide Channel-Option
- [ ] `phone_number` konfigurierbar in config.ini
- [ ] Validierung des Telefonnummer-Formats (E.164)
- [ ] API Key als Environment Variable

**Config Example:**
```ini
[channel]
type = sms

[sms]
provider = messagebird
api_key = ${SMS_API_KEY}
from_number = +491234567890
to_number = +491234567890
```

**Files:**
- `src/app/config.py` (MODIFIED)
- `tests/tdd/test_config.py` (MODIFIED)

---

### P1 Features (Should Have)

#### Feature 4: SMS Retry Logic
- **Category:** Channel (enhancement)
- **Scoping:** 2 files, ~80 LOC, Medium complexity
- **Dependencies:** Feature 1
- **Roadmap Status:** Added to ACTIVE-roadmap.md

**Acceptance:**
- [ ] Retry bei Failure (max 3 Versuche)
- [ ] Exponential Backoff (1s, 2s, 4s)
- [ ] Logging der Retry-Versuche
- [ ] Gibt auf nach max retries

**Files:**
- `src/channels/sms_sender.py` (MODIFIED)
- `tests/tdd/test_sms_retry.py` (NEW)

---

### P2 Features (Nice to Have - Future)

#### Feature 5: SMS Delivery Tracking
- **Category:** Channel (monitoring)
- **Scoping:** 2 files, ~60 LOC, Simple complexity
- **Dependencies:** Feature 1

**Acceptance:**
- [ ] Webhook für Delivery-Confirmations
- [ ] Logging von Delivery Status
- [ ] Dashboard mit Delivery Rate

**Not in MVP** - Can be added later

---

#### Feature 6: SMS Cost Estimation
- **Category:** Admin (monitoring)
- **Scoping:** 2 files, ~40 LOC, Simple complexity
- **Dependencies:** Feature 1

**Acceptance:**
- [ ] Zeigt voraussichtliche Kosten
- [ ] Warnt bei hohen Kosten
- [ ] Monthly cost tracking

**Not in MVP** - Admin feature for later

---

## Implementation Order

**Phase 1: Foundation**
1. **SMS Channel Integration** (P0)
   - Establish SMS sending capability
   - Real E2E tests with MessageBird
   - Duration: 1 workflow cycle (~1-2 days)

**Phase 2: Formatting**
2. **SMS Compact Formatter** (P0)
   - 160-char constraint
   - Data prioritization
   - Duration: 1 workflow cycle (~1 day)

**Phase 3: Configuration**
3. **SMS Channel Config** (P0)
   - Config.ini integration
   - Phone number validation
   - Duration: 1 workflow cycle (~1 day)

**Phase 4: Reliability** (After MVP)
4. **SMS Retry Logic** (P1)
   - Enhance base sender
   - Exponential backoff
   - Duration: 1 workflow cycle (~1 day)

**Phase 5: Monitoring** (Future)
5. SMS Delivery Tracking (P2)
6. SMS Cost Estimation (P2)

## Dependency Graph

```
[SMS Channel Integration] (P0)
         ↓
    [SMS Formatter] (P0)
         ↓
    [SMS Config] (P0)
         ↓
    [SMS Retry] (P1)
         ↓
  [Delivery Tracking] (P2)
  [Cost Estimation] (P2)
```

## MVP Definition

**MVP = P0 Features Complete**
- [x] Added to roadmap
- [ ] SMS Channel Integration implemented
- [ ] SMS Compact Formatter implemented
- [ ] SMS Channel Config implemented

**User can:**
- Configure phone number
- Send weather reports via SMS
- Receive compact 160-char forecasts

**User cannot yet:**
- Get retry on failure (P1)
- Track delivery status (P2)
- Monitor costs (P2)

## Estimated Effort

### P0 (MVP)
- **Total LOC:** ~300 lines
- **Total Files:** ~7 files
- **Workflow Cycles:** 3
- **Timeline:** 3-5 days (sequential implementation)

### P0 + P1
- **Total LOC:** ~380 lines
- **Total Files:** ~9 files
- **Workflow Cycles:** 4
- **Timeline:** 4-6 days

### P0 + P1 + P2
- **Total LOC:** ~480 lines
- **Total Files:** ~13 files
- **Workflow Cycles:** 6
- **Timeline:** 6-8 days

## Testing Strategy

### Real E2E Tests (NO MOCKS!)

**For Each Feature:**
1. Real SMS send via MessageBird API
2. Real delivery status check
3. Real phone number validation
4. Real retry behavior (simulate failures)

**Test Environment:**
- MessageBird test account
- Test phone numbers
- Real API credentials (test mode)

### Integration Tests

**After MVP (P0 complete):**
1. End-to-end flow: CLI → Config → Formatter → SMS → Delivery
2. Test in different scenarios:
   - Good signal (immediate delivery)
   - Bad signal (retry needed)
   - Invalid number (validation catches)

## Security & Privacy

### Phone Numbers (GDPR)
- Store encrypted in config
- No logging of full numbers
- Opt-in only (user must configure)

### API Keys
- Environment variables only
- Never commit to git
- Rotate regularly

### SMS Content
- No personal data in SMS (just weather)
- Location ID instead of address
- Opt-out mechanism

## Cost Considerations

### MessageBird Pricing (Example)
- ~€0.05 per SMS (Germany)
- ~€0.10 per SMS (international)

### Expected Usage
- 2 SMS/day (morning + evening report)
- ~60 SMS/month
- ~€3-6/month per user

### Cost Control
- Limit max SMS per day (config)
- Alert on high usage
- Budget tracking (P2 feature)

## Rollout Plan

### Phase 1: MVP (P0)
1. Implement Feature 1-3
2. Test with single user (Henning)
3. Monitor for 1 week
4. Fix issues

### Phase 2: Reliability (P1)
5. Add retry logic (Feature 4)
6. Test with 2-3 users
7. Monitor delivery rates

### Phase 3: Monitoring (P2)
8. Add delivery tracking (Feature 5)
9. Add cost estimation (Feature 6)
10. Scale to more users

## Related

- **Epic:** Multi-Channel Report Delivery (`epics.md`)
- **Architecture:** `docs/features/architecture.md`
- **API Contract:** `docs/reference/api_contract.md`
- **Email Channel (reference):** `src/channels/smtp_mailer.py`
- **Compact Format (planned):** `docs/specs/compact_formatter.md` (to be created)

## Standards to Follow

- ✅ **API Contracts:** Add SMS DTOs to contract before implementation
- ✅ **No Mocked Tests:** Real MessageBird API calls in tests
- ✅ **Provider Selection:** MessageBird as primary, AWS SNS as fallback
- ✅ **Email Formatting:** Adapt compact format principles to SMS

## Notes

- SMS more expensive than email → use wisely
- 160-char limit is hard constraint → prioritization critical
- International roaming considerations (test in Corsica!)
- Consider SMS gateway fallback (MessageBird → AWS SNS)

## Next Steps

**To start implementation:**

```bash
# 1. Start with Feature 1
/feature "SMS Channel Integration"

# 2. Follow workflow
/analyse
/write-spec
# User: "approved"
/tdd-red
/implement
/validate

# 3. Move to Feature 2
/feature "SMS Compact Formatter"
# ... workflow ...

# 4. Complete Feature 3
/feature "SMS Channel Config"
# ... workflow ...

# 5. MVP Complete!
# Test end-to-end, then deploy
```

---

**This is an EXAMPLE user story created by user-story-planner agent**
