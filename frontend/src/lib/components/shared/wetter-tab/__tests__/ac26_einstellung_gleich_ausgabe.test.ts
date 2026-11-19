// Issue #3047 Runde 7, AC-26 (Paket p5a, Befunde E1, E2, E5, E6, E7, E8, B-TM2).
// Spec: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md, „Nachtrag Runde 7“
// (Tech-Lead-Entscheidung: Grundauswahl „nie eingestellt“ = Mail-Standard, Vorlagen-Rueckfall nur
// in der Anlege-Kette). Konzept docs/context/einstellungen_neu.md §5 Punkt 6/8/9, §3.2 V12.
//
// AC-26: Given eine gespeicherte Konfiguration (nie eingestellt, Altbestand, Altformat, halbes
// Tagesfenster, `null`-Zusatzbloecke, Trend nie eingestellt) / When die Einstellungsseite sie laedt
// und eine unbeteiligte Aenderung speichert / Then zeigt sie genau, was die Ausgabe tut, und die
// Ausgabe aendert sich durch das Speichern nicht.
//
// Kette ohne Nachbau: echte Lade-Funktionen des Hubs (standAusAbo mit den Quellen, die
// WetterTabInhalt.svelte uebergibt: /api/metrics + Vergleichs-Katalog ueber den echten Lader;
// kanalStilStart; ladeMailZustand), echte Speicherer (tripNutzlast/vergleichNutzlast/
// kanalStilNutzlast), Ebene-1-Merge wie Go, danach die ECHTEN Python-Resolver (ausgabeOrakel.ts).
// Zwei Nutzer mit verschiedenen Konfigurationen; Folgen ungleich Katalogfolge.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/ac26_einstellung_gleich_ausgabe.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

import { FRONTEND, WETTER_TAB, live, vergleichsKatalogFetch } from './wetterTabDaten.ts';
import { ebene1, pythonAusgabe, type Konfigs } from './ausgabeOrakel.ts';
import { aktiveMetriken, altSchluesselAusKatalog, ausgebbarTeilen, eigenschaftenAusKatalog, vorlagenAusTemplates } from '../ampelModell.ts';
import { loadCompareSelectionEntries } from '../compareMetricCatalogLoader.ts';
import * as Z from '../wetterZustand.ts';
import { tripNutzlast, vergleichNutzlast } from '../wetterTabSpeicherung.ts';
import { kanalStilNutzlast, kanalStilStart } from '../../zustellung-tab/kanalStilSpeicherung.ts';
import { ladeMailZustand } from '../../mailInhaltZustand.ts';
import { baueReportConfigPayload, ladeReportZustand } from '../../versand-tab/reportConfigPayload.ts';
import { umgebungFuer } from '../../__tests__/svelteInstanzPruefstand.ts';
import { DERIVED_METRIC_RULES } from '../../../trip-detail/metricsEditor.ts';

type Abo = Record<string, unknown> & { display_config?: Record<string, unknown>; report_config?: Record<string, unknown> };

const LIVE = live();
const VORLAGEN = vorlagenAusTemplates(LIVE.templates);
const EIG = eigenschaftenAusKatalog(LIVE.metrics);
const zurueck = vergleichsKatalogFetch();
const KATALOG = await loadCompareSelectionEntries();
zurueck();
const ALT = altSchluesselAusKatalog(KATALOG);
const KATALOG_IDS = new Set(KATALOG.flatMap((e) => (e.metric_id ? [e.metric_id] : [])));
const aggregation = (id: string) => KATALOG.find((e) => e.metric_id === id)?.aggregation ?? 'max';
/** Zeilen-Schluessel der Vergleichstabelle (temp_max_c …) -> Groesse. */
const ZEILE_ZU_ID = Object.fromEntries(KATALOG.map((e) => [(e as { metric?: string }).metric, e.metric_id]));
const menge = (a: string[]) => [...new Set(a)].sort();

