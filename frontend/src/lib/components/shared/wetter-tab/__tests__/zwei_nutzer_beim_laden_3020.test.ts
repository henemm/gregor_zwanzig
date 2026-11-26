// Issue #3020 R1, AC-2 (Ersatz für das mit #3357 gelöschte lade_kanal_layouts_aus_trip, #2422: zwei Nutzer beim Laden).
//
// Anna und Bruno (zwei verschiedene user_id) melden sich nacheinander im selben Browser-Tab an — die Module bleiben
// geladen, nur die Sitzung wechselt. Der Ersatz-Server antwortet wie Go NUR nach der Sitzung: die Pfade der beiden
// sind gleich (dieselbe Abo-Kennung je Nutzer), die Daten verschieden. Der ECHTE Reiter Wetter, die ECHTE Karte
// „Was steht wo“ und der ECHTE Reiter Zustellung zeigen und speichern ausschließlich den eigenen Stand, in Trip und
// Orten, auch wenn der zweite lädt, bevor der erste speichert. Pfadregel #1409: alle Pfade relativ zu DIESER Datei.

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import * as P from '../../../trip-detail/__tests__/tripMehrreiterPruefstand.ts';
import { live, liveVergleichsKatalog } from './wetterTabDaten.ts';

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
type Nutzer = 'gz3020-anna' | 'gz3020-bruno';
type Kontext = 'route' | 'vergleich';
const ABO_ID = 'abo-1';

/** Gespeicherter Stand je Nutzer: verschiedene Auswahl, Tabelle, Vorlagen, Zustellzeit, Schalter. */
const EIGEN: Record<Nutzer, { metriken: string[]; telegramAus: string; ampel: string; vorlage: string; zeit: string; nacht: boolean; stil: string }> = {
	'gz3020-anna': { metriken: ['temperature', 'wind'], telegramAus: 'wind', ampel: 'skitouren', vorlage: 'Annas Vorlage', zeit: '05:30:00', nacht: false, stil: 'kurzform' },
	'gz3020-bruno': { metriken: ['gust'], telegramAus: 'gust', ampel: 'radtour', vorlage: 'Brunos Vorlage', zeit: '09:15:00', nacht: true, stil: 'rich' }
};
const placements = (u: Nutzer) => ({
	version: 1,
	rows: EIGEN[u].metriken.map((metric_id) => (metric_id === EIGEN[u].telegramAus ? { metric_id, places: { telegram: false } } : { metric_id })),
	outlook_reports: u === 'gz3020-anna' ? ['morning'] : []
});
function abo(u: Nutzer, kontext: Kontext): J {
	const e = EIGEN[u];
	if (kontext === 'route')
		return {
			id: ABO_ID,
			user_id: u,
			name: `Trip ${u}`,
			stages: [],
			display_config: { metrics: e.metriken.map((metric_id) => ({ metric_id, enabled: true, besitzer: u })), ampel: { template: e.ampel }, placements: placements(u), show_night_block: e.nacht },
			report_config: { morning_time: e.zeit, telegram_style: e.stil }
		};
	return {
		id: ABO_ID,
		user_id: u,
		name: `Orte ${u}`,
		location_ids: ['o1'],
		morning_time: e.zeit,
		display_config: { active_metrics: e.metriken.map((metric_id) => ({ metric_id, aggregation: 'max', besitzer: u })), ampel: { template: e.ampel }, placements: placements(u), telegram_style: e.stil }
	};
}

let sitzung: Nutzer = 'gz3020-anna';
let gesendet: { nutzer: Nutzer; pfad: string; rumpf: J }[] = [];
const KATALOG = live();
const ORTE_KATALOG = liveVergleichsKatalog();
const basisFetch = globalThis.fetch;
const antwort = (x: unknown) => new Response(JSON.stringify(x), { status: 200, headers: { 'Content-Type': 'application/json', ETag: `"${sitzung}"` } });

beforeEach(() => {
	clearEtagRegistry();
	gesendet = [];
	(globalThis as { fetch: unknown }).fetch = async (input: unknown, init?: RequestInit) => {
		const pfad = String(input);
		const u = sitzung;
		const aufgeloest = await P.aufloesungAntwort(input, init);
		if (aufgeloest) return aufgeloest;
		if ((init?.method ?? 'GET') !== 'GET') {
			gesendet.push({ nutzer: u, pfad, rumpf: JSON.parse(String(init?.body)) });
			return antwort(abo(u, pfad.includes('compare') ? 'vergleich' : 'route'));
		}
		if (pfad === '/api/metrics') return antwort(KATALOG.metrics);
		if (pfad === '/api/templates') return antwort(KATALOG.templates);
		if (pfad === '/api/compare/metrics?lang=de') return antwort(ORTE_KATALOG);
		if (pfad === '/api/metric-presets') return antwort((['route', 'vergleich'] as const).map((kind) => ({ id: `v-${u}-${kind}`, name: EIGEN[u].vorlage, kind, ampel: { template: 'allgemein', metrics: {} } })));
		const kind = pfad.match(/^\/api\/briefings\/abo-1\/placements\?kind=(route|vergleich)$/)?.[1] as Kontext | undefined;
		assert.ok(kind, `unerwarteter Abruf ${pfad}`);
		const a = abo(u, kind);
		return antwort(
			P.tabellenAntwort(kind, a.display_config, EIGEN[u].metriken, { ...(a.report_config ?? {}), show_night_block: EIGEN[u].nacht, telegram_style: EIGEN[u].stil })
		);
	};
});
afterEach(() => {
	(globalThis as { fetch: unknown }).fetch = basisFetch;
});

