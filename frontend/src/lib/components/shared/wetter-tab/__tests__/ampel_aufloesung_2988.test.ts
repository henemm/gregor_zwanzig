// #2988 S3: Abfrage der aufgeloesten Ampel (`ampelAufloesung.ts`) – Pfad, Rumpf, Pakete, Fehler.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md (AC-9, AC-10). Antworten aus echtem Python.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { AUFLOESUNG, aufgeloestVon, echterPost, funktion, json, modul, pythonAufloesung, refVorlagen, referenzLaden, sollAmpel, tick, type Json } from './laden2988.ts';

const DATEI = 'ampelAufloesung.ts';
const R = referenzLaden();
const loese = async (client: Json, eintraege: Json[]): Promise<Json[]> => (await funktion(DATEI, 'loeseAmpelnAuf'))(client, eintraege);
const ausAbo = async (abo: Json): Promise<Json> => (await funktion(DATEI, 'eintragAusAbo'))(abo);
const ausVorlage = async (p: Json): Promise<Json> => (await funktion(DATEI, 'eintragAusVorlage'))(p);

/** n unterscheidbare Eintraege (Vorlage wechselnd, Boeen-Grenze = Nummer). */
const eintraege = (n: number): Json[] =>
	Array.from({ length: n }, (_, i) => ({
		ampel: { template: Object.keys(refVorlagen())[i % 7], metrics: { gust: { lower: null, upper: { yellow: i + 1 } } } },
		preset_name: null,
		profil: null
	}));

function client(antwort: (rumpf: Json, nr: number) => Promise<Json> = (rumpf) => echterPost(AUFLOESUNG, rumpf)) {
	const aufrufe: { pfad: string; rumpf: Json }[] = [];
	return {
		aufrufe,
		post: async (pfad: string, rumpf: Json) => {
			aufrufe.push({ pfad, rumpf: json(rumpf) });
			return antwort(rumpf, aufrufe.length);
		}
	};
}

const PAKETE: [number, number[]][] = [
	[0, []],
	[1, [1]],
	[32, [32]],
	[33, [32, 1]],
	[70, [32, 32, 6]]
];

describe('#2988 S3: loeseAmpelnAuf – Pfad, Rumpf, Pakete', () => {
	for (const [n, pakete] of PAKETE) {
		test(`${n}_eintraege_ergeben_${pakete.length}_aufrufe_in_reihenfolge`, async () => {
			const liste = eintraege(n);
			const c = client();
			const erg = await loese(c, liste);
			assert.deepEqual(c.aufrufe.map((a) => a.pfad), pakete.map(() => AUFLOESUNG));
			assert.deepEqual(c.aufrufe.map((a) => Object.keys(a.rumpf)), pakete.map(() => ['eintraege']));
			assert.deepEqual(c.aufrufe.map((a) => a.rumpf.eintraege.length), pakete);
			assert.deepEqual(c.aufrufe.flatMap((a) => a.rumpf.eintraege), liste, 'Eintraege verändert oder vertauscht');
			assert.deepEqual(json(erg), pythonAufloesung(liste), 'Ergebnis nicht in Reihenfolge der Eintraege');
			assert.deepEqual(liste, eintraege(n), 'Eingabe verändert');
		});
	}
	test('reihenfolge_bleibt_wenn_das_erste_paket_spaeter_antwortet', async () => {
		const liste = eintraege(33);
		const c = client(async (rumpf, nr) => {
			if (nr === 1) await tick(30);
			return echterPost(AUFLOESUNG, rumpf);
		});
		const erg = json(await loese(c, liste));
		assert.deepEqual(erg.map((e: Json) => e.ampel.metrics.gust.upper.yellow), liste.map((_, i) => i + 1));
	});
});

