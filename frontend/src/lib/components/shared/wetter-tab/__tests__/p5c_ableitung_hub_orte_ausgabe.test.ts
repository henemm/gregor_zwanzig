// Issue #3047 Runde 7, Paket p5c: drei Nachgaenge aus p5a (AC-26, Spec feat_3047 „Nachtrag Runde 7“).
//
// 1. Kind-Groessen (Tagestief/-hoch, Nacht-Tiefst, Windchill-Kinder) aus der Vorlage: Tech-Lead-
//    Entscheidung „die Ausgabe darf sich durch den p5a-Fix nicht aendern“. Anlegen/Vorlage
//    uebernehmen/„+“ folgen der Python-Ableitung (loader._append_derived_metrics): Kinder gelten als
//    gewaehlt, wenn Python sie aus dem Elter ableitet. Nur ein bewusstes „−“ schreibt ein Kind aus.
//    Orakel „vor p5a“ = der Schreiber von 6ddf4a1: `tripMetriken([], auswahl)` schrieb fuer ein
//    neues Abo genau `auswahl.map(id => ({metric_id: id, enabled: true}))` (ohne Kind-Eintraege,
//    Python leitete sie ab).
// 2. Hub-Uebersicht: die Zahl der Uebersicht = Zahl der Ausgabe auch bei „nie eingestellt“
//    (Trip: Alarm-Zeile mit dem Register-Standard; Orte: Karte „Wetter“ mit dem Vergleichs-Katalog).
// 3. Orte „nie eingestellt“: Abwahl einer Groesse entfernt nur deren Zeilen; alle uebrigen Zeilen
//    der Vergleichstabelle (inkl. Varianten wie Temperatur-Minimum) bleiben.
//
// Kette ohne Nachbau: echte Lader (standAusAbo, mitVorlage, mitMetrik, ohneMetrik), echte
// Speicherer (tripNutzlast/vergleichNutzlast), Ebene-1-Merge wie Go, danach die ECHTEN
// Python-Resolver (ausgabeOrakel.ts). Zwei Nutzer mit verschiedenen Konfigurationen.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/p5c_ableitung_hub_orte_ausgabe.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';

import { aufloesungPost, aufgeloestVon, WETTER_TAB, live, vergleichsKatalogFetch } from './wetterTabDaten.ts';
import { umgebungFuer } from '../../__tests__/svelteInstanzPruefstand.ts';
import { ebene1, pythonAusgabe } from './ausgabeOrakel.ts';
import { alarmZaehler, altSchluesselAusKatalog, eigenschaftenAusKatalog, vorlagenAusTemplates } from '../ampelModell.ts';
import { loadCompareSelectionEntries } from '../compareMetricCatalogLoader.ts';
import * as Z from '../wetterZustand.ts';
import { tripNutzlast, vergleichNutzlast } from '../wetterTabSpeicherung.ts';
import { deriveVergleichKennzahlen, tripAlarmAbText } from '../../hub-uebersicht/hubUebersichtModell.ts';
import { tr, trn, type MessageKey } from '../../../../i18n/index.ts';

type Abo = Record<string, unknown> & { display_config?: Record<string, unknown>; report_config?: Record<string, unknown> };

const LIVE = live();
const VORLAGEN = vorlagenAusTemplates(LIVE.templates);
const EIG = eigenschaftenAusKatalog(LIVE.metrics);
const zurueck = vergleichsKatalogFetch();
const KATALOG = await loadCompareSelectionEntries();
zurueck();
const ALT = altSchluesselAusKatalog(KATALOG);
const aggregation = (id: string) => KATALOG.find((e) => e.metric_id === id)?.aggregation ?? 'max';
const ZEILE_ZU_ID: Record<string, string> = Object.fromEntries(KATALOG.map((e) => [(e as { metric?: string }).metric, e.metric_id]));
const menge = (a: string[]) => [...new Set(a)].sort();
const KINDER = ['temperature_night', 'temperature_day_low', 'temperature_day_high', 'wind_chill_night', 'wind_chill_day_low', 'wind_chill_day_high'];

