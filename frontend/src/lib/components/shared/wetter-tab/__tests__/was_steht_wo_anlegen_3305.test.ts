// TDD RED — Issue #3305 (Teil B von #3041, Epic #3122): Anlege-Variante der Tabellen-Speicherung „Was steht wo“.
// Spec docs/specs/modules/feat_3305_tabelle_trip_anlegen.md, Test Plan Nr. 3 (AC-6) und Nr. 6 (AC-10), Teil von Nr. 1 (AC-4).
//
// FESTGELEGTE SCHNITTSTELLE (der Implementierer folgt diesen Namen):
//   erstelleTabellenSpeicherung({ client, kind, id: '', entwurf, placements, uebernehmen })
//     - `entwurf?: () => Record<string, unknown>` (NEU): ist er gesetzt, arbeitet die Speicherung im Anlege-Modus.
//       Der Client braucht dann `post<T>(pfad, rumpf)`.
//     - `laden()`  : POST /api/briefings/placements/vorschau?kind=<kind>, Rumpf = Entwurf; liefert `placements()` einen
//                    Stand, steht er in `display_config.placements` (die übrigen display_config-Felder des Entwurfs
//                    bleiben). Kein GET, kein PUT. Ticket-Regeln (`nr/version`) wie beim GET.
//     - `aenderung()`: zählt die Version hoch, sonst NICHTS (kein PUT, kein Planen, keine Vorschau; AC-4, AC-10).
//     - `mitgefuehrt()`: wie heute (Version hoch, kein Netz).
//     - `vorschauNachMetrik()` (NEU): Metrikwechsel — Vorschau entprellt (ca. 400 ms, eigener setTimeout) neu laden;
//                    mehrere Aufrufe im Fenster ergeben genau EINEN POST.
//     - `zumMitsenden(x)`: im Anlege-Modus der lokale Stand unabhängig von `x` (keine `stored`-Bedingung).
//
// Reine Logik, Client im Speicher mit einzeln freigebbaren Antworten (kein Netz), Uhr über node:test mock.timers.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/was_steht_wo_anlegen_3305.test.ts

import { test, describe, beforeEach, afterEach, mock } from 'node:test';
import assert from 'node:assert/strict';
import { erstelleTabellenSpeicherung } from '../wasStehtWoSpeicherung.ts';
import type { Placements, PlacementsAntwort } from '../wasStehtWoStand.ts';

type Aufruf = { methode: 'GET' | 'PUT' | 'POST'; pfad: string; rumpf?: any; erledigen: (w?: unknown) => void };

function client() {
	const aufrufe: Aufruf[] = [];
	const neu = (methode: Aufruf['methode'], pfad: string, rumpf?: unknown) =>
		new Promise<any>((erledigen) => aufrufe.push({ methode, pfad, rumpf: rumpf === undefined ? undefined : JSON.parse(JSON.stringify(rumpf)), erledigen }));
	return {
		aufrufe,
		get: <T>(pfad: string) => neu('GET', pfad) as Promise<T>,
		put: <T>(pfad: string, rumpf: unknown) => neu('PUT', pfad, rumpf) as Promise<T>,
		post: <T>(pfad: string, rumpf: unknown) => neu('POST', pfad, rumpf) as Promise<T>
	};
}
// setImmediate läuft an der falschen Uhr vorbei (mock.timers fälscht nur setTimeout).
const ruhe = () => new Promise((r) => setImmediate(r));
const p = (...ids: string[]): Placements => ({ version: 1, rows: ids.map((metric_id) => ({ metric_id })) });
const a = (stand: Placements, marke = ''): PlacementsAntwort =>
	({ kind: 'route', stored: false, placements: stand, rows: [], sms_example: { text: marke, length: marke.length, max_length: 160 } }) as unknown as PlacementsAntwort;
const VORSCHAU = '/api/briefings/placements/vorschau?kind=route';

