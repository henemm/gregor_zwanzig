// TDD RED — Issue #3031 (Inhalt je Kanal A1): Speichern der Kanallisten ueber den EINEN Speicherer
// des Reiters Wetter (wetterTabSpeicherung.ts), Trip und Vergleich.
// Spec: docs/specs/modules/feat_3031_inhalt_je_kanal_listen.md — Test Plan 2 (Speicherseite), 3, 4, 13
// (AC-2, AC-7, AC-8, AC-9), Implementation Details 2, 4, 11.
//
// Erwartete Schnittstelle (Erweiterung, /50 baut danach):
//   shared/wetter-tab/wetterZustand.ts
//     WetterStand.kanaele?: KanalListen        // Stand der Karte; fehlt ⇒ Karte nicht geladen
//   shared/wetter-tab/wetterTabSpeicherung.ts
//     SpeicherOptionen.kanalFormatFuer?: (id: string) => 'roh' | 'einfach'   // Format neuer Zeilen
//     tripNutzlast(o).weatherConfig  = { ampel, metrics, channel_layouts }   // channel_layouts nur mit stand.kanaele
//     vergleichNutzlast(o).display_config = { ampel, active_metrics, channel_layouts, channel_active_metrics }
//   Beim Speichern werden die Listen gegen die AKTUELLE Wetter-Auswahl normalisiert
//   (kanalInhalt.normalisiereZeilen): neue Metrik eingeschaltet ans Ende, abgewaehlte faellt weg.
//   Gesendet wird IMMER der volle Stand aller drei Listen (Go ersetzt den Schluessel als Ganzes),
//   keine fremden display_config-Schluessel (Teilfeld-Nutzlast).
//   KanalListen/Adapter: organisms/wetter-tab/kanalInhalt.ts (siehe kanal_inhalt_3031_modell.test.ts).
//
// Gemessen dort, wo es WIRKT:
//   - Trip: Nutzlast → Go-Merge (`mergeConfigMap`) → ECHTE Python-Kaskade (`load_trip` +
//     `get_metrics_for_channel`, Orakel aus kanalInhaltPruefstand.ts) und → Adapter lesen (Neuladen).
//   - Vergleich: echter Speicherer + echte Hub-Schlange + echtes `api` (ETag/If-Match) gegen den
//     Go-Merge-Pruefserver; 412 ⇒ Neuladen, fremder Stand bleibt. Die Vergleichs-Renderer-Wirkung
//     gehoert zu #3039 (hier nicht geprueft).
// Keine Mocks.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/kanal_inhalt_3031_speicherung.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createPutQueue } from '../../../compare/compareHubPersistenz.ts';
import { createController } from '../../__tests__/versandVergleichPruefstand.ts';
import { createGoMergeServer, vollerVergleich, type GoMergeServer } from '../../__tests__/goMergeServerPruefstand.ts';
import { fixture, live } from './wetterTabDaten.ts';
import { aktivId, formatAusKatalog, goMergeDisplayConfig, kanalInhalt, pythonKanalStand, type OrakelZeile } from './kanalInhaltPruefstand.ts';
import { vorlagenAusTemplates } from '../ampelModell.ts';
import { mitMetrik, ohneMetrik, standAusAbo, type AboSicht, type WetterStand } from '../wetterZustand.ts';
import { SPEICHERER, tripNutzlast, type SpeicherOptionen } from '../wetterTabSpeicherung.ts';

type Zeile = { id: string; enabled: boolean; format: 'roh' | 'einfach' };
type Listen = Record<'email' | 'telegram' | 'sms', Zeile[]>;
type Dc = Record<string, unknown>;
const LK = ['email', 'telegram', 'sms'] as const;
const an = (z: Zeile[]) => z.filter((x) => x.enabled).map((x) => x.id);
const fmt = (id: string) => formatAusKatalog(id);
const vorlagen = vorlagenAusTemplates(live().templates);
const sortiert = (a: string[]) => [...a].sort();

/** Neue Reihenfolge: letzte eingeschaltete Zeile nach vorn (echte Umsortierung, nie No-Op). */
function umsortiert(z: Zeile[]): string[] {
	const ids = z.map((x) => x.id);
	const letzte = an(z).at(-1)!;
	return [letzte, ...ids.filter((i) => i !== letzte)];
}