// ── Trip: echter Speicherer + Ebene-1-Merge ───────────────────────────────────────────────────
function tripSpeichern(abo: Abo, s: Z.WetterStand): Abo {
	const n = tripNutzlast({ client: null as never, stand: () => s, vorlagen: () => VORLAGEN, abo: () => abo as never });
	return { display_config: ebene1(abo.display_config, n.weatherConfig as Record<string, unknown>), report_config: {} };
}
/** Was 6ddf4a1 fuer eine Auswahl ohne Bestand schrieb (Orakel „vor p5a“). */
const vorP5a = (auswahl: string[]): Abo => ({ display_config: { metrics: auswahl.map((id) => ({ metric_id: id, enabled: true })) }, report_config: {} });
const lesen = (abo: Abo) => Z.standAusAbo('route', abo as never, aufgeloestVon(abo), {}, { eig: EIG });

// Nutzer A legt aus „allgemein“ an (Vorlage ohne Kind-Groessen), Nutzer B aus „alpen-trekking“
// (Nacht-Tiefst ausdruecklich, Windchill ohne Kinder).
const ANLEGEN = ['allgemein', 'alpen-trekking'] as const;
const neu: Record<string, { stand: Z.WetterStand; gespeichert: Abo; vorher: Abo }> = {};
for (const v of ANLEGEN) {
	const abo: Abo = { display_config: { ampel: { template: v } } };
	const stand = Z.standAusAbo('route', abo as never, aufgeloestVon(abo), {}, { eig: EIG, alsVorlage: true });
	const vorlagenAuswahl = Object.entries(VORLAGEN[v].metrics ?? {}).filter(([, e]) => e?.enabled === true).map(([id]) => id);
	neu[v] = { stand, gespeichert: tripSpeichern(abo, stand), vorher: vorP5a(vorlagenAuswahl) };
}
// Nutzer A: bestehender Trip uebernimmt die Vorlage „wandern“; Nutzer B: „+ Temperatur“ auf einer Liste ohne Temperatur.
const BESTAND_A: Abo = { display_config: { metrics: [{ metric_id: 'wind', enabled: true, bucket: 'primary', order: 0 }] }, report_config: {} };
const vorlageUebernommen = Z.mitVorlage(lesen(BESTAND_A), 'wandern', VORLAGEN, 'route', {});
const BESTAND_B: Abo = {
	display_config: {
		metrics: [
			{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 0 },
			{ metric_id: 'wind_chill', enabled: false, bucket: 'primary', order: 1 }
		]
	},
	report_config: {}
};
const plusTemperatur = Z.mitMetrik(lesen(BESTAND_B), 'temperature', 'route');
const plusWindchill = Z.mitMetrik(plusTemperatur, 'wind_chill', 'route');
const vorlageAbo = tripSpeichern(BESTAND_A, vorlageUebernommen);
const plusAbo = tripSpeichern(BESTAND_B, plusWindchill);
// Bewusstes „−“ auf ein Kind nach dem Anlegen (Nutzer A).
const minusKind = Z.ohneMetrik(lesen(neu.allgemein.gespeichert), 'temperature_day_low');
const minusAbo = tripSpeichern(neu.allgemein.gespeichert, minusKind);

const AUS_VORHER_ALLGEMEIN = vorP5a(Object.entries(VORLAGEN.allgemein.metrics ?? {}).filter(([, e]) => e?.enabled === true).map(([id]) => id));
const AUS = pythonAusgabe({
	trip: {
		...Object.fromEntries(ANLEGEN.flatMap((v) => [[`${v}__neu`, neu[v].gespeichert], [`${v}__vorher`, neu[v].vorher]])),
		vorlage: vorlageAbo,
		vorlage_vorher: vorP5a(Object.entries(VORLAGEN.wandern.metrics ?? {}).filter(([, e]) => e?.enabled === true).map(([id]) => id)),
		plus: plusAbo,
		plus_vorher: { display_config: { metrics: [{ metric_id: 'gust', enabled: true }, { metric_id: 'wind_chill', enabled: true }, { metric_id: 'temperature', enabled: true }] } },
		minus: minusAbo
	}
});

