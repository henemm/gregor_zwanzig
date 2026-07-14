// TDD RED — Issue #1256 Scheibe 7: Hub-Versand-Tab Inline-Edit via
// eingebettetem VersandTab (context="vergleich") + Aktivierungs-Karte
// (AC-17, AC-18, AC-35, AC-36).
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 7
//   (AC-17/18/35/36/37); AC-19/AC-20 separat (bestehender Vorschau-Test
//   bzw. statischer Totcode-Nachweis).
// Context: docs/context/feat-1256-s7-hub-versand-inline.md.
//
// Ist: `CompareTabs.svelte` rendert den Versand-Bereich als Bespoke-Nachbau
// (disabled Kanal-Switches, `goToEditVersand()`-Redirect). Der geteilte
// `VersandTab context="vergleich"` mutiert ausschliesslich `wiz.*` (kein
// Self-Save) — im Hub gibt es keinen Speichern-Button, also muss die in S6
// etablierte Bridge (`compareHubWizardBridge.ts`) die Versand-Felder
// hydratisieren und Event-diskretisiert per PUT persistieren.
//
// Die hier importierten Exporte existieren noch NICHT — die named imports
// schlagen heute fehl (RED), bis Phase 6 die Bridge erweitert.
//
// API-Design (von dieser RED-Phase festgelegt, S6-Praezedenz):
//   - hydrateVersandFieldsFromPreset(preset): Plain-Objekt mit GENAU den
//     Feldern, die VersandTab im vergleich-Zweig aus `wiz` liest.
//     Defaults identisch zur Edit-Routen-Hydration
//     (routes/compare/[id]/edit/+page.svelte:44-61): morningEnabled ?? true,
//     morningTime ?? '06:00' (HH:MM, aus HH:MM:SS gesliced),
//     eveningEnabled ?? false, eveningTime ?? '18:00', endDate ?? null,
//     sendTelegram/sendSms ?? false, alertCooldownMinutes/alertQuietFrom/
//     alertQuietTo ?? undefined. sendEmail ist IMMER true — ComparePreset
//     kennt kein send_email-Feld (vorbestehende Luecke, Known Limitation
//     der Freigabe; Persistenz-Nachweis laeuft ueber Telegram/SMS).
//   - VersandSnapshot + flushPendingVersandSave(preset, current, before):
//     analog flushPendingCorridorSave — null bei unveraendertem Snapshot
//     (Waechter gegen unnoetige PUTs, #1234), sonst fertiger PUT-Payload
//     via buildHubPutPayload (Read-Modify-Write: alle nicht-Versand-Felder
//     unveraendert aus `preset`, #1257-Kontext).
//   - hubActivationBanner(status): reines Modell der Aktivierungs-Karte
//     (Soll: screen-compare-detail.jsx:273-277 + 313-325). Die JSX-Copy
//     "im konfigurierten Rhythmus" ist eine bekannte timeWindow-Stale-Spur
//     und wird NICHT mitkopiert (Spec § Umsetzungsregel Stale-Spuren).

import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import type { ComparePreset } from '../../../types.ts';
import {
	hydrateVersandFieldsFromPreset,
	flushPendingVersandSave,
	hubActivationBanner,
	type VersandSnapshot
} from '../compareHubWizardBridge.ts';

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-42',
		name: 'Skigebiete Tirol',
		location_ids: ['loc-1', 'loc-2', 'loc-3'],
		schedule: 'daily',
		weekday: 0,
		profil: 'wintersport',
		hour_from: 6,
		hour_to: 9,
		empfaenger: ['urlauber@example.com'],
		forecast_hours: 48,
		letzter_versand: undefined,
		top_ort_letzter_versand: null,
		created_at: '2026-01-01T00:00:00Z',
		corridors: [{ metric: 'snow_depth_cm', range: [20, null], notify: true, mark: true, prio: 'hoch' }],
		send_telegram: true,
		send_sms: false,
		morning_enabled: true,
		morning_time: '06:30:00',
		evening_enabled: true,
		evening_time: '19:15:00',
		end_date: '2026-08-01',
		alert_cooldown_minutes: 90,
		alert_quiet_from: '22:00',
		alert_quiet_to: '06:00',
		display_config: {
			region: 'Tirol',
			ideal_ranges: { snow_depth_cm: { min: 20, max: null } },
			channel_layouts: { email: { columns: ['temp'] } },
			active_metrics: ['snow_depth_cm', 'wind_gust'],
			metric_alert_levels: { snow_depth_cm: 'warn', wind_gust: 'mark' }
		},
		...overrides
	};
}

