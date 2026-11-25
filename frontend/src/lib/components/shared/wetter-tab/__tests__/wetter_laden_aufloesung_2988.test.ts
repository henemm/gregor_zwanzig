// #2988 S3, AC-9: der Reiter zeigt die vom Server aufgeloeste Ampel, gleich dem Stand vor dem Umbau.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md. Referenz aus dem Altbaum:
// tests/fixtures/ampel_laden_referenz_2988.json; Aufloesung aus echtem Python.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { AUFLOESUNG, KONTEXTE, aufgeloestVon, echterPost, funktion, json, modul, oeffne, pythonAufloesung, refVorlagen, referenzLaden, sollAmpel, type Json } from './laden2988.ts';
import { live, liveVergleichsKatalog } from './wetterTabDaten.ts';
import { toCompareSelectionEntries } from '../../weather-metrics-tab/compareMetricSelection.ts';
import type { Kontext } from '../ampelModell.ts';

const R = referenzLaden();
const text = (x: Json): string | null => (typeof x === 'string' ? x : null);
const eintrag = (abo: Json): Json => ({ ampel: abo.display_config?.ampel ?? null, preset_name: text(abo.display_config?.preset_name), profil: text(abo.profil) });
let warm = false;
/** Alle Referenz-Abos in EINEM Python-Lauf. */
function vorwaermen(): void {
	if (!warm) pythonAufloesung(R.abos.map((f: Json) => eintrag(f.abo)));
	warm = true;
}

/** Altschluessel wie im Reiter: nur der Vergleich laedt den Vergleichs-Katalog. */
async function altSchluessel(context: Kontext): Promise<Json> {
	if (context === 'route') return {};
	return (await funktion('ampelModell.ts', 'altSchluesselAusKatalog'))(toCompareSelectionEntries(liveVergleichsKatalog()));
}

/** Lese-Client mit zaehlendem post. */
function client(presets: Json = []) {
	const posts: { pfad: string; rumpf: Json }[] = [];
	const daten: Json = { '/api/metrics': live().metrics, '/api/templates': live().templates, '/api/metric-presets': presets };
	return {
		posts,
		get: async (pfad: string) => {
			assert.ok(pfad in daten, `unerwartet: GET ${pfad}`);
			return structuredClone(daten[pfad]);
		},
		post: async (pfad: string, rumpf: Json) => {
			posts.push({ pfad, rumpf: json(rumpf) });
			return echterPost(pfad, rumpf);
		}
	};
}
async function lade(context: Kontext, abo: Json, c = client()): Promise<Json> {
	const d = await (await funktion('wetterTabLaden.ts', 'ladeWetterDaten'))(c, context, abo);
	assert.ok(d.aufgeloest, 'TDD RED: ladeWetterDaten liefert keine aufgeloeste Ampel (WetterDaten.aufgeloest)');
	return d;
}
async function standAus(context: Kontext, abo: Json, d: Json): Promise<Json> {
	const f = await funktion('wetterZustand.ts', 'standAusAbo');
	return f(context, abo, d.aufgeloest, await altSchluessel(context), { eig: d.eig });
}
const preset = (id: string, rest: Json): Json => ({ id, name: `V ${id}`, is_default: false, created_at: '2026-01-01T00:00:00Z', metrics: [], ...rest });
const ABO = { id: 'x', name: 'X', display_config: { ampel: { template: 'wandern', metrics: { gust: { alarm_ab: 'red' } } } } };
const FREMD = { id: 'y', display_config: { ampel: { template: 'skitouren', metrics: { gust: { upper: { yellow: 33 } } }, thunder: { mittel: 'red' } } } };

