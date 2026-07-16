// TDD RED — Issue #582 Paket 1 (Compare-Liste Design-Fidelity 1:1).
//
// Verhaltensbasierte Pure-Function-Tests (echte Aufrufe, Assertions auf
// Rückgabewerte). KEINE Mocks, KEINE Datei-Inhalt-Checks (CLAUDE.md).
//
// RED-Grund: Die vier hier getesteten Helfer existieren in
// ../subscriptionHelpers.ts noch nicht bzw. liefern (presetScheduleLabel)
// noch das alte Lang-Label. Der Import/Aufruf schlägt daher fehl, bis der
// GREEN-Schritt sie ergänzt/anpasst.
//
// Spec: docs/specs/modules/issue_582_compare_list_fidelity.md
//       (Datenherkunft-Tabelle + AC-5 + AC-7)
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_582_list_helpers.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	presetProfileLabel,
	presetTileScheduleLabel,
	relativeLastSent,
	presetChannels
} from '../subscriptionHelpers.ts';
import type { ComparePreset, ActivityProfile } from '../../../types.ts';

// ─── Fixture (echtes ComparePreset-Objekt, keine Mocks) ──────────────────────

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-1',
		name: 'Skigebiete Tirol',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'daily',
		weekday: 0,
		profil: 'wintersport',
		hour_from: 6,
		hour_to: 9,
		empfaenger: ['urlauber@example.com'],
		letzter_versand: undefined,
		top_ort_letzter_versand: null,
		created_at: '2026-01-01T00:00:00Z',
		display_config: {},
		...overrides
	};
}

// ─── 1) presetProfileLabel ───────────────────────────────────────────────────

test('presetProfileLabel: wintersport → lesbares Label (nicht roher Key)', () => {
	const label = presetProfileLabel('wintersport');
	assert.match(label, /Wintersport/, 'enthält "Wintersport"');
	assert.notEqual(label, 'wintersport', 'darf nicht der rohe Key sein');
});

test('presetProfileLabel: wandern → lesbares deutsches Label', () => {
	const label = presetProfileLabel('wandern');
	assert.match(label, /Wander/, 'enthält lesbares Wander-Label');
	assert.notEqual(label, 'wandern', 'darf nicht der rohe Key sein');
});

test('presetProfileLabel: summer_trekking → lesbares deutsches Label (kein Roh-Key)', () => {
	const label = presetProfileLabel('summer_trekking');
	assert.notEqual(label, 'summer_trekking', 'darf nicht der rohe Key sein');
	assert.ok(label.length > 0, 'nicht leer');
});

// Staging-Bug: Großgeschriebene Legacy-Werte (case-insensitive-Fix)
test('presetProfileLabel: SUMMER_TREKKING (Großbuchstaben) → "Sommer-Trekking"', () => {
	const label = presetProfileLabel('SUMMER_TREKKING' as ActivityProfile);
	assert.equal(label, 'Sommer-Trekking', 'Großbuchstaben müssen case-insensitive aufgelöst werden');
});

test('presetProfileLabel: WINTERSPORT (Großbuchstaben) → "Wintersport"', () => {
	const label = presetProfileLabel('WINTERSPORT' as ActivityProfile);
	assert.equal(label, 'Wintersport');
});

test('presetProfileLabel: leerer String → ""', () => {
	assert.equal(presetProfileLabel('' as ActivityProfile), '');
});

test('presetProfileLabel: undefined → ""', () => {
	assert.equal(presetProfileLabel(undefined as unknown as ActivityProfile), '');
});

// ─── 2) presetScheduleLabel (Rhythmus-Kurzlabel) ─────────────────────────────

