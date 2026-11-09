// TDD RED — Issue #1743 (Reiter aufräumen), AC-19/AC-20/AC-21: Anlegen OHNE den Versand-Abschnitt je
// zu berühren. Der Schritt „Versand" entfällt; „Fertig/Anlegen" wird frei, sobald „Alarme" besucht
// ist, und der POST trägt trotzdem die Standard-Versandeinstellungen:
//   - Ortsvergleich: gültiges Standard-`schedule` (der Server antwortet sonst 400 validation_error),
//   - Trip: die Standard-Versandzeiten in `report_config`.
//
// Spec: docs/specs/modules/feat_1743_reiter_aufraeumen.md (Abschnitt 9, AC-19..AC-21)
//
// Messweise (Wirkort, kein Mock-Theater): das ECHTE Instanz-Skript der Anlege-Editoren
// (standardwerteEditorPruefstand.ts / svelteInstanzPruefstand.ts). Gesät werden nur Eingaben, die ein
// Nutzer erzeugt (Name, Datum, Etappen mit GPX bzw. ≥2 Orte, Besuchs-Flags bis Alarme) — NIE `ready`/
// `canActivateNow`: die Freischaltung leitet der Editor selbst her. Der Speicherweg ist der echte
// (`buildAndSave` → `api.post` bzw. `handleActivate` → lokaler Payload-Bau im Editor); nur die
// Netzgrenze zeichnet den gesendeten Körper auf (Trip: `api.post`, Vergleich: `globalThis.fetch`).
// Issue #2727 (AC-8): der Ortsvergleich-Editor bekommt Name/Orte über `stateOverride` statt über
// einen Context — Vergleichsfälle heute rot (VERTRAG FEHLT), Trip-Fälle unverändert grün.
// Ein Versand-Besuchs-Flag wird nicht gesät — genau das ist „Versand nie berührt".
// Issue #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md AC-6): letzter Schritt ist „Zustellung"
// (Flags wtVisited/zuVisited bzw. metrikenVisited/zustellungVisited); „Versand nie berührt" heisst
// weiter: am Versand-Abschnitt wurde nichts geaendert, der POST traegt die Standardwerte.
//
// Ausführen (aus frontend/):
//   node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/anlegen_ohne_versand_beruehrung_postet_standardversand.test.ts

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { COMPARE_EDITOR, TRIP_EDITOR, editorUmgebung, ruhe } from './standardwerteEditorPruefstand.ts';
import type { Knoten } from './svelteInstanzPruefstand.ts';
import { ladeReportZustand } from '../versand-tab/reportConfigPayload.ts';

// ── Trip (/trips/new) ───────────────────────────────────────────────────────────

const ETAPPE_MIT_GPX = { id: 1, name: 'Toblach → Helmhotel', gpx: { file: 'e1.gpx', km: 12, asc: 800 }, waypoints: [] };

async function tripAnlegen(flags: Record<string, boolean>): Promise<{ ready: unknown; gepostet: Knoten[] }> {
	const gepostet: Knoten[] = [];
	const e = await editorUmgebung(TRIP_EDITOR, {
		stateOverride: { activeTab: 'zustellung', isMobileViewport: false, name: 'Karnischer Höhenweg', startDate: '2026-07-01', ...flags },
		stages: [ETAPPE_MIT_GPX],
		api: {
			post: async (url: string, body: unknown) => {
				assert.equal(url, '/api/trips');
				gepostet.push(body as Knoten);
				return { id: 'trip-neu' };
			},
			get: async () => ({})
		}
	});
	assert.equal(typeof e.u.buildAndSave, 'function', 'Messaufbau kaputt: buildAndSave nicht gebunden.');
	assert.equal(e.u.etDone, true, 'Messaufbau kaputt: Etappen mit GPX gelten nicht als erledigt.');
	await e.u.buildAndSave();
	return { ready: e.u.ready, gepostet };
}