function makeSnapshot(overrides: Partial<VersandSnapshot> = {}): VersandSnapshot {
	return {
		sendTelegram: true,
		sendSms: false,
		morningEnabled: true,
		morningTime: '06:30',
		eveningEnabled: true,
		eveningTime: '19:15',
		endDate: '2026-08-01',
		alertCooldownMinutes: 90,
		alertQuietFrom: '22:00',
		alertQuietTo: '06:00',
		...overrides
	};
}

describe('AC-36 (Basis): hydrateVersandFieldsFromPreset — Versand-Felder aus dem Preset', () => {
	test('hydratisiert alle Versand-Felder aus einem voll belegten Preset', () => {
		const h = hydrateVersandFieldsFromPreset(makePreset());
		assert.strictEqual(h.sendTelegram, true);
		assert.strictEqual(h.sendSms, false);
		assert.strictEqual(h.morningEnabled, true);
		assert.strictEqual(h.morningTime, '06:30'); // HH:MM aus HH:MM:SS
		assert.strictEqual(h.eveningEnabled, true);
		assert.strictEqual(h.eveningTime, '19:15');
		assert.strictEqual(h.endDate, '2026-08-01');
		assert.strictEqual(h.alertCooldownMinutes, 90);
		assert.strictEqual(h.alertQuietFrom, '22:00');
		assert.strictEqual(h.alertQuietTo, '06:00');
	});

	test('Defaults identisch zur Edit-Routen-Hydration, wenn Versand-Felder fehlen', () => {
		const bare = makePreset({
			send_telegram: undefined,
			send_sms: undefined,
			morning_enabled: undefined,
			morning_time: undefined,
			evening_enabled: undefined,
			evening_time: undefined,
			end_date: undefined,
			alert_cooldown_minutes: undefined,
			alert_quiet_from: undefined,
			alert_quiet_to: undefined
		});
		const h = hydrateVersandFieldsFromPreset(bare);
		assert.strictEqual(h.sendTelegram, false);
		assert.strictEqual(h.sendSms, false);
		assert.strictEqual(h.morningEnabled, true);
		assert.strictEqual(h.morningTime, '06:00');
		assert.strictEqual(h.eveningEnabled, false);
		assert.strictEqual(h.eveningTime, '18:00');
		assert.strictEqual(h.endDate, null);
		assert.strictEqual(h.alertCooldownMinutes, undefined);
		assert.strictEqual(h.alertQuietFrom, undefined);
		assert.strictEqual(h.alertQuietTo, undefined);
	});

	test('sendEmail ist immer true (ComparePreset hat kein send_email-Feld — Known Limitation)', () => {
		const h = hydrateVersandFieldsFromPreset(makePreset());
		assert.strictEqual(h.sendEmail, true);
	});
});