function aufbau(start: Placements | null = null) {
	const c = client();
	let stand: Placements | null = start;
	let entwurf: Record<string, unknown> = {
		name: 'Neu-3305',
		stages: [{ id: 's1', name: 'A', date: '2026-12-01', waypoints: [] }],
		display_config: { channels: { email: true }, metrics: [{ metric_id: 'wind', enabled: true }] },
		report_config: { email_format: 'full' }
	};
	const uebernommen: PlacementsAntwort[] = [];
	const s = erstelleTabellenSpeicherung({
		client: c,
		kind: 'route',
		id: '',
		entwurf: () => entwurf,
		placements: () => (stand ? structuredClone(stand) : null),
		uebernehmen: (x: PlacementsAntwort) => uebernommen.push(x)
	} as never);
	return {
		c,
		s,
		uebernommen,
		setze: (x: Placements) => (stand = x),
		entwurf: () => entwurf,
		neuerEntwurf: (e: Record<string, unknown>) => (entwurf = e)
	};
}
const methoden = (c: ReturnType<typeof client>) => c.aufrufe.map((x) => `${x.methode} ${x.pfad}`);

beforeEach(() => mock.timers.enable({ apis: ['setTimeout'] }));
afterEach(() => mock.timers.reset());

describe('#3305 Anlege-Variante: Laden über die Vorschau (kein GET, kein PUT)', () => {
	test('laden(): genau ein POST auf die Vorschau mit dem Entwurf als Rumpf; Antwort wird übernommen', async () => {
		const t = aufbau();
		const lauf = t.s.laden();
		await ruhe();
		assert.deepEqual(methoden(t.c), [`POST ${VORSCHAU}`], 'Anlegen hat keine Kennung: Lesen nur über die Vorschau');
		assert.deepEqual(t.c.aufrufe[0].rumpf, t.entwurf(), 'ohne lokalen Stand: Rumpf = Entwurf');
		t.c.aufrufe[0].erledigen(a(p('wind')));
		await lauf;
		assert.equal(t.uebernommen.length, 1);
	});

	test('laden() mit lokalem Stand: display_config.placements trägt ihn, metrics/channels des Entwurfs bleiben', async () => {
		const t = aufbau(p('gust', 'wind'));
		void t.s.laden();
		await ruhe();
		const rumpf = t.c.aufrufe[0]?.rumpf;
		assert.equal(t.c.aufrufe[0]?.methode, 'POST');
		assert.deepEqual(rumpf?.display_config?.placements, p('gust', 'wind'));
		assert.deepEqual(rumpf?.display_config?.metrics, [{ metric_id: 'wind', enabled: true }]);
		assert.deepEqual(rumpf?.display_config?.channels, { email: true });
		assert.equal(rumpf?.name, 'Neu-3305');
	});

	test('zumMitsenden: im Anlegen der lokale Stand auch ohne gespeicherte Tabelle (Datenverlust-Schutz)', () => {
		const t = aufbau(p('gust', 'wind'));
		t.s.aenderung();
		assert.deepEqual(t.s.zumMitsenden(false), p('gust', 'wind'));
	});
});