describe('AC-19/AC-21: /trips/new — Anlegen nach Zustellung, ohne den Versand-Abschnitt zu berühren', () => {
	test('Positivkontrolle Messaufbau: mit allen Flags wird genau ein POST gesendet', async () => {
		const { gepostet } = await tripAnlegen({ wtVisited: true, zuVisited: true });
		assert.equal(gepostet.length, 1, 'Messaufbau kaputt: auch mit allen Besuchen kein POST /api/trips');
	});

	test('Wetter besucht, Zustellung nicht → kein POST (nicht früher frei)', async () => {
		const { ready, gepostet } = await tripAnlegen({ wtVisited: true });
		assert.equal(ready, false, 'Anlegen ist schon vor dem Zustellungs-Besuch frei');
		assert.equal(gepostet.length, 0);
	});

	test('Zustellung besucht, Versand nie berührt → POST mit den Standard-Versandzeiten', async () => {
		const { ready, gepostet } = await tripAnlegen({ wtVisited: true, zuVisited: true });
		assert.equal(ready, true, '#2794 AC-6 FAIL: „Trip speichern" ist nach dem Zustellungs-Besuch noch gesperrt.');
		assert.equal(gepostet.length, 1, '#1743 AC-21 FAIL: kein POST /api/trips');
		const rc = gepostet[0].report_config as Knoten | undefined;
		assert.ok(rc, `#1743 AC-21 FAIL: POST ohne report_config — die Standard-Versandzeiten fehlen. Körper: ${JSON.stringify(gepostet[0]).slice(0, 300)}`);
		const standard = ladeReportZustand(undefined);
		// Zeiten reisen im Wire-Format HH:MM:SS (baueReportConfigPayload, wie der Hub-Speicherweg).
		const wert = (feld: string) => (feld.endsWith('_time') && typeof rc![feld] === 'string' ? (rc![feld] as string).slice(0, 5) : rc![feld]);
		for (const feld of ['morning_enabled', 'morning_time', 'evening_enabled', 'evening_time', 'send_email'] as const) {
			assert.equal(wert(feld), standard[feld],`#1743 AC-21 FAIL: report_config.${feld} = ${JSON.stringify(rc![feld])}, Standard ${JSON.stringify(standard[feld])}`);
		}
	});
});

// ── Ortsvergleich (/compare/new) ────────────────────────────────────────────────

const presetPosts: Knoten[] = [];
let originalFetch: typeof globalThis.fetch;
before(() => {
	originalFetch = globalThis.fetch;
	globalThis.fetch = (async (input: unknown, init?: { method?: string; body?: unknown }) => {
		const url = String(input);
		if (url.includes('/api/compare/presets') && init?.method === 'POST') {
			presetPosts.push(JSON.parse(String(init.body)) as Knoten);
			return new Response(JSON.stringify({ id: 'cmp-neu' }), { status: 201, headers: { 'content-type': 'application/json' } });
		}
		return new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } });
	}) as typeof globalThis.fetch;
});
after(() => {
	globalThis.fetch = originalFetch;
});

async function vergleichAnlegen(flags: Record<string, boolean>): Promise<{ frei: unknown; gepostet: Knoten[] }> {
	presetPosts.length = 0;
	// Issue #2727 (AC-8): kein Context mehr — Name und Orte reisen ueber stateOverride.
	const e = await editorUmgebung(COMPARE_EDITOR, {
		stateOverride: {
			activeTab: 'zustellung',
			isMobileViewport: false,
			name: 'Sardinien-Woche',
			pickedIds: ['loc-a', 'loc-b', 'loc-c'],
			...flags
		},
		window: { matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }) }
	});
	assert.equal(typeof e.u.handleActivate, 'function', 'Messaufbau kaputt: handleActivate nicht gebunden.');
	assert.equal(
		e.u.orteOk,
		true,
		'VERTRAG FEHLT (#2727): CompareNewEditor uebernimmt name/pickedIds nicht aus stateOverride (ohne Context).'
	);
	await e.u.handleActivate();
	await ruhe();
	return { frei: e.u.canActivateNow, gepostet: [...presetPosts] };
}

describe('AC-19/AC-20: /compare/new — Aktivieren nach Zustellung, ohne den Versand-Abschnitt zu berühren', () => {
	test('Positivkontrolle Messaufbau: mit allen Flags wird genau ein POST gesendet', async () => {
		const { gepostet } = await vergleichAnlegen({ metrikenVisited: true, zustellungVisited: true });
		assert.equal(gepostet.length, 1, 'Messaufbau kaputt: auch mit allen Besuchen kein POST /api/compare/presets');
	});

	test('Wetter besucht, Zustellung nicht → kein POST (nicht früher frei)', async () => {
		const { frei, gepostet } = await vergleichAnlegen({ metrikenVisited: true });
		assert.equal(frei, false, '„Briefing aktivieren" ist schon vor dem Zustellungs-Besuch frei');
		assert.equal(gepostet.length, 0);
	});

	test('Zustellung besucht, Versand nie berührt → POST mit gültigem Standard-schedule', async () => {
		const { frei, gepostet } = await vergleichAnlegen({ metrikenVisited: true, zustellungVisited: true });
		assert.equal(frei, true, '#2794 AC-6 FAIL: „Briefing aktivieren" ist nach dem Zustellungs-Besuch noch gesperrt.');
		assert.equal(gepostet.length, 1, '#1743 AC-20 FAIL: kein POST /api/compare/presets');
		// Gueltig ist, was der Go-Handler annimmt (internal/handler/compare_preset.go:
		// "daily"|"weekly"|"manual"); der Wizard-Standard 'daily_morning' reist als 'daily'
		// (compareEditorSave.buildNewComparePresetPayload).
		assert.ok(
			['daily', 'weekly', 'manual'].includes(gepostet[0].schedule as string),
			`#1743 AC-20 FAIL: POST ohne gültiges schedule (Server antwortet 400): ${JSON.stringify(gepostet[0].schedule)}`
		);
		assert.equal(gepostet[0].schedule, 'daily', '#1743 AC-20 FAIL: nicht der Standard-schedule');
	});
});
