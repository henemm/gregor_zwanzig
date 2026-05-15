#!/usr/bin/env bash
# AC-Checks für Issue #190 — Cleanup alter Wizard-Code.
# In RED-Phase: alle ACs fehlschlagen (alter Code noch da, neue Files fehlen).
# In GREEN-Phase: alle ACs passieren.
#
# Aufruf: bash docs/artifacts/issue-190-alter-wizard-cleanup/check-cleanup.sh

set +e
cd "$(git rev-parse --show-toplevel)" || exit 2

FAIL=0
PASS=0
total=0

check() {
  local label="$1"; shift
  total=$((total + 1))
  if "$@"; then
    PASS=$((PASS + 1))
    echo "PASS  $label"
  else
    FAIL=$((FAIL + 1))
    echo "FAIL  $label"
  fi
}

# AC-1: Verzeichnis components/wizard/ existiert nicht mehr
check "AC-1 components/wizard/ entfernt" \
  bash -c '[ ! -d frontend/src/lib/components/wizard ]'

# AC-2: Vier neue Files unter components/edit/
for new_file in EditRouteSection EditStagesSection EditWeatherSection EditReportConfigSection; do
  check "AC-2 components/edit/${new_file}.svelte existiert" \
    test -f "frontend/src/lib/components/edit/${new_file}.svelte"
done

# AC-3: Kein Import auf $lib/components/wizard mehr im Quellcode
check "AC-3 kein \$lib/components/wizard-Import im src/" \
  bash -c '! grep -rq "from .\\\$lib/components/wizard" frontend/src 2>/dev/null'

# AC-4: trip-wizard.spec.ts gelöscht
check "AC-4 frontend/e2e/trip-wizard.spec.ts gelöscht" \
  bash -c '[ ! -f frontend/e2e/trip-wizard.spec.ts ]'

# AC-8: Kein WizardStep1Route/2Stages/3Weather/4ReportConfig mehr im src/
for old_name in WizardStep1Route WizardStep2Stages WizardStep3Weather WizardStep4ReportConfig TripWizard.svelte WizardStepper; do
  check "AC-8 alter Komponentenname '${old_name}' nicht mehr in src/" \
    bash -c "! grep -rq \"${old_name}\" frontend/src 2>/dev/null"
done

echo ""
echo "Summary: ${PASS}/${total} pass, ${FAIL} fail"
exit $FAIL