/** Anmelden und den Hub öffnen: Reiter Wetter samt Karte und Reiter Zustellung, alles aus der Sitzung geladen. */
async function oeffnen(u: Nutzer, kontext: Kontext) {
	sitzung = u;
	const ctl = P.erstelleController(ABO_ID, kontext === 'route' ? 'trip' : 'vergleich');
	const eigenes = { [kontext === 'route' ? 'trip' : 'preset']: abo(u, kontext), saveController: ctl, enqueueHubWrite: <T>(fn: () => Promise<T>) => fn() };
	const wetter = await P.bauen(P.DATEI.wetter, { ...P.LAUFZEIT, context: kontext, createMode: false, ...eigenes });
	await wetter.u.laden();
	assert.equal(wetter.u.phase, 'bereit', 'Messaufbau: Reiter Wetter hat nicht geladen');
	// Die Karte lädt ihre Tabelle über das echte `api` aus der Sitzung.
	const karte = await P.karteImReiter(wetter);
	const zustellung = await P.bauen(P.DATEI.zustellung, { ...P.LAUFZEIT, context: kontext, panel: eigenes });
	return { wetter, karte, zustellung, ctl };
}
type Hub = Awaited<ReturnType<typeof oeffnen>>;

function zeigtNurEigenes(h: Hub, u: Nutzer, kontext: Kontext): void {
	const e = EIGEN[u];
	const auswahl = h.wetter.u.stand.auswahl as string[];
	for (const id of e.metriken) assert.ok(auswahl.includes(id), `${u}: ${id} fehlt in der Grundauswahl`);
	const andere = Object.values(EIGEN).find((x) => x !== e)!;
	for (const id of andere.metriken) assert.ok(!auswahl.includes(id), `${u}: fremde Metrik ${id} in der Grundauswahl`);
	assert.equal(h.wetter.u.stand.vorlageId, e.ampel, `${u}: aufgelöste Ampel (#2988)`);
	assert.deepEqual(h.wetter.u.daten.eigene.map((v: J) => v.name), [e.vorlage], `${u}: eigene Vorlagen`);
	assert.deepEqual(h.karte.u.lokal, placements(u), `${u}: Tabelle der Karte`);
	const f = h.karte.u.felderAusAntwort(h.karte.u.antwort);
	assert.deepEqual([f.show_night_block, f.telegram_style], [e.nacht, e.stil], `${u}: Schalter der Karte`);
	assert.equal(h.zustellung.u.stand.morgenZeit, e.zeit.slice(0, 5), `${u}: Zustellzeit`);
	assert.equal((h.wetter.u.abo() as J).user_id, u, kontext);
}

for (const kontext of ['route', 'vergleich'] as const) {
	describe(`#3020 AC-2 ${kontext}: zwei Nutzer laden nacheinander im selben Tab`, () => {
		test(`${kontext}: jeder sieht nur seine Auswahl, Tabelle, Vorlagen, Schalter und Zustellzeit`, async () => {
			zeigtNurEigenes(await oeffnen('gz3020-anna', kontext), 'gz3020-anna', kontext);
			zeigtNurEigenes(await oeffnen('gz3020-bruno', kontext), 'gz3020-bruno', kontext);
			zeigtNurEigenes(await oeffnen('gz3020-anna', kontext), 'gz3020-anna', kontext);
		});

		test(`${kontext}: Bruno speichert nach Anna — sein Rumpf trägt nur seine Daten`, async () => {
			const anna = await oeffnen('gz3020-anna', kontext);
			anna.wetter.u.aendern({ ...anna.wetter.u.stand, tagesfenster: { start: 3, end: 22 } });
			await P.fertig(anna.ctl);
			assert.ok(gesendet.length >= 1 && gesendet.every((g) => g.nutzer === 'gz3020-anna'), 'Messaufbau: Anna hat gespeichert');
			gesendet = [];
			const bruno = await oeffnen('gz3020-bruno', kontext);
			zeigtNurEigenes(anna, 'gz3020-anna', kontext); // Brunos Laden ändert Annas Stand nicht
			bruno.wetter.u.aendern({ ...bruno.wetter.u.stand, tagesfenster: { start: 6, end: 20 } });
			await P.fertig(bruno.ctl);
			bruno.zustellung.u.aendern({ ...bruno.zustellung.u.stand, abendZeit: '20:00' });
			await P.fertig(bruno.ctl);

			assert.ok(gesendet.length >= 2, 'Messaufbau: Wetter und Zustellung haben gespeichert');
			const wetter = gesendet[0].rumpf;
			const display = kontext === 'route' ? wetter : wetter.display_config;
			assert.deepEqual(display.placements, placements('gz3020-bruno'));
			const eintraege = (kontext === 'route' ? display.metrics : display.active_metrics) as J[];
			assert.deepEqual(eintraege.filter((m) => m.besitzer).map((m) => [m.metric_id, m.besitzer]), [['gust', 'gz3020-bruno']]);
			const letzter = gesendet.at(-1)!.rumpf;
			assert.deepEqual(letzter, kontext === 'route' ? { report_config: { evening_time: '20:00:00' } } : { evening_time: '20:00:00' });
			assert.ok(gesendet.every((g) => g.nutzer === 'gz3020-bruno'));
			assert.ok(!JSON.stringify(gesendet).includes('gz3020-anna'));
		});
	});
}