// Issue #1268 (AC-10): Die Erwartung hat ihre Ursache gewechselt. Vorher leitete
// presetTileScheduleLabel die Stunde aus `hour_from` ab; seit #1268 aus dem
// echten Versand-Slot (morning_time/evening_time). Der Test hiess "daily/06" und
// uebergab hour_from: 6 — er blieb nach dem Umbau nur deshalb gruen, weil die
// Fixture kein morning_time hat und der Migrations-Fallback zufaellig ebenfalls
// 06:00 liefert. Damit haette er einen Rueckbau auf hour_from NICHT gefangen.
// Deshalb steht die Ursache jetzt explizit in der Fixture.
// Erschoepfende Abdeckung (Zero-Value, Abend-Slot, Fallback):
// __tests__/compare_tile_schedule_label_slots.test.ts
test('presetTileScheduleLabel: daily mit Versand-Slot 06:00 → enthält "tägl." und "06"', () => {
	const label = presetTileScheduleLabel(
		makePreset({ schedule: 'daily', morning_time: '06:00:00', hour_from: 9 })
	);
	assert.match(label, /tägl\./i, 'enthält Kurzform "tägl."');
	assert.match(label, /06/, 'enthält die Versandzeit "06" — nicht hour_from=9');
});

test('presetTileScheduleLabel: weekly/weekday=5 → enthält Wochentag "Samstag"', () => {
	// 0=Montag … 5=Samstag (Konvention WEEKDAYS in subscriptionHelpers.ts)
	const label = presetTileScheduleLabel(makePreset({ schedule: 'weekly', weekday: 5 }));
	assert.match(label, /Samstag/, 'enthält den Wochentag Samstag');
});

// ─── 3) relativeLastSent ─────────────────────────────────────────────────────

test('relativeLastSent: heute → "heute"', () => {
	const nowIso = new Date().toISOString();
	assert.match(relativeLastSent(nowIso), /heute/i, 'erkennt heutigen Versand');
});

test('relativeLastSent: vor ~3 Wochen → enthält "Wochen" oder "vor"', () => {
	const threeWeeksAgo = new Date(Date.now() - 21 * 24 * 60 * 60 * 1000).toISOString();
	const label = relativeLastSent(threeWeeksAgo);
	assert.ok(
		/Wochen/.test(label) || /vor/i.test(label),
		`erwartet relatives Label mit "Wochen"/"vor", erhielt: "${label}"`
	);
});

test('relativeLastSent: undefined → leerer String', () => {
	assert.equal(relativeLastSent(undefined), '');
});

// ─── 4) presetChannels (Signal verboten — PO #610) ───────────────────────────

test('presetChannels: Email-Empfänger ≥1 → enthält "Email"', () => {
	const channels = presetChannels(makePreset({ empfaenger: ['a@b.com'] }));
	assert.ok(channels.includes('Email'), `erwartet "Email" in ${JSON.stringify(channels)}`);
});

// Issue #1270 (AC-8/KB-6): Quelle der Kanal-Liste sind die Opt-in-Felder,
// nicht die channel_layouts-Keys (die immer alle Kanäle enthalten). Der alte
// Assert ("channel_layouts telegram/sms → Telegram und SMS") prüfte genau das
// Fehlverhalten und ist damit veraltet — hier auf den neuen Vertrag gezogen.
test('presetChannels: send_telegram/send_sms Opt-in → enthält Telegram und SMS', () => {
	const channels = presetChannels(
		makePreset({
			empfaenger: [],
			send_telegram: true,
			send_sms: true,
			display_config: {}
		})
	);
	assert.ok(channels.includes('Telegram'), `erwartet "Telegram" in ${JSON.stringify(channels)}`);
	assert.ok(channels.includes('SMS'), `erwartet "SMS" in ${JSON.stringify(channels)}`);
});

test('presetChannels: NIEMALS "Signal" — auch bei signal-Key im Layout (PO #610)', () => {
	const channels = presetChannels(
		makePreset({
			empfaenger: ['signal@example.com'],
			send_telegram: true,
			display_config: { channel_layouts: { signal: {}, telegram: {} } }
		})
	);
	assert.ok(
		!channels.some((c) => /signal/i.test(c)),
		`Signal darf NIE erscheinen, erhielt: ${JSON.stringify(channels)}`
	);
});