describe('p5c-1 Anlegen aus Vorlage: Kind-Groessen wie Python abgeleitet, Ausgabe wie vor p5a', () => {
	for (const v of ANLEGEN) {
		test(`anlegen_${v}_mail_spalten_wie_vor_p5a`, () => {
			assert.deepEqual(menge(AUS.trip[`${v}__neu`].mail), menge(AUS.trip[`${v}__vorher`].mail));
		});
		test(`anlegen_${v}_anzeige_gleich_mail`, () => {
			assert.deepEqual(neu[v].stand.auswahl, AUS.trip[`${v}__neu`].mail, 'Anzeige beim Anlegen (Folge) = Mail-Spalten');
			assert.equal(new Set(AUS.trip[`${v}__neu`].mail).size, AUS.trip[`${v}__neu`].mail.length, 'doppelte Mail-Spalte');
			assert.deepEqual(menge(lesen(neu[v].gespeichert).auswahl), menge(AUS.trip[`${v}__neu`].mail), 'neu geladen = Mail');
		});
	}
	// Elter-Folge wie vor p5a: abgeleitete Kinder standen (gleiche `order` wie der Elter) direkt hinter ihm.
	for (const [v, elter] of [['allgemein', 'temperature'], ['alpen-trekking', 'wind_chill']] as const) {
		test(`anlegen_${v}_kinder_direkt_hinter_${elter}_wie_vor_p5a`, () => {
			const block = (mail: string[]) => mail.slice(mail.indexOf(elter), mail.indexOf(elter) + 4);
			assert.deepEqual(block(AUS.trip[`${v}__neu`].mail), block(AUS.trip[`${v}__vorher`].mail));
		});
	}
	test('vorlage_uebernehmen_mail_wie_vor_p5a_und_anzeige_gleich_mail', () => {
		assert.deepEqual(menge(AUS.trip.vorlage.mail), menge(AUS.trip.vorlage_vorher.mail));
		// Menge: bestehende Eintraege behalten beim Uebernehmen ihre Folge (AC-19), das ist nicht Teil von p5c.
		assert.deepEqual(menge(vorlageUebernommen.auswahl), menge(AUS.trip.vorlage.mail));
	});
	test('plus_elter_bringt_abgeleitete_kinder_wie_vor_p5a', () => {
		assert.deepEqual(menge(AUS.trip.plus.mail), menge(AUS.trip.plus_vorher.mail));
		assert.deepEqual(plusWindchill.auswahl, AUS.trip.plus.mail);
	});
	test('bewusstes_minus_schreibt_nur_dieses_kind_aus', () => {
		const soll = AUS.trip.allgemein__neu.mail.filter((id) => id !== 'temperature_day_low');
		assert.deepEqual(AUS.trip.minus.mail, soll);
		assert.deepEqual(minusKind.auswahl, soll);
	});
	// #3020 R1 (G34, #2454 AC-2 spiegelbildlich): „−“ am Elter nimmt die mitgelaufenen Kinder mit; ein einzeln
	// umgezogenes Kind (hier: vor dem Elter einzeln dazugenommen) bleibt in Auswahl und Mail.
	test('minus_elter_nimmt_mitgelaufene_kinder_mit', { todo: 'Fehler #3363: „−“ an Temperatur lässt die abgeleiteten Größen stehen' }, () => {
		const einzeln = { ...lesen(BESTAND_A), auswahl: ['temperature_night', 'wind'] };
		const mitElter = Z.mitMetrik(einzeln, 'temperature', 'route');
		assert.deepEqual(mitElter.auswahl, ['temperature_night', 'wind', 'temperature', 'temperature_day_low', 'temperature_day_high'], 'Messaufbau');
		const ohne = Z.ohneMetrik(mitElter, 'temperature');
		assert.deepEqual(ohne.auswahl, ['temperature_night', 'wind']);
		const { mail } = pythonAusgabe({ trip: { ohne: tripSpeichern(BESTAND_A, ohne) } }).trip.ohne;
		assert.deepEqual(menge(mail), ['temperature_night', 'wind']);
	});
	test('messaufbau_vorlagen_ohne_kinder', () => {
		assert.ok(!KINDER.some((k) => VORLAGEN.allgemein.metrics?.[k]?.enabled === true), '„allgemein“ fuehrt Kinder');
		assert.ok(AUS.trip.allgemein__vorher.mail.includes('temperature_day_low'), 'vor p5a ohne abgeleitetes Tagestief');
	});
});