describe('#2988 S3: loeseAmpelnAuf wirft bei jedem Fehler', () => {
	const gut = () => pythonAufloesung(eintraege(2));
	const zweiter = (neu: Json) => ({ ergebnisse: [gut()[0], neu] });
	const ohne = (weg: string) => zweiter(Object.fromEntries(Object.entries(gut()[1]).filter(([k]) => k !== weg)));
	const UNBRAUCHBAR: Record<string, () => Json> = {
		antwort_null: () => null,
		antwort_undefined: () => undefined,
		antwort_text: () => 'kaputt',
		antwort_liste: () => gut(),
		ergebnisse_fehlt: () => ({}),
		ergebnisse_null: () => ({ ergebnisse: null }),
		ergebnisse_objekt: () => ({ ergebnisse: { 0: gut()[0], 1: gut()[1], length: 2 } }),
		ergebnisse_leer: () => ({ ergebnisse: [] }),
		ergebnisse_zu_kurz: () => ({ ergebnisse: gut().slice(0, 1) }),
		ergebnisse_zu_lang: () => ({ ergebnisse: [...gut(), gut()[0]] }),
		eintrag_null: () => zweiter(null),
		eintrag_text: () => zweiter('x'),
		vorlage_id_fehlt: () => ohne('vorlage_id'),
		vorlage_id_null: () => zweiter({ ...gut()[1], vorlage_id: null }),
		vorlage_id_leer: () => zweiter({ ...gut()[1], vorlage_id: '' }),
		ampel_fehlt: () => ohne('ampel'),
		ampel_null: () => zweiter({ ...gut()[1], ampel: null }),
		ampel_ohne_metrics: () => zweiter({ ...gut()[1], ampel: { template: 'wandern', thunder: {} } }),
		ampel_metrics_null: () => zweiter({ ...gut()[1], ampel: { template: 'wandern', metrics: null, thunder: {} } })
	};
	for (const [name, antwort] of Object.entries(UNBRAUCHBAR)) {
		test(`unbrauchbar_${name}`, async () => {
			const f = await funktion(DATEI, 'loeseAmpelnAuf');
			await assert.rejects(async () => f(client(async () => antwort()), eintraege(2)));
		});
	}
	test('client_fehler_wird_weitergeworfen', async () => {
		const f = await funktion(DATEI, 'loeseAmpelnAuf');
		await assert.rejects(
			async () => f(client(() => Promise.reject({ status: 503, error: 'kaputt' })), eintraege(1)),
			(e) => (e as Json)?.status === 503
		);
	});
	test('ein_gescheitertes_paket_laesst_alles_scheitern', async () => {
		const f = await funktion(DATEI, 'loeseAmpelnAuf');
		const c = client(async (rumpf) => {
			if (rumpf.eintraege.length === 1) throw new Error('zweites Paket');
			return echterPost(AUFLOESUNG, rumpf);
		});
		await assert.rejects(async () => f(c, eintraege(33)), /zweites Paket/);
	});
	test('laenge_wird_je_paket_geprueft_nicht_nur_in_summe', async () => {
		const f = await funktion(DATEI, 'loeseAmpelnAuf');
		const c = client(async (rumpf) => {
			const { ergebnisse } = await echterPost(AUFLOESUNG, rumpf);
			return { ergebnisse: rumpf.eintraege.length === 32 ? ergebnisse.slice(1) : [...ergebnisse, ...ergebnisse] };
		});
		await assert.rejects(async () => f(c, eintraege(33)));
	});
});

describe('#2988 S3: eintragAusAbo', () => {
	const LEER = { ampel: null, preset_name: null, profil: null };
	const OHNE: [string, Json][] = [
		['null', null],
		['undefined', undefined],
		['leer', {}],
		['display_config_null', { display_config: null }]
	];
	for (const [name, abo] of OHNE) {
		test(`ohne_angaben_alles_null_${name}`, async () => {
			assert.deepEqual(await ausAbo(abo), LEER);
		});
	}
	test('drei_felder_von_ihrer_stelle_am_abo', async () => {
		const ampel = { template: 'wandern', metrics: { gust: { alarm_ab: 'red' } } };
		const abo = { ampel: { template: 'x' }, preset_name: 'x', profil: 'wintersport', display_config: { ampel, preset_name: 'radtour', profil: 'x' } };
		assert.deepEqual(await ausAbo(abo), { ampel, preset_name: 'radtour', profil: 'wintersport' });
	});
	for (const wert of [7, 0, true, null, ['wandern'], { a: 1 }]) {
		test(`nicht_text_wird_null_${JSON.stringify(wert)}`, async () => {
			const e = await ausAbo({ profil: wert, display_config: { preset_name: wert } });
			assert.deepEqual(e, LEER);
			assert.equal(pythonAufloesung([e])[0].vorlage_id, 'allgemein');
		});
	}
	for (const liste of [[{ metric_id: 'gust', enabled: true }], [], ['gust']] as Json[]) {
		test(`nie_metrics_${JSON.stringify(liste)}`, async () => {
			const e = await ausAbo({ metrics: liste, display_config: { preset_name: 'wandern', metrics: liste, active_metrics: liste } });
			assert.deepEqual(e, { ampel: null, preset_name: 'wandern', profil: null });
			assert.equal(pythonAufloesung([e])[0].vorlage_id, 'wandern', 'als Altbestand einer eigenen Vorlage gelesen');
		});
	}
	test('referenz_abos_ergeben_dieselbe_aufloesung_wie_vor_dem_umbau', async () => {
		const liste: Json[] = [];
		for (const f of R.abos) liste.push(await ausAbo(f.abo));
		const erg = pythonAufloesung(liste);
		R.abos.forEach((f: Json, i: number) => {
			assert.equal(erg[i].vorlage_id, f.soll.vorlageId, f.name);
			assert.deepEqual(erg[i].ampel, sollAmpel(f.soll), f.name);
			assert.deepEqual(erg[i], aufgeloestVon(f.abo), f.name);
		});
	});
	test('abo_bleibt_unveraendert', async () => {
		for (const f of R.abos) {
			const abo = structuredClone(f.abo);
			await ausAbo(abo);
			assert.deepEqual(abo, f.abo, f.name);
		}
	});
});