// ── Gespeicherte Konfigurationen (Persistenzformat), je Nutzer eigene ─────────────────────────
const TRIPS: Record<string, Abo> = {
	a_nie_eingestellt_ohne_metrics: { display_config: {}, report_config: { multi_day_trend_reports: [] } },
	b_metrics_leer_vorlage_alpen: { display_config: { metrics: [], ampel: { template: 'alpen-trekking' } }, report_config: {} },
	a_folge_mit_temperatur: {
		display_config: {
			metrics: [
				{ metric_id: 'precipitation', enabled: true, bucket: 'primary', order: 0 },
				{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 1 },
				{ metric_id: 'temperature', enabled: true, bucket: 'primary', order: 2 },
				{ metric_id: 'wind', enabled: false, bucket: 'primary', order: 3 }
			]
		},
		report_config: { multi_day_trend_reports: ['morning'] }
	},
	b_temperatur_vorn: {
		display_config: {
			metrics: [
				{ metric_id: 'temperature', enabled: true, bucket: 'primary', order: 0 },
				{ metric_id: 'thunder', enabled: true, bucket: 'primary', order: 1 },
				{ metric_id: 'temperature_day_low', enabled: false, bucket: 'primary', order: 2 }
			]
		}
	},
	a_altformat: { display_config: { metrics: ['wind', { metric_id: 'gust' }, { metric_id: 'precipitation', enabled: true }] } },
	b_tagesfenster_halb: { display_config: {}, report_config: { day_window_start_hour: 6 } },
	a_tagesfenster_gleich: { display_config: {}, report_config: { day_window_start_hour: 8, day_window_end_hour: 8 } },
	b_tagesfenster_mitternacht: { display_config: {}, report_config: { day_window_start_hour: 22, day_window_end_hour: 3 } },
	a_trend_nie_eingestellt: { display_config: {}, report_config: { morning_time: '06:15:00' } },
	b_ohne_report_config: { display_config: { metrics: [{ metric_id: 'wind', enabled: true, bucket: 'primary', order: 0 }] } },
	a_trend_flags_widersprechen: {
		display_config: {},
		report_config: { multi_day_trend_morning: true, multi_day_trend_evening: false, multi_day_trend_reports: ['evening'] }
	},
	b_mailinhalt_null: { display_config: {}, report_config: { show_stage_stats: null, show_yesterday_comparison: null } },
	a_bewusst_leer: { display_config: { metrics: [{ metric_id: 'temperature', enabled: false }, { metric_id: 'wind', enabled: false }] } }
};

const ORTE: Record<string, Abo> = {
	a_nie_eingestellt: { display_config: {} },
	b_vorlage_alpen_ohne_liste: { display_config: { ampel: { template: 'alpen-trekking' } } },
	a_folge: { display_config: { active_metrics: [{ metric_id: 'gust', aggregation: 'max' }, { metric_id: 'precipitation', aggregation: 'sum' }, { metric_id: 'temperature', aggregation: 'max' }] } },
	b_mit_nacht_tief: {
		display_config: {
			active_metrics: [
				{ metric_id: 'wind', aggregation: 'max' },
				{ metric_id: 'temperature_night', aggregation: 'max' },
				{ metric_id: 'temperature', aggregation: 'min' }
			]
		}
	},
	a_bewusst_leer: { display_config: { active_metrics: [] } }
};

const trip = (id: string, roh: Abo): Abo => ({ id, name: id, stages: [], ...structuredClone(roh) });
const ort = (id: string, roh: Abo): Abo => ({ id, name: id, location_ids: [], ...structuredClone(roh) });

// ── Editor-Seite (echte Lader) ───────────────────────────────────────────────────────────────
function tripSicht(abo: Abo) {
	const w = Z.standAusAbo('route', abo, VORLAGEN, {}, { eig: EIG });
	const k = kanalStilStart('route', abo as never);
	const m = ladeMailZustand(abo.report_config ?? {});
	return {
		auswahl: menge(w.auswahl),
		tagesfenster: [w.tagesfenster.start, w.tagesfenster.end],
		trend: [k.trendMorgen, k.trendAbend],
		etappen_kennzahlen: m.show_stage_stats,
		vortag: m.show_yesterday_comparison
	};
}

