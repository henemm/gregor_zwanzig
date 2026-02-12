# Feature: SMS Channel Integration

**Status:** open
**Priority:** HIGH
**Category:** Channel
**Mode:** NEU
**Created:** 2026-02-01

## What

Integration mit SMS-Gateway für den Versand von Wetterberichten per SMS.

## Why

Weitwanderer in Gebieten ohne Internet-Zugang (z.B. GR20) benötigen Wetterinformationen.
SMS funktioniert auch bei schwachem Mobilfunksignal.

## For Whom

- **Primary User:** Weitwanderer mit eingeschränkter Konnektivität
- **Secondary User:** Admins die SMS-Versand konfigurieren

## Affected Systems

- **Channel Layer** (src/channels/) - NEW
  - `sms_sender.py` - SMS gateway integration
  - `sms_config.py` - Configuration handling

- **Config Layer** (src/app/) - MODIFIED
  - `config.py` - Add sms channel option

- **Tests** (tests/tdd/) - NEW
  - `test_sms_sender.py` - Real SMS send/receive tests

## Scoping

- **Files:** 3-4 files
- **LOC estimate:** ~150 lines
- **Complexity:** Medium
- **Within limits:** ✅ YES

### Breakdown

- SMS Sender class: ~80 LOC
- SMS Config handling: ~30 LOC
- Config integration: ~20 LOC
- Real E2E tests: ~20 LOC

## Dependencies

**Requires:**
- SMS gateway account (e.g., Twilio, MessageBird)
- API credentials configuration

**Blocks:**
- SMS Compact Formatter (needs channel to format for)
- SMS Retry Logic (needs base sender to enhance)

## Technical Approach

### SMS Gateway Selection

**Options:**
1. Twilio - Popular, expensive, reliable
2. MessageBird - European, moderate pricing
3. AWS SNS - Cheap, complex setup

**Recommendation:** MessageBird (EU-based, GDPR-compliant)

### Architecture

```
CLI → Config → SMS Sender → MessageBird API
                    ↓
                Send SMS → User Phone
```

### Integration Points

1. **Config:** Add `channel = sms` option
2. **SMS Sender:** New class implementing `ChannelInterface`
3. **Error Handling:** Retry on failure, log errors

### API Contract

New DTO (add to `docs/reference/api_contract.md`):

```python
class SMSMessage:
    to_number: str          # E.164 format required
    body: str               # Max 160 characters
    from_number: str        # Configured sender
    timestamp: datetime     # Send time
```

## Testing Strategy

### Real E2E Tests (NO MOCKS!)

**Test 1: Send SMS**
```python
def test_send_sms_real():
    # 1. Send real SMS via MessageBird
    sms_sender.send("+49...", "Test message")

    # 2. Wait for delivery
    time.sleep(5)

    # 3. Check delivery status via API
    status = sms_sender.get_delivery_status()
    assert status == "delivered"
```

**Test 2: Receive Confirmation**
```python
def test_receive_confirmation():
    # 1. Send SMS
    # 2. Check webhook callback
    # 3. Verify delivery confirmation
```

### Test Account Setup

- Use test phone number from MessageBird
- Configure webhook for delivery confirmations
- Real API calls with test credentials

## Configuration

### Config File (config.ini)

```ini
[channel]
type = sms

[sms]
provider = messagebird
api_key = ${SMS_API_KEY}
from_number = +49...
to_number = +49...
```

### Environment Variables

```bash
export SMS_API_KEY="your-api-key"
```

## Error Handling

### Scenarios

1. **Invalid phone number** → Validate E.164 format, fail fast
2. **API timeout** → Retry with exponential backoff
3. **Rate limit exceeded** → Log error, alert user
4. **Insufficient credits** → Check balance, alert admin

## Security

- API key in environment variable (not in code!)
- Phone numbers validated (prevent injection)
- HTTPS for all API calls
- No logging of phone numbers (GDPR)

## Next Steps

1. **Start workflow:**
   ```bash
   /analyse "SMS Channel Integration"
   ```

2. **Create specification:**
   ```bash
   /write-spec
   ```

3. **Get user approval:**
   User: "approved"

4. **Write failing tests:**
   ```bash
   /tdd-red
   ```

5. **Implement:**
   ```bash
   /implement
   ```

6. **Validate:**
   ```bash
   /validate
   ```

## Related

- Architecture: `docs/features/architecture.md`
- API Contract: `docs/reference/api_contract.md`
- User Story: `docs/project/backlog/stories/sms-berichte.md` (to be created)
- Email Channel Reference: `src/channels/smtp_mailer.py`

## Standards to Follow

- ✅ API Contracts: Add SMS DTO to contract
- ✅ No Mocked Tests: Real SMS send/receive
- ✅ Provider Selection: MessageBird as primary

## Notes

- SMS has 160-char limit → needs compact formatter (separate feature)
- Consider international formats (E.164)
- Test in different countries (roaming)
- Monitor costs (SMS expensive!)

---

**This is an EXAMPLE feature brief created by feature-planner agent**