// ═══════════════════════════════ Trip ═══════════════════════════════════════

/** Trip-Bestand: golden_b (echtes Editor-Persistenzformat) plus fremde display_config-Schluessel. */
function tripAbo(): AboSicht {
	const g = fixture('einstellung_auslieferung/golden_b.json');
	return {
		id: 'trip-3031',
		profil: 'wandern',
		report_config: g.report_config,
		display_config: {
			...g.display_config,
			telegram_kurzform: true,
			show_night_block: false,
			outlook_metric_formats: { temperature: true },
			preset_name: 'wandern'
		}
	};
}

async function tripAufbau() {
	const m = await kanalInhalt();
	const abo = tripAbo();
	const stand = standAusAbo('route', abo, vorlagen);
	const listen: Listen = m.listenAusAbo('route', abo, stand.auswahl, fmt);
	const speichern = (s: WetterStand) => {
		const optionen: SpeicherOptionen & { kanalFormatFuer: (id: string) => 'roh' | 'einfach' } = {
			client: null as never,
			stand: () => s,
			vorlagen: () => vorlagen,
			abo: () => abo,
			kanalFormatFuer: fmt
		};
		return tripNutzlast(optionen);
	};
	const nachMerge = (s: WetterStand): Dc => goMergeDisplayConfig(abo.display_config, speichern(s).weatherConfig);
	return { m, abo, stand, listen, speichern, nachMerge };
}

describe('Test 3 (Trip): Aenderung in einem Kanal ⇒ voller channel_layouts-Stand, uebrige Schluessel unangetastet', () => {
	test('Nutzlast /weather-config: genau ampel + metrics + channel_layouts; alle drei Listen vollstaendig', async () => {
		const { m, stand, listen, speichern } = await tripAufbau();
		const neu = m.mitReihenfolge(listen, 'email', umsortiert(listen.email));
		const wc = speichern({ ...stand, kanaele: neu } as WetterStand).weatherConfig as Dc;
		assert.deepEqual(sortiert(Object.keys(wc)), ['ampel', 'channel_layouts', 'metrics'], 'der Reiter Wetter sendet fremde display_config-Schluessel bzw. keine Kanallisten');
		const cl = wc.channel_layouts as Record<string, { metric_id: string }[]>;
		for (const k of LK) {
			assert.ok(Array.isArray(cl?.[k]), `channel_layouts.${k} fehlt — Go ersetzt den Schluessel als Ganzes, der Kanal ginge verloren`);
			assert.deepEqual(sortiert(cl[k].map((e) => e.metric_id)), sortiert(stand.auswahl), `${k}: nicht der volle Listenstand`);
		}
	});

	test('nach Go-Merge: alle uebrigen display_config-Schluessel byte-gleich', async () => {
		const { m, abo, stand, listen, nachMerge } = await tripAufbau();
		const dc = nachMerge({ ...stand, kanaele: m.mitReihenfolge(listen, 'email', umsortiert(listen.email)) } as WetterStand);
		for (const [k, v] of Object.entries(abo.display_config as Dc)) {
			if (['ampel', 'metrics', 'channel_layouts'].includes(k)) continue;
			assert.deepEqual(dc[k], v, `display_config.${k} veraendert`);
		}
	});

	test('Wirkung: E-Mail-Reihenfolge geaendert, Telegram und SMS liefern exakt wie vorher (Python-Kaskade)', async () => {
		const { m, stand, listen, nachMerge } = await tripAufbau();
		const vorher = pythonKanalStand(nachMerge({ ...stand, kanaele: listen } as WetterStand));
		const neu = m.mitReihenfolge(listen, 'email', umsortiert(listen.email));
		const nachher = pythonKanalStand(nachMerge({ ...stand, kanaele: neu } as WetterStand));
		assert.deepEqual(nachher.email.map((o: OrakelZeile) => o[0]), an(neu.email), 'E-Mail liefert nicht die neue Reihenfolge');
		assert.deepEqual(nachher.telegram, vorher.telegram, 'Telegram durch eine E-Mail-Aenderung veraendert');
		assert.deepEqual(nachher.sms, vorher.sms, 'SMS durch eine E-Mail-Aenderung veraendert');
	});

	test('Bestandsschutz: Karte nicht geladen (kein stand.kanaele) ⇒ kein channel_layouts in der Nutzlast', async () => {
		const { stand, speichern } = await tripAufbau();
		const wc = speichern({ ...stand, kanaele: undefined } as WetterStand).weatherConfig as Dc;
		assert.ok(!('channel_layouts' in wc), 'ohne geladene Karte wuerde ein leerer/erfundener Stand die Listen ueberschreiben');
	});
});