describe('AC-35/AC-36: flushPendingVersandSave — Event-diskretisierte PUT-Persistenz', () => {
	test('liefert null, wenn sich der Versand-Snapshot nicht geaendert hat (Waechter gegen No-Op-PUTs)', () => {
		const preset = makePreset();
		const snap = makeSnapshot();
		assert.strictEqual(flushPendingVersandSave(preset, snap, makeSnapshot()), null);
		// before=null → Baseline ist current selbst → ebenfalls kein PUT
		assert.strictEqual(flushPendingVersandSave(preset, snap, null), null);
	});

	test('AC-35: Kanal-Toggle (sendTelegram → false) landet im PUT-Body', () => {
		const preset = makePreset();
		const payload = flushPendingVersandSave(
			preset,
			makeSnapshot({ sendTelegram: false }),
			makeSnapshot()
		);
		assert.ok(payload, 'geaenderter Kanal muss einen PUT-Payload liefern');
		assert.strictEqual(payload.url, '/api/compare/presets/cmp-42');
		assert.strictEqual(payload.body.send_telegram, false);
		assert.strictEqual(payload.body.send_sms, false);
	});

	test('AC-36: geaenderte Briefing-Uhrzeit wird als HH:MM:SS persistiert', () => {
		const payload = flushPendingVersandSave(
			makePreset(),
			makeSnapshot({ morningTime: '07:15' }),
			makeSnapshot()
		);
		assert.ok(payload);
		assert.strictEqual(payload.body.morning_time, '07:15:00');
		assert.strictEqual(payload.body.evening_time, '19:15:00');
	});

	test('endDate-Sentinel: null ("bis auf Weiteres") sendet end_date="" (Loesch-Sentinel aus #1232)', () => {
		const payload = flushPendingVersandSave(
			makePreset(),
			makeSnapshot({ endDate: null }),
			makeSnapshot()
		);
		assert.ok(payload);
		assert.strictEqual(payload.body.end_date, '');
	});

	test('Read-Modify-Write (#1257-Kontext): Nicht-Versand-Felder bleiben unveraendert aus dem Preset', () => {
		const preset = makePreset();
		const payload = flushPendingVersandSave(
			preset,
			makeSnapshot({ sendSms: true }),
			makeSnapshot()
		);
		assert.ok(payload);
		assert.deepStrictEqual(payload.body.corridors, preset.corridors);
		assert.deepStrictEqual(
			payload.body.display_config?.metric_alert_levels,
			preset.display_config!.metric_alert_levels
		);
		assert.deepStrictEqual(
			payload.body.display_config?.active_metrics,
			preset.display_config!.active_metrics
		);
		assert.deepStrictEqual(payload.body.empfaenger, preset.empfaenger);
		assert.strictEqual(payload.body.schedule, preset.schedule);
	});
});

describe('AC-17/AC-18: hubActivationBanner — Aktivierungs-Karten-Modell (Soll: screen-compare-detail.jsx:273-277)', () => {
	test('AC-17: status=active → Label "Aktiv", CTA "Pausieren"', () => {
		const b = hubActivationBanner('active');
		assert.strictEqual(b.statusLabel, 'Aktiv');
		assert.strictEqual(b.cta, 'Pausieren');
	});

	test('AC-18: active-Copy nennt Lauf ohne Enddatum ("bis du pausierst"), ohne Rhythmus-Stale-Spur', () => {
		const b = hubActivationBanner('active');
		assert.ok(b.text.includes('bis du pausierst'), `Copy fehlt "bis du pausierst": ${b.text}`);
		assert.ok(!b.text.includes('Rhythmus'), 'timeWindow-Stale-Spur "Rhythmus" darf nicht mitkopiert werden (Spec § Umsetzungsregel)');
	});

	test('status=paused → Label "Pausiert", CTA "Aktivieren", Copy nennt dass kein Briefing rausgeht', () => {
		const b = hubActivationBanner('paused');
		assert.strictEqual(b.statusLabel, 'Pausiert');
		assert.strictEqual(b.cta, 'Aktivieren');
		assert.ok(b.text.includes('kein Briefing'), `Copy fehlt "kein Briefing": ${b.text}`);
	});

	test('status=draft → Label "Entwurf", CTA "Aktivieren"', () => {
		const b = hubActivationBanner('draft');
		assert.strictEqual(b.statusLabel, 'Entwurf');
		assert.strictEqual(b.cta, 'Aktivieren');
	});
});