function orteSicht(abo: Abo) {
	const w = Z.standAusAbo('vergleich', abo, VORLAGEN, ALT, { eig: EIG });
	const t = ausgebbarTeilen('vergleich', w.auswahl, KATALOG_IDS);
	return { auswahl: menge(t.zeilen), gesperrt: t.gesperrt, tagesfenster: [w.tagesfenster.start, w.tagesfenster.end] };
}

// ── Unbeteiligte Gesten mit dem echten Speicherer, danach Ebene-1-Merge wie Go ─────────────
/** Reiter Wetter: „Alarm ab fuer alle: Rot" (aendert nur die Ampel). */
function tripNachWetterGeste(abo: Abo): Abo {
	const s = Z.mitAlarmAbFuerAlle(Z.standAusAbo('route', abo, VORLAGEN, {}, { eig: EIG }), 'red', EIG);
	const n = tripNutzlast({ client: null as never, stand: () => s, vorlagen: () => VORLAGEN, abo: () => abo });
	return {
		...abo,
		display_config: ebene1(abo.display_config, n.weatherConfig as Record<string, unknown>),
		report_config: ebene1(abo.report_config, n.tripFelder.report_config),
		official_alerts_enabled: n.tripFelder.official_alerts_enabled,
		official_warnings: n.tripFelder.official_warnings
	};
}

/** Uebergangsblock Zustellung: Telegram-Kurzstil umschalten. */
function tripNachKurzstil(abo: Abo): Abo {
	const start = kanalStilStart('route', abo as never);
	const n = kanalStilNutzlast('route', { ...start, stil: start.stil === 'rich' ? 'kurzform' : 'rich' }, start) as { report_config: Record<string, unknown> };
	return { ...abo, report_config: ebene1(abo.report_config, n.report_config) };
}

function orteNachWetterGeste(abo: Abo): Abo {
	const s = Z.mitAlarmAbFuerAlle(Z.standAusAbo('vergleich', abo, VORLAGEN, ALT, { eig: EIG }), 'red', EIG);
	const n = vergleichNutzlast({
		client: null as never,
		stand: () => s,
		vorlagen: () => VORLAGEN,
		abo: () => abo,
		aggregationFuer: aggregation,
		altSchluessel: ALT
	}) as Record<string, unknown>;
	const { display_config, ...oben } = n;
	return { ...abo, ...JSON.parse(JSON.stringify(oben)), display_config: ebene1(abo.display_config, display_config as Record<string, unknown>) };
}

function ohneId(k: Record<string, Abo>): Record<string, unknown> {
	return Object.fromEntries(Object.entries(k).map(([id, a]) => [id, { ...a, id: undefined, name: undefined }]));
}

// ── Eine Python-Runde fuer alle Faelle (vorher, nach Wetter-Geste, nach Kurzstil) ───────────
const nachWetter = Object.fromEntries(Object.entries(TRIPS).map(([id, r]) => [id, tripNachWetterGeste(trip(id, r))]));
const nachKurz = Object.fromEntries(Object.entries(TRIPS).map(([id, r]) => [id, tripNachKurzstil(trip(id, r))]));
const orteNach = Object.fromEntries(Object.entries(ORTE).map(([id, r]) => [id, orteNachWetterGeste(ort(id, r))]));
const eingabe: Konfigs = {
	trip: {
		...ohneId(Object.fromEntries(Object.entries(TRIPS).map(([id, r]) => [id, trip(id, r)]))),
		...Object.fromEntries(Object.entries(ohneId(nachWetter)).map(([id, a]) => [`${id}__wetter`, a])),
		...Object.fromEntries(Object.entries(ohneId(nachKurz)).map(([id, a]) => [`${id}__kurzstil`, a]))
	},
	orte: {
		...ohneId(Object.fromEntries(Object.entries(ORTE).map(([id, r]) => [id, ort(id, r)]))),
		...Object.fromEntries(Object.entries(ohneId(orteNach)).map(([id, a]) => [`${id}__wetter`, a]))
	}
};
const AUS = pythonAusgabe(eingabe);