describe('#2988 S3: eintragAusVorlage', () => {
	const basis = { id: 'ev', name: 'Meine', is_default: false, created_at: '2026-01-01T00:00:00Z', kind: 'route' };
	const an = (aufgeloest: Json): string[] => Object.entries(aufgeloest.ampel.metrics).filter(([, z]) => (z as Json).enabled).map(([id]) => id);
	test('mit_ampel_nur_die_ampel', async () => {
		const ampel = { template: 'wandern', metrics: { gust: { alarm_ab: 'red' } } };
		const p = { ...basis, preset_name: 'x', profil: 'x', ampel, metrics: [{ metric_id: 'wind', enabled: true, use_friendly_format: true }] };
		assert.deepEqual(json(await ausVorlage(p)), { ampel });
	});
	test('leere_ampel_ist_abo_sicht', async () => {
		assert.deepEqual(json(await ausVorlage({ ...basis, ampel: {}, metrics: [{ metric_id: 'wind', enabled: true }] })), { ampel: {} });
	});
	for (const ampel of [null, undefined]) {
		test(`ohne_ampel_je_zeile_genau_metric_id_und_enabled_${ampel}`, async () => {
			const metrics = [
				{ metric_id: 'gust', enabled: true, use_friendly_format: true, horizons: { today: true } },
				{ metric_id: 'wind', enabled: false, use_friendly_format: false }
			];
			assert.deepEqual(json(await ausVorlage({ ...basis, ampel, metrics })), {
				metrics: [
					{ metric_id: 'gust', enabled: true },
					{ metric_id: 'wind', enabled: false }
				]
			});
		});
	}
	const LISTEN: [string, Json][] = [
		['fehlt', {}],
		['null', { metrics: null }],
		['text', { metrics: 'gust' }],
		['objekt', { metrics: { gust: true } }]
	];
	for (const [name, rest] of LISTEN) {
		test(`unlesbare_liste_wird_leer_${name}`, async () => {
			const e = json(await ausVorlage({ ...basis, ...rest }));
			assert.deepEqual(e, { metrics: [] });
			assert.deepEqual(an(pythonAufloesung([e])[0]), [], 'ohne Liste ist heute alles aus');
		});
	}
	test('unlesbare_zeilen_werfen_nicht_und_zaehlen_nicht', async () => {
		const e = json(await ausVorlage({ ...basis, metrics: [null, 'gust', 7, {}, { metric_id: 'wind', enabled: true }] }));
		assert.deepEqual(an(pythonAufloesung([e])[0]), ['wind']);
	});
	for (const f of R.eigene) {
		test(`gleich_referenz_${f.name}`, async () => {
			const preset = structuredClone(f.preset);
			const erg = pythonAufloesung([json(await ausVorlage(preset))])[0];
			assert.equal(erg.vorlage_id, f.soll.vorlageId);
			assert.deepEqual(erg.ampel, sollAmpel(f.soll));
			assert.deepEqual(preset, f.preset, 'Vorlage verändert');
		});
	}
});

describe('#2988 S3: ein volles Paket bleibt unter der Grenze', () => {
	// Je Vorlage alle Groessen des Katalogs, alle sechs Grenzen gesetzt: mehr kann der Reiter nicht speichern.
	test('32_vollstaendige_vorlagen_ampeln_unter_256_kib', async () => {
		await modul(DATEI);
		const ampeln = Object.values(refVorlagen()) as Json[];
		const zeile = { enabled: true, lower: { red: -1000.5, orange: -900.5, yellow: -800.5 }, upper: { yellow: 8000.5, orange: 9000.5, red: 10000.5 }, alarm_ab: 'orange' };
		const ids = [...new Set(ampeln.flatMap((a) => Object.keys(a.metrics)))];
		const voll = { template: 'alpen-trekking', metrics: Object.fromEntries(ids.map((id) => [id, zeile])), thunder: { mittel: 'orange', hoch: 'orange' } };
		const liste: Json[] = [];
		for (let i = 0; i < 32; i++) liste.push(await ausVorlage({ id: `v${i}`, name: 'V', is_default: false, created_at: '', metrics: [], ampel: voll }));
		const c = client();
		await loese(c, liste);
		assert.deepEqual(c.aufrufe.map((a) => a.rumpf.eintraege.length), [32], 'ein Paket');
		const bytes = Buffer.byteLength(JSON.stringify(c.aufrufe[0].rumpf), 'utf-8');
		assert.ok(bytes > 32 * 1000, `Messaufbau: Rumpf zu klein (${bytes})`);
		assert.ok(bytes < 256 * 1024, `${bytes} Byte`);
	});
});