describe('AC-9 (#2988): geladener Stand gleich Referenz vor dem Umbau', () => {
	for (const f of R.abos) {
		test(`stand_gleich_${f.name}`, async () => {
			vorwaermen();
			const abo = structuredClone(f.abo);
			const c = client();
			const d = await lade(f.context, abo, c);
			const s = await standAus(f.context, abo, d);
			const Z = await modul('wetterZustand.ts');
			const alt = await altSchluessel(f.context);
			assert.equal(s.vorlageId, f.soll.vorlageId);
			assert.deepEqual(json(s.ampel), sollAmpel(f.soll));
			assert.deepEqual(s.auswahl, f.soll.auswahl);
			assert.equal(s.warnungenAn, f.soll.warnungenAn);
			assert.equal(s.radarAn, f.soll.radarAn);
			assert.deepEqual(s.tagesfenster, f.soll.tagesfenster);
			assert.equal(Z.abweichungenVon(s, d.vorlagen, f.context, alt), f.soll.zaehler);
			assert.deepEqual(json(Z.mengeVon(s, d.vorlagen, f.context, alt)), f.soll.menge);
			assert.deepEqual(abo, f.abo, 'Abo der Seite verändert');
			assert.deepEqual(c.posts, [{ pfad: AUFLOESUNG, rumpf: { eintraege: [eintrag(f.abo)] } }]);
		});
	}
	for (const context of KONTEXTE) {
		test(`${context}_ohne_abo_gilt_allgemein`, async () => {
			const d = await lade(context, undefined);
			const s = await standAus(context, undefined, d);
			assert.equal(s.vorlageId, 'allgemein');
			assert.deepEqual(json(s.ampel), refVorlagen().allgemein);
		});
	}
});

describe('AC-9 (#2988): eigene Vorlagen im selben Aufruf wie das Abo', () => {
	for (const context of KONTEXTE) {
		const andere = { route: 'vergleich', vergleich: 'route' }[context];
		test(`${context}_eigene_vorlagen_gleich_referenz_abo_ist_eintrag_null`, async () => {
			const liste = R.eigene.map((f: Json) => ({ ...f.preset, kind: context }));
			const c = client(liste);
			const d = await lade(context, ABO, c);
			assert.equal(c.posts.length, 1, 'nicht genau ein Aufruf');
			assert.equal(c.posts[0].pfad, AUFLOESUNG);
			assert.equal(c.posts[0].rumpf.eintraege.length, 1 + R.eigene.length);
			assert.deepEqual(c.posts[0].rumpf.eintraege[0], eintrag(ABO));
			assert.deepEqual(json(d.aufgeloest), aufgeloestVon(ABO));
			assert.deepEqual(d.eigene.map((e: Json) => e.id), liste.map((p: Json) => p.id));
			R.eigene.forEach((f: Json, i: number) => assert.deepEqual(json(d.eigene[i].ampel), sollAmpel(f.soll), f.name));
		});
		test(`${context}_nur_vorlagen_der_art_werden_angefragt`, async () => {
			const liste = [
				preset('fremd', { kind: andere, ampel: { template: 'skitouren' } }),
				preset('eigen', { kind: context, ampel: { template: 'radtour' } }),
				preset('', { kind: context, ampel: { template: 'wassersport' } }),
				preset('ohne-art', { ampel: { template: 'wintersport' } })
			];
			// Bestand ohne Art stammt aus dem Trip.
			const erwartet = { route: ['eigen', 'ohne-art'], vergleich: ['eigen'] }[context];
			const angefragt = liste.filter((p) => erwartet.includes(p.id)).map((p) => ({ ampel: p.ampel }));
			for (const antwort of [liste, { presets: liste }]) {
				const c = client(antwort);
				const d = await lade(context, ABO, c);
				assert.deepEqual(d.eigene.map((e: Json) => e.id), erwartet);
				assert.deepEqual(c.posts.map((p) => p.rumpf.eintraege), [[eintrag(ABO), ...angefragt]]);
			}
		});
		test(`${context}_felder_der_vorlage_bleiben`, async () => {
			const p = preset('eigen', { kind: context, description: 'Text', herkunft: { id: 't', name: 'GR20' }, ampel: { template: 'radtour' } });
			const [e] = (await lade(context, ABO, client([p]))).eigene;
			assert.deepEqual(json(e), { id: 'eigen', name: 'V eigen', ampel: refVorlagen().radtour, beschreibung: 'Text', herkunftName: 'GR20' });
		});
		const PAKETE: [number, number[]][] = [
			[0, [1]],
			[31, [32]],
			[32, [32, 1]],
			[40, [32, 9]]
		];
		for (const [zahl, pakete] of PAKETE) {
			test(`${context}_${zahl}_eigene_vorlagen_pakete_und_zuordnung`, async () => {
				const ids = Object.keys(refVorlagen());
				const liste = Array.from({ length: zahl }, (_, i) => preset(`v${i}`, { kind: context, ampel: { template: ids[i % 7], metrics: { gust: { lower: null, upper: { yellow: i + 1 } } } } }));
				const c = client(liste);
				const d = await lade(context, ABO, c);
				assert.deepEqual(c.posts.map((p) => p.rumpf.eintraege.length), pakete);
				assert.deepEqual(json(d.aufgeloest), aufgeloestVon(ABO));
				assert.deepEqual(
					d.eigene.map((e: Json) => [e.id, e.ampel.template, e.ampel.metrics.gust.upper.yellow]),
					liste.map((p, i) => [p.id, ids[i % 7], i + 1])
				);
			});
		}
		test(`${context}_reiter_fragt_beim_oeffnen_genau_einmal`, async () => {
			const r = await oeffne(context, structuredClone(ABO), { presets: [preset('eigen', { kind: context, ampel: { template: 'radtour' } })] });
			assert.deepEqual(r.posts().map((p) => p.pfad), [AUFLOESUNG]);
			assert.deepEqual(json(r.posts()[0].rumpf.eintraege), [eintrag(ABO), { ampel: { template: 'radtour' } }]);
			assert.deepEqual(json(r.eigene()[0].ampel), refVorlagen().radtour);
			r.eigeneUebernehmen('eigen');
			assert.equal(r.u.stand.vorlageId, 'radtour');
			assert.equal(r.posts().length, 1, 'Übernehmen fragt die Auflösung');
		});
	}
});