function tripAusgabeSicht(id: string) {
	const a = AUS.trip[id];
	return { auswahl: menge(a.mail ?? []), tagesfenster: a.tagesfenster, trend: a.trend, etappen_kennzahlen: a.etappen_kennzahlen, vortag: a.vortag };
}

describe('AC-26 Trip: Einstellungsseite zeigt, was die Ausgabe tut', () => {
	for (const id of Object.keys(TRIPS)) {
		test(`anzeige_gleich_ausgabe_${id}`, () => {
			assert.deepEqual(tripSicht(trip(id, TRIPS[id])), tripAusgabeSicht(id));
		});
	}
});

describe('AC-26 Trip: unbeteiligtes Speichern aendert die Ausgabe nicht', () => {
	for (const id of Object.keys(TRIPS)) {
		test(`wetter_geste_ausgabe_bleibt_${id}`, () => {
			assert.deepEqual(AUS.trip[`${id}__wetter`], AUS.trip[id], 'Reiter Wetter: „Alarm ab fuer alle" aendert die Ausgabe');
			assert.deepEqual(AUS.trip[`${id}__wetter`].mail, AUS.trip[id].mail, 'Mail-Spaltenfolge');
		});
		test(`kurzstil_ausgabe_bleibt_${id}`, () => {
			assert.deepEqual(AUS.trip[`${id}__kurzstil`].trend, AUS.trip[id].trend, 'Kurzstil umschalten aendert den Mehrtages-Trend');
		});
		test(`neu_geladen_zeigt_dasselbe_${id}`, () => {
			assert.deepEqual(tripSicht(nachWetter[id]), tripSicht(trip(id, TRIPS[id])));
		});
	}
});

describe('AC-26 Orte: Einstellungsseite zeigt, was die Ausgabe tut', () => {
	for (const id of Object.keys(ORTE)) {
		test(`anzeige_gleich_ausgabe_${id}`, () => {
			const a = AUS.orte[id];
			const sicht = orteSicht(ort(id, ORTE[id]));
			assert.deepEqual(sicht.auswahl, menge(a.mail.map((z) => ZEILE_ZU_ID[z])), 'Zeilen des Reiters = Zeilen der Vergleichstabelle');
			assert.deepEqual(sicht.tagesfenster, a.tagesfenster);
		});
		test(`wetter_geste_ausgabe_bleibt_${id}`, () => {
			assert.deepEqual(AUS.orte[`${id}__wetter`], AUS.orte[id]);
		});
	}

	test('e6_nicht_ausgebbare_groesse_steht_gesperrt_statt_still', () => {
		assert.deepEqual(orteSicht(ort('b_mit_nacht_tief', ORTE.b_mit_nacht_tief)).gesperrt, ['temperature_night']);
		const nach = orteNach.b_mit_nacht_tief.display_config as { active_metrics: { metric_id: string }[] };
		assert.ok(nach.active_metrics.some((e) => e.metric_id === 'temperature_night'), 'gesperrter Eintrag beim Speichern verloren');
	});
});

