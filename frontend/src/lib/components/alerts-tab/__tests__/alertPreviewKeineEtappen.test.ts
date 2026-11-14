// Issue #2069 AC-8 (Fix-Loop F-A1): Trip ohne Etappe mit mindestens zwei
// Wegpunkten zeigt in der Alarm-Vorschau den Hinweis `alert-preview-no-stages`
// statt eines Fehlertexts und bietet KEINEN Abruf an; ein Trip mit echter
// Etappe (auch an einem kuenftigen Datum) zeigt den Hinweis nicht, ebenso der
// Ortsvergleich.
// Spec: docs/specs/modules/alert_preview_echte_segmente.md
//
// Testart: echtes serverseitiges Rendern der echten AlertPreviewCard
// (svelte/server, Hooks frontend/test-svelte-ssr-hooks.mjs). Keine Mocks.
// "Kein Abruf" ist im Node-Kontext dort beobachtbar, wo er wirkt: der Abruf
// startet ausschliesslich ueber den Knopf `alert-preview-load-btn`
// (onclick={loadPreview}); fehlt der Knopf, kann kein Abruf ausgeloest werden.
// Mit einer aktiven Regel rendert die Karte im Normalfall genau diesen Knopf —
// der Vergleichsfall (3) belegt, dass der Messaufbau ihn sieht.
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/alerts-tab/__tests__/alertPreviewKeineEtappen.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

// Pfadregel #1409: relativ zu DIESER Datei.
const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> alerts-tab -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const { render } = await import('svelte/server');
const AlertPreviewCard = (await import(pathToFileURL(path.resolve(HERE, '../AlertPreviewCard.svelte')).href)).default;

const REGELN = [
	{ id: 'r1', metric: 'wind_gust', threshold: 60, kind: 'absolute', severity: 'warning', enabled: true }
];

const wp = (id: string, lat: number, lon: number) => ({ id, name: id, lat, lon, elevation_m: 1000 });

const tid = (t: string) => `data-testid="${t}"`;
const html = (props: Record<string, unknown>) =>
	render(AlertPreviewCard as never, { props: { alertRules: REGELN, ...props } } as never).body;

describe('AC-8: Hinweis statt Fehler, wenn der Trip keine Etappe mit >= 2 Wegpunkten hat', () => {
	test('(1) route ohne Etappen: Hinweis da, kein Abrufknopf, kein Fehlertext', () => {
		const h = html({ kind: 'route', id: 't-2069', stages: [] });
		assert.ok(h.includes(tid('alert-preview-no-stages')), 'Hinweis alert-preview-no-stages fehlt');
		assert.match(h, /Trip hat noch keine Etappen mit Wegpunkten/);
		assert.equal(h.includes(tid('alert-preview-load-btn')), false, 'ohne Etappe darf kein Abruf angeboten werden');
		assert.equal(h.includes(tid('alert-preview-error')), false);
	});

	test('(2) route mit Etappe aus nur EINEM Wegpunkt: Hinweis da, kein Abrufknopf', () => {
		const h = html({
			kind: 'route',
			id: 't-2069',
			stages: [{ id: 'S1', name: 'Etappe 1', date: '2026-11-14', waypoints: [wp('G1', 42.1, 9.0)] }]
		});
		assert.ok(h.includes(tid('alert-preview-no-stages')), 'eine Etappe mit 1 Wegpunkt ergibt kein Segment — Hinweis erwartet');
		assert.equal(h.includes(tid('alert-preview-load-btn')), false);
	});

	test('(3) route mit Etappe aus 2 Wegpunkten an kuenftigem Datum: kein Hinweis, Abrufknopf da', () => {
		const h = html({
			kind: 'route',
			id: 't-2069',
			stages: [
				{ id: 'S0', name: 'leer', date: '2027-06-01', waypoints: [] },
				{ id: 'S1', name: 'Etappe 1', date: '2027-06-02', waypoints: [wp('G1', 42.1, 9.0), wp('G2', 42.2, 9.1)] }
			]
		});
		assert.equal(h.includes(tid('alert-preview-no-stages')), false, 'geplanter Trip mit Etappe: Beispielwarnung bleibt abrufbar');
		assert.ok(h.includes(tid('alert-preview-load-btn')), 'Abrufknopf fehlt (Messaufbau)');
	});

	test('(4) vergleich (ohne Etappen, mit Orten): kein Etappen-Hinweis', () => {
		const h = html({ kind: 'vergleich', id: 'v-2069', locationIds: ['loc-a'] });
		assert.equal(h.includes(tid('alert-preview-no-stages')), false, 'der Etappen-Hinweis gilt nur im Trip');
		assert.ok(h.includes(tid('alert-preview-load-btn')));
	});
});