describe('p5c-1 Eigene Vorlage und „+“ ohne Doppelte', () => {
	test('eigene_vorlage_leitet_kinder_ab_mail_wie_vor_p5a', () => {
		const eigene = structuredClone(VORLAGEN.allgemein);
		const s = Z.mitEigenerVorlage(lesen(BESTAND_A), eigene, VORLAGEN, 'route', {});
		const a = pythonAusgabe({ trip: { neu: tripSpeichern(BESTAND_A, s), vorher: AUS_VORHER_ALLGEMEIN } });
		assert.deepEqual(menge(a.trip.neu.mail), menge(a.trip.vorher.mail));
		assert.deepEqual(menge(s.auswahl), menge(a.trip.neu.mail));
	});
	test('plus_elter_fuegt_vorhandenes_kind_nicht_doppelt_an', () => {
		const s = { ...lesen(BESTAND_A), auswahl: ['wind', 'temperature_night'] };
		assert.deepEqual(Z.mitMetrik(s, 'temperature', 'route').auswahl, ['wind', 'temperature_night', 'temperature', 'temperature_day_low', 'temperature_day_high']);
	});
});

describe('p5c-1 Vergleich: „+“ Temperatur leitet keine Trip-Kinder ab', () => {
	test('vergleich_plus_ohne_kinder', () => {
		const abo = { display_config: { active_metrics: [{ metric_id: 'wind', aggregation: 'max' }] } };
		const s = Z.standAusAbo('vergleich', abo as never, aufgeloestVon(abo), ALT, { eig: EIG });
		assert.deepEqual(Z.mitMetrik(s, 'temperature', 'vergleich').auswahl, ['wind', 'temperature']);
	});
});

describe('p5c-1 Verdrahtung: der Reiter (WetterTabInhalt) reicht beim „+“ seinen Kontext weiter', () => {
	const tab = path.resolve(WETTER_TAB, '../../organisms/wetter-tab/WetterTabInhalt.svelte');
	const api = {
		get: async (pfad: string) => {
			if (pfad === '/api/metrics') return LIVE.metrics;
			if (pfad === '/api/templates') return LIVE.templates;
			if (pfad === '/api/metric-presets') return [];
			throw new Error(`unerwartet: ${pfad}`);
		},
		post: aufloesungPost()
	};
	async function plusTemperatur(context: 'route' | 'vergleich', abo: Abo): Promise<string[]> {
		const { u } = await umgebungFuer(tab, {
			context,
			trip: context === 'route' ? abo : undefined,
			preset: context === 'vergleich' ? abo : undefined,
			createMode: false,
			saveController: undefined,
			enqueueHubWrite: undefined,
			onTripUpdate: undefined,
			onCompareUpdate: undefined,
			onAnlegeStand: undefined,
			api
		});
		const z = vergleichsKatalogFetch();
		try {
			await u.laden();
		} finally {
			z();
		}
		assert.equal(u.phase, 'bereit', 'Messaufbau: Reiter hat nicht geladen');
		u.hinzufuegen('temperature');
		return u.stand.auswahl;
	}
	test('trip_plus_temperatur_mit_kindern', async () => {
		const a = await plusTemperatur('route', { id: 't', name: 't', stages: [], ...structuredClone(BESTAND_B) });
		assert.ok(a.includes('temperature_day_low') && a.includes('temperature_night'), JSON.stringify(a));
	});
	test('vergleich_plus_temperatur_ohne_kinder', async () => {
		const a = await plusTemperatur('vergleich', { id: 'o', name: 'o', location_ids: [], display_config: { active_metrics: [{ metric_id: 'wind', aggregation: 'max' }] } });
		assert.deepEqual(a, ['wind', 'temperature']);
	});
});

// ── 2. Hub-Uebersicht ────────────────────────────────────────────────────────────────────────
const HUB_TRIPS: Record<string, Abo> = {
	a_nie_eingestellt: { id: 'a', name: 'a', stages: [], display_config: {}, report_config: {} },
	b_nie_eingestellt_alpen: { id: 'b', name: 'b', stages: [], display_config: { metrics: [], ampel: { template: 'alpen-trekking' } }, report_config: {} }
};
const HUB_ORTE: Record<string, Abo> = {
	a_nie_eingestellt: { id: 'o1', name: 'o1', location_ids: [], profil: 'wandern', display_config: {} },
	b_vorlage_alpen_ohne_liste: { id: 'o2', name: 'o2', location_ids: [], profil: 'wandern', display_config: { ampel: { template: 'alpen-trekking' } } },
	a_mit_nacht_tief: {
		id: 'o3',
		name: 'o3',
		location_ids: [],
		display_config: { active_metrics: [{ metric_id: 'wind', aggregation: 'max' }, { metric_id: 'temperature_night', aggregation: 'max' }] }
	}
};
const ohneKopf = (k: Record<string, Abo>) => Object.fromEntries(Object.entries(k).map(([id, a]) => [id, { ...a, id: undefined, name: undefined }]));
const HUB = pythonAusgabe({ trip: ohneKopf(HUB_TRIPS), orte: ohneKopf(HUB_ORTE) });