describe('AC-26 Anlege-Kette: Vorlage gilt, im Vergleich nur ausgebbare Groessen (E1, E6)', () => {
	test('trip_anlegen_zeigt_vorlage', () => {
		const s = Z.standAusAbo('route', { display_config: { ampel: { template: 'alpen-trekking' } } }, VORLAGEN, {}, { eig: EIG, alsVorlage: true });
		// p5c (Tech-Lead-Entscheidung, Ausgabe unveraendert): die Vorlage samt der Kinder, die Python aus
		// ihren Eltern ableitet (Mail-Nachweis: p5c_ableitung_hub_orte_ausgabe.test.ts).
		const vorlage = aktiveMetriken(VORLAGEN['alpen-trekking']);
		const kinder = DERIVED_METRIC_RULES.filter((r) => vorlage.includes(r.parent)).map((r) => r.child);
		assert.deepEqual(menge(s.auswahl), menge([...vorlage, ...kinder]));
	});
	test('vergleich_anlegen_vorlage_ohne_nicht_ausgebbare', () => {
		const s = Z.standAusAbo('vergleich', { display_config: { ampel: { template: 'alpen-trekking' } } }, VORLAGEN, ALT, { eig: EIG, alsVorlage: true });
		const vorlage = aktiveMetriken(VORLAGEN['alpen-trekking']);
		assert.ok(vorlage.includes('temperature_night'), 'Messaufbau: Vorlage ohne Nacht-Tiefst');
		assert.deepEqual(menge(s.auswahl), menge(vorlage.filter((id) => KATALOG_IDS.has(id))));
	});
	test('vergleich_vorlage_uebernehmen_ohne_nicht_ausgebbare', () => {
		const s0 = Z.standAusAbo('vergleich', ort('x', ORTE.a_folge), VORLAGEN, ALT, { eig: EIG });
		const s = Z.mitVorlage(s0, 'alpen-trekking', VORLAGEN, 'vergleich', ALT);
		assert.ok(!s.auswahl.includes('temperature_night'));
		assert.ok(s.auswahl.length > 0);
	});
});

describe('B-TM2: wieder hinzugefuegte Metrik steht in der Mail hinten (feat_2794 AC-19)', () => {
	test('minus_dann_plus_haengt_hinten_an', () => {
		const roh: Abo = {
			display_config: {
				metrics: [
					{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 0 },
					{ metric_id: 'uv_index', enabled: true, bucket: 'primary', order: 1 },
					{ metric_id: 'wind', enabled: true, bucket: 'primary', order: 2 }
				]
			},
			report_config: {}
		};
		const speichern = (abo: Abo, schritt: (s: Z.WetterStand) => Z.WetterStand): Abo => {
			const s = schritt(Z.standAusAbo('route', abo, VORLAGEN, {}, { eig: EIG }));
			const n = tripNutzlast({ client: null as never, stand: () => s, vorlagen: () => VORLAGEN, abo: () => abo });
			return { ...abo, display_config: ebene1(abo.display_config, n.weatherConfig as Record<string, unknown>) };
		};
		const ohne = speichern(trip('b', roh), (s) => Z.ohneMetrik(s, 'uv_index'));
		const wieder = speichern(ohne, (s) => Z.mitMetrik(s, 'uv_index'));
		const a = pythonAusgabe({ trip: { ohne: ohne, wieder: wieder } });
		assert.deepEqual(a.trip.ohne.mail, ['gust', 'wind']);
		assert.deepEqual(a.trip.wieder.mail, ['gust', 'wind', 'uv_index']);
	});
});

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
const NICHT_IM_BRIEFING = (await import(pathToFileURL(path.resolve(WETTER_TAB, '../../organisms/wetter-tab/NichtImBriefing.svelte')).href)).default;

describe('E6: gesperrte Groesse mit Grund in DE und EN', () => {
	const komp = NICHT_IM_BRIEFING;
	for (const [sprache, erwartet] of [['de', 'Nicht im Orts-Vergleich ausgebbar'], ['en', 'Not available in the location comparison']] as const) {
		test(`gesperrt_grund_${sprache}`, () => {
			locale.set(sprache);
			const { body } = render(komp, {
				props: { metriken: [], gesperrt: [{ id: 'temperature_night', name: 'NACHTTIEF' }], hinzugefuegt: null, onHinzufuegen: () => {} }
			});
			assert.match(body, /data-testid="wetter-gesperrt"/);
			assert.ok(body.includes(erwartet) && body.includes('NACHTTIEF'), body);
			locale.set('de');
		});
	}
});