describe('Test 2 (Trip, Speicherseite): neue Metrik am Ende jeder Liste, Abwahl in allen Listen', () => {
	test('„Luftdruck" im Reiter Wetter eingeschaltet ⇒ in jeder Liste eingeschaltet am Ende; Renderer liefern ihn in allen Kanaelen', async () => {
		const { stand, listen, speichern, nachMerge } = await tripAufbau();
		assert.ok(!stand.auswahl.includes('pressure'), 'Messaufbau: pressure ist schon gewaehlt');
		const s = { ...mitMetrik(stand, 'pressure'), kanaele: listen } as WetterStand;
		const cl = (speichern(s).weatherConfig as Dc).channel_layouts as Record<string, Record<string, unknown>[]>;
		for (const k of LK) {
			assert.equal(cl?.[k]?.at(-1)?.metric_id, 'pressure', `${k}: neue Metrik nicht am Ende`);
			assert.equal(cl[k].at(-1)!.enabled, true, `${k}: neue Metrik nicht eingeschaltet`);
		}
		const orakel = pythonKanalStand(nachMerge(s));
		for (const k of LK) assert.equal(orakel[k].at(-1)?.[0], 'pressure', `${k}: Renderer liefern den neuen Luftdruck nicht (am Ende)`);
	});

	test('Boeen im Reiter Wetter abgewaehlt ⇒ in keiner Liste mehr, in keinem Kanal ausgeliefert', async () => {
		const { stand, listen, speichern, nachMerge } = await tripAufbau();
		assert.ok(stand.auswahl.includes('gust'), 'Messaufbau: gust muss gewaehlt sein');
		const s = { ...ohneMetrik(stand, 'gust'), kanaele: listen } as WetterStand;
		const cl = (speichern(s).weatherConfig as Dc).channel_layouts as Record<string, { metric_id: string }[]>;
		for (const k of LK) assert.ok(!cl[k].some((e) => e.metric_id === 'gust'), `${k}: abgewaehlte Boeen noch in der Liste`);
		const orakel = pythonKanalStand(nachMerge(s));
		for (const k of LK) assert.ok(!orakel[k].some((o: OrakelZeile) => o[0] === 'gust'), `${k}: Boeen trotz Abwahl ausgeliefert`);
	});
});

describe('Test 13 (Trip, AC-2): Telegram umsortiert, gespeichert, neu geladen ⇒ E-Mail Zeile fuer Zeile unveraendert', () => {
	test('Rundlauf Speichern → Go-Merge → Neuladen (Adapter) und Wirkung (Python)', async () => {
		const { m, stand, listen, nachMerge } = await tripAufbau();
		const reihenfolge = umsortiert(listen.telegram);
		const neu = m.mitReihenfolge(listen, 'telegram', reihenfolge);
		const dc = nachMerge({ ...stand, kanaele: neu } as WetterStand);
		const geladen: Listen = m.listenAusAbo('route', { display_config: dc }, stand.auswahl, fmt);
		assert.deepEqual(geladen.telegram.map((z) => z.id), reihenfolge, 'Telegram zeigt nach Neuladen nicht die neue Reihenfolge');
		assert.deepEqual(geladen.email, listen.email, 'E-Mail-Liste nach Neuladen nicht Zeile fuer Zeile gleich');
		assert.deepEqual(geladen.sms, listen.sms, 'SMS-Liste nach Neuladen veraendert');
		const vorher = pythonKanalStand(nachMerge({ ...stand, kanaele: listen } as WetterStand));
		const orakel = pythonKanalStand(dc);
		assert.deepEqual(orakel.telegram.map((o: OrakelZeile) => o[0]), an(neu.telegram), 'Telegram liefert nicht die neue Reihenfolge');
		assert.deepEqual(orakel.email, vorher.email, 'E-Mail liefert anders als vorher');
	});

	test('Aus-Zeile und Roh/Einfach ueberleben den Rundlauf (SMS Boeen aus, E-Mail Boeen Einfach, Telegram Boeen Roh)', async () => {
		const { m, stand, listen, nachMerge } = await tripAufbau();
		let neu = m.mitSchalter(listen, 'sms', 'gust', false);
		neu = m.mitFormat(neu, 'email', 'gust', 'einfach');
		neu = m.mitFormat(neu, 'telegram', 'gust', 'roh');
		const dc = nachMerge({ ...stand, kanaele: neu } as WetterStand);
		const geladen: Listen = m.listenAusAbo('route', { display_config: dc }, stand.auswahl, fmt);
		assert.deepEqual(geladen, neu, 'Stand nach Neuladen weicht ab');
		const pos = listen.sms.findIndex((z) => z.id === 'gust');
		assert.deepEqual(geladen.sms[pos], { ...listen.sms[pos], enabled: false }, 'Aus-Zeile hat ihre Position verloren');
		const orakel = pythonKanalStand(dc);
		assert.ok(!orakel.sms.some((o: OrakelZeile) => o[0] === 'gust'), 'Boeen trotz Aus in der SMS ausgeliefert');
		assert.deepEqual(orakel.email.find((o: OrakelZeile) => o[0] === 'gust'), ['gust', true], 'E-Mail Boeen nicht Einfach');
		assert.deepEqual(orakel.telegram.find((o: OrakelZeile) => o[0] === 'gust'), ['gust', false], 'Telegram Boeen nicht Roh');
	});
});