describe('p5c-2 Hub-Uebersicht: Zahl der Uebersicht = Zahl der Ausgabe', () => {
	for (const id of Object.keys(HUB_TRIPS)) {
		test(`trip_alarmzeile_${id}`, () => {
			const mail = HUB.trip[id].mail;
			const z = alarmZaehler(lesen(HUB_TRIPS[id]).ampel, mail, EIG);
			assert.equal(tripAlarmAbText(HUB_TRIPS[id] as never, VORLAGEN, EIG), tr(z.schluessel as MessageKey, z.werte));
		});
	}
	for (const id of Object.keys(HUB_ORTE)) {
		test(`orte_karte_wetter_${id}`, () => {
			const anzahl = new Set(HUB.orte[id].mail.map((z) => ZEILE_ZU_ID[z])).size;
			const k = deriveVergleichKennzahlen(HUB_ORTE[id] as never, 'active', null, [], VORLAGEN, ALT).wertebereicheKarte!;
			assert.equal(k.beschreibungKurz, trn('vergleich.hub.wertebereiche_kurz', anzahl));
		});
	}
	test('orte_karte_ohne_katalog_keine_geratene_zahl', () => {
		const k = deriveVergleichKennzahlen(HUB_ORTE.a_nie_eingestellt as never, 'active', null, [], VORLAGEN, null).wertebereicheKarte!;
		assert.equal(k.beschreibungKurz, '—');
	});
});

// ── 3. Orte „nie eingestellt“: Abwahl entfernt nur die Zeilen der Groesse ────────────────────
function orteSpeichern(abo: Abo, s: Z.WetterStand): Abo {
	const n = vergleichNutzlast({
		client: null as never,
		stand: () => s,
		vorlagen: () => VORLAGEN,
		abo: () => abo as never,
		aggregationFuer: aggregation,
		altSchluessel: ALT
	}) as Record<string, unknown>;
	return { display_config: ebene1(abo.display_config, n.display_config as Record<string, unknown>) };
}
const ORTE_NIE: Record<string, { abo: Abo; weg: string }> = {
	a_uv_weg: { abo: { display_config: {} }, weg: 'uv_index' },
	b_wind_weg_vorlage_alpen: { abo: { display_config: { ampel: { template: 'alpen-trekking' } } }, weg: 'wind' }
};
const orteNach = Object.fromEntries(
	Object.entries(ORTE_NIE).map(([id, f]) => {
		const s = Z.ohneMetrik(Z.standAusAbo('vergleich', f.abo as never, aufgeloestVon(f.abo), ALT, { eig: EIG }), f.weg);
		return [id, orteSpeichern(f.abo, s)];
	})
);
const ORTE_AUS = pythonAusgabe({
	orte: {
		...Object.fromEntries(Object.entries(ORTE_NIE).map(([id, f]) => [id, f.abo])),
		...Object.fromEntries(Object.entries(orteNach).map(([id, a]) => [`${id}__nach`, a]))
	}
});

describe('p5c-3 Orte nie eingestellt: Abwahl entfernt nur die Zeilen dieser Groesse', () => {
	for (const [id, f] of Object.entries(ORTE_NIE)) {
		test(`orte_${id}_uebrige_zeilen_bleiben`, () => {
			const vorher = ORTE_AUS.orte[id].mail;
			assert.ok(vorher.some((z) => ZEILE_ZU_ID[z] === f.weg), `Messaufbau: ${f.weg} nicht in der Tabelle`);
			assert.ok(new Set(vorher.map((z) => ZEILE_ZU_ID[z])).size < vorher.length, 'Messaufbau: keine Varianten-Zeilen');
			assert.deepEqual(ORTE_AUS.orte[`${id}__nach`].mail, vorher.filter((z) => ZEILE_ZU_ID[z] !== f.weg));
		});
	}
});
