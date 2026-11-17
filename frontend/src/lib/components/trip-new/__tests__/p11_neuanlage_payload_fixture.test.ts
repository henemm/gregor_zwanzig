// Issue #3047 Runde 7, Paket p11: Neuanlage-POST-Rumpf als versionierte Fixture.
// Spec: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md („Nachtrag Runde 7",
// PO 2026-11-16 „Amtliche Warnungen Neuanlage", loest #1258 AC-4 ab).
//
// Die ECHTEN Anlege-Funktionen (`buildCreateTripPayload` mit dem Start-Alarmzustand, wie
// TripNewEditor ihn sendet; `buildNewComparePresetPayload` mit dem Standard-Feldsatz) bauen den
// POST-Rumpf. Er muss genau der Fixture
//   tests/fixtures/einstellung_gleich_mail/neuanlage_p11_payload.json
// gleichen. Die Python-Seite (tests/tdd/test_3047_p11_neuanlage_warnungen.py) speist dieselbe
// Fixture durch Loader -> Zeitplaner -> Transport-Mitschrift; so laeuft sie im CI-Job `test`
// ohne Node, und jede Drift des Frontend-Rumpfs macht DIESEN Test rot (Job `frontend-test`).
//
// Neu erzeugen (nur bei bewusster Rumpf-Aenderung):
//   cd frontend && GZ_FIXTURE_SCHREIBEN=1 npm test -- src/lib/components/trip-new/__tests__/p11_neuanlage_payload_fixture.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import * as T from '../tripNewLogic.ts';
import * as C from '../../compare/compareEditorSave.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> trip-new -> components -> lib -> src -> frontend -> Repo
const FIXTURE = path.resolve(
	HERE, '../../../../../..', 'tests', 'fixtures', 'einstellung_gleich_mail', 'neuanlage_p11_payload.json'
);

function anlageRuempfe(): { trip: Record<string, unknown>; vergleich: Record<string, unknown> } {
	const alarm = T.initialCreateTripAlarmState();
	const trip = T.buildCreateTripPayload({
		name: 'Neu', startDate: '2026-11-20',
		stages: [{ id: 'a', name: 'A', waypoints: [] }], channels: { email: true }, alarm,
		officialAlertsEnabled: alarm.officialWarningsEnabled
	} as never) as unknown as Record<string, unknown>;
	const f = C.compareFeldsatzStandard();
	const vergleich = C.buildNewComparePresetPayload({ ...f, alertChannels: undefined } as never) as unknown as Record<string, unknown>;
	return { trip, vergleich };
}

// Trip- und Etappen-IDs erzeugt der Editor zufaellig; sie tragen keine Warn-Aussage und werden
// fuer den Vergleich auf einen festen Platzhalter gesetzt (alles andere bleibt byte-genau).
function ohneZufallsIds(r: ReturnType<typeof anlageRuempfe>) {
	const kopie = JSON.parse(JSON.stringify(r));
	kopie.trip.id = 'neu';
	for (const s of kopie.trip.stages as { id: string }[]) s.id = 'etappe';
	return kopie;
}

test('p11 Neuanlage: POST-Rumpf von Trip und Vergleich gleicht der Fixture', () => {
	const ist = ohneZufallsIds(anlageRuempfe());
	if (process.env.GZ_FIXTURE_SCHREIBEN === '1') {
		fs.writeFileSync(FIXTURE, JSON.stringify(ist, null, 2) + '\n', 'utf-8');
	}
	assert.ok(fs.existsSync(FIXTURE), `Fixture fehlt: ${FIXTURE}`);
	assert.deepEqual(ist, JSON.parse(fs.readFileSync(FIXTURE, 'utf-8')));
});

test('p11 Neuanlage: beide Warn-Felder ausdruecklich true (Trip und Vergleich)', () => {
	for (const [art, rumpf] of Object.entries(anlageRuempfe())) {
		const r = rumpf as { official_alerts_enabled?: unknown; official_warnings?: { enabled?: unknown } };
		assert.equal(r.official_alerts_enabled, true, `${art}: Briefing-Feld`);
		assert.equal(r.official_warnings?.enabled, true, `${art}: Alarm-Feld`);
	}
});