test('presetChannels: leere Empfänger + keine Layouts → []', () => {
	const channels = presetChannels(makePreset({ empfaenger: [], display_config: {} }));
	assert.deepEqual(channels, []);
});

// F003-Fix (Adversary): signal@firma.com ist eine legitime E-Mail-Adresse → "Email"
test('presetChannels: signal@firma.com ist gültige E-Mail → enthält "Email" (F003-fix)', () => {
	const channels = presetChannels(makePreset({ empfaenger: ['signal@firma.com'], display_config: {} }));
	assert.ok(channels.includes('Email'), `signal@firma.com muss als Email erkannt werden, erhielt: ${JSON.stringify(channels)}`);
});

// F003-Fix: channel_layouts mit key "signal" → Signal-Kanal-Label darf trotzdem NIE erscheinen
test('presetChannels: channel_layouts signal-Key → NIE "Signal" als Kanal (F003-fix)', () => {
	const channels = presetChannels(
		makePreset({
			empfaenger: [],
			send_sms: true,
			display_config: { channel_layouts: { signal: {}, sms: {} } }
		})
	);
	assert.ok(
		!channels.some((c) => /signal/i.test(c)),
		`Signal-Kanal darf NIE erscheinen, erhielt: ${JSON.stringify(channels)}`
	);
	assert.ok(channels.includes('SMS'), `SMS muss erkannt werden, erhielt: ${JSON.stringify(channels)}`);
});

// ─── TDD RED für Spec issue_1229_monitor_hub, AC-3 ───────────────────────────
//
// presetBriefingTimesLabel existiert in ../subscriptionHelpers.ts noch nicht —
// der Import darunter schlägt fehl, bis der GREEN-Schritt die Funktion
// ergänzt. Dadurch fällt die gesamte Datei rot aus (dokumentiertes RED-Muster
// dieser Datei, siehe Kopfkommentar).
//
// Spec: docs/specs/modules/issue_1229_monitor_hub.md (AC-3 + Edge Cases)

import { presetBriefingTimesLabel } from '../subscriptionHelpers.ts';

test('presetBriefingTimesLabel: beide Slots aktiv → "Morgen 06:30 · Abend 18:00"', () => {
	const label = presetBriefingTimesLabel(
		makePreset({
			morning_enabled: true,
			morning_time: '06:30:00',
			evening_enabled: true,
			evening_time: '18:00:00'
		})
	);
	assert.equal(label, 'Morgen 06:30 · Abend 18:00');
});

test('presetBriefingTimesLabel: nur morning aktiv → "Morgen 06:30" (kein "·")', () => {
	const label = presetBriefingTimesLabel(
		makePreset({
			morning_enabled: true,
			morning_time: '06:30:00',
			evening_enabled: false,
			evening_time: undefined
		})
	);
	assert.equal(label, 'Morgen 06:30');
	assert.ok(!label.includes('·'), 'kein Trennpunkt bei nur einem aktiven Slot');
});

test('presetBriefingTimesLabel: nur evening aktiv → "Abend 18:00" (kein "·")', () => {
	const label = presetBriefingTimesLabel(
		makePreset({
			morning_enabled: false,
			morning_time: undefined,
			evening_enabled: true,
			evening_time: '18:00:00'
		})
	);
	assert.equal(label, 'Abend 18:00');
	assert.ok(!label.includes('·'), 'kein Trennpunkt bei nur einem aktiven Slot');
});

test('presetBriefingTimesLabel: beide Slots disabled → "—"', () => {
	const label = presetBriefingTimesLabel(
		makePreset({
			morning_enabled: false,
			morning_time: '06:30:00',
			evening_enabled: false,
			evening_time: '18:00:00'
		})
	);
	assert.equal(label, '—');
});

test('presetBriefingTimesLabel: Alt-Preset ohne Slot-Felder (undefined) → "—", kein Crash', () => {
	const label = presetBriefingTimesLabel(
		makePreset({
			morning_enabled: undefined,
			morning_time: undefined,
			evening_enabled: undefined,
			evening_time: undefined
		})
	);
	assert.equal(label, '—');
});