describe('AC-9 (#2988): der Reiter zeigt die Server-Antwort, nichts lokal Gerechnetes', () => {
	/** Antwort fuer ein anderes Abo, gleiche Laenge. */
	const vertauscht = async (pfad: string, rumpf: Json): Promise<Json> => ({ ergebnisse: (await echterPost(pfad, rumpf)).ergebnisse.map(() => aufgeloestVon(FREMD)) });
	for (const context of KONTEXTE) {
		test(`${context}_stand_folgt_der_antwort`, async () => {
			const r = await oeffne(context, structuredClone(ABO), { post: vertauscht });
			assert.equal(r.u.stand.vorlageId, 'skitouren');
			assert.deepEqual(json(r.u.stand.ampel), aufgeloestVon(FREMD).ampel);
		});
		test(`${context}_eigene_vorlage_folgt_der_antwort`, async () => {
			const r = await oeffne(context, structuredClone(ABO), { post: vertauscht, presets: [preset('eigen', { kind: context, ampel: { template: 'radtour' } })] });
			assert.deepEqual(json(r.eigene()[0].ampel), aufgeloestVon(FREMD).ampel);
		});
		test(`${context}_vorlage_id_der_antwort_gilt_auch_fuer_template`, async () => {
			const f = await funktion('wetterZustand.ts', 'standAusAbo');
			const a = aufgeloestVon(FREMD);
			const s = f(context, structuredClone(ABO), { vorlage_id: 'radtour', ampel: a.ampel }, await altSchluessel(context), {});
			assert.equal(s.vorlageId, 'radtour');
			assert.equal(s.ampel.template, 'radtour');
			assert.deepEqual(a, aufgeloestVon(FREMD), 'Antwort verändert');
		});
		test(`${context}_antwort_wird_weder_geteilt_noch_veraendert`, async () => {
			const d = await lade(context, structuredClone(ABO));
			const vorher = json(d.aufgeloest);
			const s = await standAus(context, structuredClone(ABO), d);
			for (const z of Object.values(s.ampel.metrics) as Json[]) {
				z.enabled = 'x';
				z.alarm_ab = 'x';
				z.lower.x = 1;
				z.upper.x = 1;
			}
			s.ampel.thunder.mittel = 'x';
			s.ampel.metrics.neu = {};
			assert.deepEqual(json(d.aufgeloest), vorher, 'Stand teilt Objekte mit der Antwort');
			assert.deepEqual(json((await standAus(context, structuredClone(ABO), d)).ampel), vorher.ampel);
		});
	}
});