describe('#3305 AC-4/AC-10 (Test 6): Kartenbedienung ohne Metrikänderung lädt nichts und schreibt nichts', () => {
	test('mehrere Änderungen, Zeitgeber läuft ab: null Aufrufe (kein PUT, keine Vorschau)', async () => {
		const t = aufbau(p('wind'));
		t.setze(p('wind', 'gust'));
		t.s.aenderung();
		t.s.aenderung();
		t.s.aenderung();
		mock.timers.tick(5000);
		await ruhe();
		assert.deepEqual(methoden(t.c), [], 'reine Kartenbedienung: kein Netzaufruf');
	});

	test('Metrikwechsel: genau EINE entprellte Vorschau, erst nach dem Zeitgeber', async () => {
		const t = aufbau(p('wind'));
		t.s.mitgefuehrt();
		t.s.vorschauNachMetrik();
		mock.timers.tick(100);
		t.s.mitgefuehrt();
		t.s.vorschauNachMetrik();
		mock.timers.tick(100);
		t.s.vorschauNachMetrik();
		await ruhe();
		assert.equal(t.c.aufrufe.length, 0, 'vor Ablauf des Zeitgebers kein Aufruf');
		mock.timers.tick(2000);
		await ruhe();
		assert.deepEqual(methoden(t.c), [`POST ${VORSCHAU}`], 'drei Metrikwechsel im Fenster = ein Nachladen');
		mock.timers.tick(5000);
		await ruhe();
		assert.equal(t.c.aufrufe.length, 1, 'kein weiteres Nachladen ohne neue Änderung (keine Schleife)');
	});

	test('die entprellte Vorschau liest den Entwurf beim Senden (neue Metrik steht im Rumpf)', async () => {
		const t = aufbau(p('wind'));
		t.s.vorschauNachMetrik();
		t.neuerEntwurf({ ...t.entwurf(), display_config: { channels: { email: true }, metrics: [{ metric_id: 'wind', enabled: true }, { metric_id: 'rain', enabled: true }] } });
		mock.timers.tick(2000);
		await ruhe();
		assert.deepEqual(
			t.c.aufrufe[0]?.rumpf?.display_config?.metrics?.map((m: { metric_id: string }) => m.metric_id),
			['wind', 'rain']
		);
	});
});

describe('#3305 AC-6 (Test 3): späte Vorschau-Antworten überschreiben keinen neueren Stand', () => {
	test('Antwort, die nach einem Klick eintrifft, wird verworfen', async () => {
		const t = aufbau(p('wind'));
		const lauf = t.s.laden();
		await ruhe();
		assert.equal(t.c.aufrufe[0]?.methode, 'POST', 'Messaufbau: Vorschau läuft');
		t.setze(p('wind', 'gust'));
		t.s.aenderung(); // Klick, während die Vorschau unterwegs ist
		t.c.aufrufe[0].erledigen(a(p('wind'), 'alt'));
		await lauf;
		assert.equal(t.uebernommen.length, 0, 'späte Antwort nach Klick übernommen');
	});

	test('Antwort, die nach einem Metrikwechsel eintrifft, wird verworfen; die neuere gilt', async () => {
		const t = aufbau(p('wind'));
		const erste = t.s.laden();
		await ruhe();
		assert.equal(t.c.aufrufe[0]?.methode, 'POST', 'Messaufbau: erste Vorschau läuft');
		// Metrikwechsel: Karte führt den Stand mit und plant die Vorschau.
		t.setze(p('wind', 'rain'));
		t.s.mitgefuehrt();
		t.s.vorschauNachMetrik();
		mock.timers.tick(2000);
		await ruhe();
		assert.equal(t.c.aufrufe.length, 2, 'zweite Vorschau nach dem Metrikwechsel');
		// Ältere Antwort kommt zuerst: verworfen.
		t.c.aufrufe[0].erledigen(a(p('wind'), 'alt'));
		await erste;
		assert.equal(t.uebernommen.length, 0, 'späte Antwort nach Metrikwechsel übernommen');
		t.c.aufrufe[1].erledigen(a(p('wind', 'rain'), 'neu'));
		await ruhe();
		assert.deepEqual(t.uebernommen.map((x) => x.sms_example?.text), ['neu']);
	});

	test('ältere Antwort NACH der neueren: bleibt verworfen', async () => {
		const t = aufbau(p('wind'));
		const erste = t.s.laden();
		await ruhe();
		t.s.mitgefuehrt();
		t.s.vorschauNachMetrik();
		mock.timers.tick(2000);
		await ruhe();
		assert.equal(t.c.aufrufe.length, 2, 'Messaufbau: zwei Vorschauen unterwegs');
		t.c.aufrufe[1].erledigen(a(p('wind', 'rain'), 'neu'));
		await ruhe();
		t.c.aufrufe[0].erledigen(a(p('wind'), 'alt'));
		await erste;
		assert.deepEqual(t.uebernommen.map((x) => x.sms_example?.text), ['neu']);
	});
});