// ═══════════════════════════════ Vergleich ══════════════════════════════════

const ID = 'cp-3031';
const PFAD = `/api/compare/presets/${ID}`;

/** Voller Vergleich (jedes Feld belegt) mit Kanallisten in der neuen Form (#3039). */
function vergleichAbo(): Record<string, unknown> {
	const v = vollerVergleich(ID);
	const dc = v.display_config as Dc;
	dc.active_metrics = ['temperature', 'wind', 'gust', 'precipitation'].map((metric_id) => ({ metric_id, aggregation: 'max' }));
	dc.ampel = { template: 'allgemein' };
	const z = (metric_id: string, enabled = true, use_friendly_format = false) => ({ metric_id, enabled, use_friendly_format });
	dc.channel_layouts = {
		email: [z('temperature'), z('wind'), z('gust', true, true), z('precipitation')],
		telegram: [z('gust'), z('temperature'), z('wind'), z('precipitation', false)],
		sms: [z('temperature'), z('precipitation'), z('wind', false), z('gust')]
	};
	return v;
}

describe('Test 3/4/13 (Vergleich): EIN PUT in der Hub-Schlange mit vollem Stand, channel_active_metrics, 412 ⇒ Neuladen', () => {
	let server: GoMergeServer;
	beforeEach(async () => {
		clearEtagRegistry();
		server = createGoMergeServer({ [ID]: vergleichAbo() });
		server.install();
		await api.get(PFAD);
	});
	afterEach(() => server.restore());

	async function reiter() {
		const m = await kanalInhalt();
		let seite = vergleichAbo() as AboSicht;
		let stand: WetterStand = standAusAbo('vergleich', seite, vorlagen);
		const listen: Listen = m.listenAusAbo('vergleich', seite, stand.auswahl, fmt);
		stand = { ...stand, kanaele: listen } as WetterStand;
		const ctl = createController(ID);
		const queue = createPutQueue();
		const neuGeladen: AboSicht[] = [];
		// `kanalFormatFuer` ist die neue Option (Kopfkommentar); bis /50 sie anlegt, traegt der Test sie selbst.
		const optionen: SpeicherOptionen & { kanalFormatFuer: (id: string) => 'roh' | 'einfach' } = {
			client: api,
			stand: () => stand,
			vorlagen: () => vorlagen,
			abo: () => seite,
			saveController: ctl,
			enqueueHubWrite: (fn) => queue.enqueue(fn),
			uebernehmen: (a) => {
				seite = a as AboSicht;
			},
			neuGeladen: (a) => {
				neuGeladen.push(a);
			},
			kanalFormatFuer: fmt
		};
		const sp = SPEICHERER.vergleich(optionen);
		return {
			m,
			listen,
			ctl,
			neuGeladen,
			get stand() {
				return stand;
			},
			aendern(neu: Listen) {
				stand = { ...stand, kanaele: neu } as WetterStand;
				sp.melden();
			}
		};
	}
	const puts = () => server.mitschnitt.filter((e) => e.method === 'PUT');

	test('Test 3: Umsortieren in E-Mail ⇒ Rumpf display_config = ampel + active_metrics + channel_layouts + channel_active_metrics, alle drei Listen', async () => {
		const r = await reiter();
		r.aendern(r.m.mitReihenfolge(r.listen, 'email', umsortiert(r.listen.email)));
		await r.ctl.flush();
		assert.equal(puts().length, 1);
		const dc = (puts()[0].anfrage as Dc).display_config as Dc;
		assert.deepEqual(sortiert(Object.keys(dc)), ['active_metrics', 'ampel', 'channel_active_metrics', 'channel_layouts']);
		const cl = dc.channel_layouts as Record<string, unknown[]>;
		for (const k of LK) assert.equal(cl?.[k]?.length, 4, `channel_layouts.${k} nicht vollstaendig`);
	});

	test('Test 3: nach dem Speichern sind die uebrigen display_config-Schluessel auf dem Server unveraendert', async () => {
		const r = await reiter();
		const vorher = server.stand(ID).display_config as Dc;
		r.aendern(r.m.mitReihenfolge(r.listen, 'email', umsortiert(r.listen.email)));
		await r.ctl.flush();
		const nachher = server.stand(ID).display_config as Dc;
		for (const [k, v] of Object.entries(vorher)) {
			if (['ampel', 'active_metrics', 'channel_layouts', 'channel_active_metrics'].includes(k)) continue;
			assert.deepEqual(nachher[k], v, `display_config.${k} veraendert`);
		}
	});

	test('Test 4: channel_active_metrics = nur eingeschaltete Kennungen in Listenreihenfolge, je Kanal', async () => {
		const r = await reiter();
		const neu = r.m.mitSchalter(r.listen, 'sms', 'gust', false);
		r.aendern(neu);
		await r.ctl.flush();
		const dc = (puts()[0].anfrage as Dc).display_config as Dc;
		const cam = dc.channel_active_metrics as Record<string, unknown[]>;
		for (const k of LK) assert.deepEqual(cam?.[k]?.map(aktivId), an(neu[k]), `channel_active_metrics.${k}`);
	});

	test('Test 4: 412 ⇒ neu laden, fremder Kanal-Stand bleibt auf dem Server, Controller meldet Konflikt', async () => {
		const r = await reiter();
		const fremd = { email: [{ metric_id: 'wind', enabled: true, use_friendly_format: false }], telegram: [], sms: [] };
		server.fremdSchreiben(ID, { display_config: { channel_layouts: fremd } });
		r.aendern(r.m.mitReihenfolge(r.listen, 'telegram', umsortiert(r.listen.telegram)));
		await r.ctl.flush();
		assert.equal(puts().length, 1);
		assert.equal(puts()[0].status, 412, 'Messaufbau: veralteter Stand muss abgelehnt werden');
		assert.ok('channel_layouts' in (((puts()[0].anfrage as Dc).display_config as Dc) ?? {}), 'der Speicherer sendet die Kanallisten gar nicht');
		assert.equal(r.neuGeladen.length, 1, 'nach 412 nicht neu geladen');
		assert.deepEqual((server.stand(ID).display_config as Dc).channel_layouts, fremd, 'fremder Stand still ueberschrieben');
		assert.equal(r.ctl.state, 'conflict');
	});

	test('Test 13 (Vergleich): Telegram umsortiert, gespeichert, neu geladen ⇒ Telegram neu, E-Mail Zeile fuer Zeile gleich', async () => {
		const r = await reiter();
		const reihenfolge = umsortiert(r.listen.telegram);
		r.aendern(r.m.mitReihenfolge(r.listen, 'telegram', reihenfolge));
		await r.ctl.flush();
		assert.equal(puts()[0]?.status, 200);
		const geladen: Listen = r.m.listenAusAbo('vergleich', server.stand(ID) as AboSicht, r.stand.auswahl, fmt);
		assert.deepEqual(geladen.telegram.map((z) => z.id), reihenfolge);
		assert.deepEqual(geladen.email, r.listen.email, 'E-Mail-Liste nicht Zeile fuer Zeile gleich');
		assert.deepEqual(geladen.sms, r.listen.sms, 'SMS-Liste veraendert');
	});
});