describe('F004 (#2988): geladene Ampel ist vollständig, aboAmpelVon traegt sie', () => {
	function vollstaendig(ampel: Json, wo: string): void {
		assert.ok(Object.keys(ampel.metrics).length > 10, wo);
		for (const [id, z] of Object.entries(ampel.metrics) as [string, Json][]) {
			assert.equal(typeof z.enabled, 'boolean', `${wo} ${id}.enabled`);
			assert.equal(typeof z.alarm_ab, 'string', `${wo} ${id}.alarm_ab`);
			for (const seite of ['lower', 'upper']) assert.ok(z[seite] && typeof z[seite] === 'object', `${wo} ${id}.${seite}`);
		}
		for (const k of ['mittel', 'hoch']) assert.equal(typeof ampel.thunder[k], 'string', `${wo} thunder.${k}`);
	}
	for (const context of KONTEXTE) {
		test(`${context}_alle_vorlagen_und_altbestand`, async () => {
			vorwaermen();
			const Z = await modul('wetterZustand.ts');
			const alt = await altSchluessel(context);
			const liste = R.eigene.map((f: Json) => ({ ...f.preset, kind: context }));
			const abos = R.abos.filter((x: Json) => x.context === context);
			assert.equal(abos.filter((f: Json) => f.name.includes('|vorlage_')).length, 7, 'Messaufbau: Vorlagen');
			for (const f of abos) {
				const mitEigenen = f.name.includes('|vorlage_');
				const d = await lade(context, f.abo, client(mitEigenen ? liste : []));
				const s = await standAus(context, f.abo, d);
				vollstaendig(s.ampel, f.name);
				vollstaendig(Z.aboAmpelVon(s, d.vorlagen, context, alt), `${f.name} aboAmpelVon`);
				for (const e of d.eigene) {
					vollstaendig(e.ampel, e.id);
					const t = Z.mitEigenerVorlage(s, e.ampel, d.vorlagen, context, alt);
					vollstaendig(Z.aboAmpelVon(t, d.vorlagen, context, alt), `${e.id} aboAmpelVon`);
				}
			}
		});
	}
});