// #3155 (Spec feat_3155 Entscheidung 4): die Karte „Mehrtages-Trend" und ihre Bool-Felder
// entfallen; gueltig bleibt, dass die Liste (die Python allein liest) das Speichern
// unveraendert uebersteht und widersprechende Bool-Felder nichts bewirken.
describe('E2: Speichern erhaelt die Ausblick-Liste, die Python liest (Liste vor Bool-Feldern)', () => {
	for (const id of Object.keys(TRIPS).filter((k) => Array.isArray(TRIPS[k].report_config?.multi_day_trend_reports))) {
		test(`liste_vor_flags_${id}`, () => {
			const rc = TRIPS[id].report_config as Record<string, unknown>;
			const liste = rc.multi_day_trend_reports as string[];
			const nach = baueReportConfigPayload({ snapshot: rc, live: rc, zustand: ladeReportZustand(rc) });
			assert.deepEqual(nach.multi_day_trend_reports, liste, 'Speichern veraendert die Ausblick-Liste');
			assert.deepEqual([liste.includes('morning'), liste.includes('evening')], AUS.trip[id].trend);
		});
	}
});

describe('E2: Kurzstil umschalten sendet nur den Stil (fremder Trend-Stand bleibt)', () => {
	test('kurzstil_ueberschreibt_spaeter_gespeicherten_trend_nicht', () => {
		const geladen = trip('t', TRIPS.a_trend_nie_eingestellt);
		const start = kanalStilStart('route', geladen as never);
		// Nach dem Laden speichert ein anderer Schreiber (z. B. zweiter Tab) „Trend nur morgens“.
		const zwischen = { ...geladen, report_config: ebene1(geladen.report_config, { multi_day_trend_reports: ['morning'] }) };
		const n = kanalStilNutzlast('route', { ...start, stil: 'kurzform' }, start) as { report_config: Record<string, unknown> };
		const danach = { ...zwischen, report_config: ebene1(zwischen.report_config, n.report_config), id: undefined };
		const a = pythonAusgabe({ trip: { danach } });
		assert.deepEqual(a.trip.danach.trend, [true, false], 'Kurzstil-Speichern hat den Trend zurueckgeschrieben');
		assert.equal(n.report_config.telegram_style, 'kurzform');
	});
});

describe('AC-26 Verdrahtung: der Reiter (WetterTabInhalt) laedt mit den Quellen des Mail-Standards', () => {
	const tab = path.resolve(WETTER_TAB, '../../organisms/wetter-tab/WetterTabInhalt.svelte');
	const lesen = {
		get: async (pfad: string) => {
			if (pfad === '/api/metrics') return LIVE.metrics;
			if (pfad === '/api/templates') return LIVE.templates;
			if (pfad === '/api/metric-presets') return [];
			throw new Error(`unerwartet: ${pfad}`);
		}
	};
	async function montiert(context: 'route' | 'vergleich', abo: Abo) {
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
			api: lesen
		});
		const zurueckFetch = vergleichsKatalogFetch();
		try {
			await u.laden();
		} finally {
			zurueckFetch();
		}
		assert.equal(u.phase, 'bereit', 'Messaufbau: Reiter hat nicht geladen');
		return u;
	}
	test('trip_nie_eingestellt_zeigt_register_standard', async () => {
		const u = await montiert('route', trip('t', TRIPS.a_nie_eingestellt_ohne_metrics));
		assert.deepEqual(menge(u.stand.auswahl), menge(AUS.trip.a_nie_eingestellt_ohne_metrics.mail));
	});
	test('orte_nie_eingestellt_zeigt_alle_zeilen_und_gesperrtes', async () => {
		const u = await montiert('vergleich', ort('o', ORTE.a_nie_eingestellt));
		assert.deepEqual(menge(u.stand.auswahl), menge(AUS.orte.a_nie_eingestellt.mail.map((z) => ZEILE_ZU_ID[z])));
		const v = await montiert('vergleich', ort('o2', ORTE.b_mit_nacht_tief));
		assert.deepEqual(ausgebbarTeilen('vergleich', v.stand.auswahl, v.katalogIds).gesperrt, ['temperature_night']);
	});
});