describe('F007 (#2988): mitEigenerVorlage waehlt nur Eingeschaltetes und Ausgebbares', () => {
	async function uebernommen(context: Kontext, ampel: Json, alt: Json): Promise<string[]> {
		const Z = await modul('wetterZustand.ts');
		const leer = { vorlageId: 'allgemein', ampel: {}, auswahl: [], warnungenAn: true, radarAn: false, tagesfenster: { start: 4, end: 19 } };
		return Z.mitEigenerVorlage(leer, ampel, refVorlagen(), context, alt).auswahl;
	}
	/** „allgemein“, alles aus, dann `enabled` wie angegeben. */
	function mitEnabled(werte: Json): Json {
		const a = refVorlagen().allgemein;
		for (const z of Object.values(a.metrics) as Json[]) z.enabled = false;
		for (const [id, enabled] of Object.entries(werte)) a.metrics[id] = { ...a.metrics[id], enabled };
		return a;
	}
	const gemischt = () => mitEnabled({ gust: true, temperature_night: true });
	for (const context of KONTEXTE) {
		test(`${context}_nur_enabled_genau_true`, async () => {
			const ampel = mitEnabled({ gust: true, wind: 'true', precipitation: 1, thunder: null, visibility: undefined });
			assert.deepEqual(await uebernommen(context, ampel, await altSchluessel(context)), ['gust']);
		});
	}
	test('vergleich_nicht_ausgebbare_groesse_faellt_weg', async () => {
		assert.deepEqual(await uebernommen('vergleich', gemischt(), await altSchluessel('vergleich')), ['gust']);
	});
	test('vergleich_ohne_katalog_bleibt_die_auswahl', async () => {
		assert.deepEqual((await uebernommen('vergleich', gemischt(), {})).sort(), ['gust', 'temperature_night']);
	});
	test('uebernahme_kopiert_die_ampel_der_vorlage', async () => {
		const Z = await modul('wetterZustand.ts');
		const ampel = { ...gemischt(), template: 'gibt-es-nicht' };
		const vorher = structuredClone(ampel);
		const s = Z.mitEigenerVorlage({ auswahl: [] }, ampel, refVorlagen(), 'route');
		assert.equal(s.ampel.template, 'allgemein');
		s.ampel.metrics.gust.upper.yellow = -1;
		s.ampel.thunder.mittel = 'x';
		assert.deepEqual(ampel, vorher, 'Stand teilt Objekte mit der Vorlage');
	});
	test('route_behaelt_nachtgroesse', async () => {
		assert.deepEqual((await uebernommen('route', gemischt(), {})).sort(), ['gust', 'temperature_night']);
	});
});

describe('#2988 S3: zuruecksetzen kopiert die fertige Vorlage', () => {
	const IDS = Object.keys(refVorlagen());
	test('jede_vorlage_als_tiefe_kopie_mit_ihrer_auswahl', async () => {
		const f = await funktion('ampelModell.ts', 'zuruecksetzen');
		assert.equal(IDS.length, 7);
		for (const id of IDS) {
			const vorlagen = refVorlagen();
			const r = f(id, vorlagen);
			assert.deepEqual(r.ampel, refVorlagen()[id], id);
			const aktiv = Object.entries(refVorlagen()[id].metrics).filter(([, z]) => (z as Json).enabled === true);
			assert.deepEqual(r.auswahl, aktiv.map(([m]) => m), id);
			for (const z of Object.values(r.ampel.metrics) as Json[]) {
				z.enabled = 'x';
				z.lower.x = 1;
				z.upper.x = 1;
			}
			r.ampel.thunder.mittel = 'x';
			r.ampel.metrics.neu = {};
			assert.deepEqual(vorlagen, refVorlagen(), `${id}: Vorlage geteilt`);
		}
	});
	test('unbekannte_vorlage_faellt_auf_allgemein', async () => {
		const f = await funktion('ampelModell.ts', 'zuruecksetzen');
		const vorlagen = refVorlagen();
		const r = f('gibt-es-nicht', vorlagen);
		assert.deepEqual(r.ampel, refVorlagen().allgemein);
		r.ampel.metrics.gust.upper.yellow = -1;
		assert.deepEqual(vorlagen, refVorlagen(), 'Vorlage geteilt');
	});
	for (const context of KONTEXTE) {
		test(`${context}_im_reiter_zurueck_auf_die_vorlage_ohne_aufruf`, async () => {
			const r = await oeffne(context, structuredClone(FREMD));
			assert.ok(r.zahl() > 0, 'Messaufbau: keine Abweichung');
			const n = r.aufrufe.length;
			r.zuruecksetzen();
			assert.deepEqual(json(r.u.stand.ampel), refVorlagen().skitouren);
			assert.equal(r.zahl(), 0);
			assert.equal(r.aufrufe.length, n);
		});
	}
});
