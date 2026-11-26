// TDD RED — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter), Modell-Schicht `ampelModell.ts`.
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md — AC-12, AC-14, AC-15, AC-17, AC-18, AC-37, AC-39
//
// Reine Funktionen, EIN Code fuer Trip und Orts-Briefing. Vorlagen-Ampeln kommen aus `/api/templates`,
// Metrik-Eigenschaften (group, alertable, is_precursor, allowed_sides, display_only, unit) aus
// `/api/metrics` — beide hier aus der echten Python-Antwort, nie aus einer Frontend-Kopie.
// Texte liefert das Modell NIE selbst: nur Katalogschluessel (Bereich `wetter`) und Platzhalter-Werte.
//
// Festgelegte API (ampelModell.ts):
//   type AlarmAb = 'never'|'yellow'|'orange'|'red'; type Farbe = 'yellow'|'orange'|'red'
//   type Seite = {red?, orange?, yellow?: number|null}
//   type AmpelMetrik = {enabled?: boolean; alarm_ab?: AlarmAb; lower?: Seite|null; upper?: Seite|null}
//   type Ampel = {template?: string; metrics?: Record<string, AmpelMetrik>; thunder?: {mittel?: Farbe; hoch?: Farbe}}
//   type VorlagenAmpeln = Record<string, Ampel>
//   type MetrikEigenschaften = {id, group, alertable, is_precursor, allowed_sides, display_only, unit}
//   vorlagenAusTemplates(liste)                      -> VorlagenAmpeln            (GET /api/templates)
//   eigenschaftenAusKatalog(apiMetrics)              -> Record<id, MetrikEigenschaften> (GET /api/metrics, nach Kategorie)
//   (#2988 S4: Aufloesung, Gueltigkeit und Vorlagen-Wahl rechnet allein Python, POST /api/ampel/aufloesung;
//    hier ueber `pythonAufloesung` aus wetterTabDaten.ts. Der Zaehler zaehlt `abweichungsMenge`.)
//   grenzenFehler({lower, upper})                    -> string[] Katalogschluessel wetter.* (AC-17)
//   gewitterFarben('mittel'|'hoch')                  -> Farbe[]  (mittel: gelb·orange·rot, hoch: orange·rot)
//   gewitterFehler(thunder)                          -> string[] (leer = gueltig)
//   alarmAbOptionen(id, eig)                         -> AlarmAb[] (Gewitter ohne 'yellow'; nicht alarmfaehig -> [])
//   gruenZeile(eintrag, eig)                         -> {art: 'von_bis'|'ab'|'bis'|'immer', schluessel, werte}
//   erklaersatz(id, eintrag, eig, thunder?)          -> {art: 'normal'|'gewitter'|'gewitter_nie'|'nie'|'vorbote'|'anzeige'|'ohne_grenze', schluessel, werte}
//   zeilenGruppen(auswahl, eig)                      -> {gruppe, metriken: string[]}[] (feste Gruppenfolge, nur belegte, unbekannte Ids fallen weg)
//   aktiveMetriken(aufgeloest)                       -> string[] (enabled === true)
//   auswahlLesen(context, displayConfig, aufgeloest) -> string[] (Trip: metrics[].enabled; Vergleich: active_metrics, fehlt -> aus Ampel)
//   alarmAbFuerAlle(ampel, auswahl, stufe, eig)      -> Ampel (nur gewaehlte alarmfaehige Metriken; Gewitter nie 'yellow')
//   alarmZaehler(ampel, auswahl, eig)                -> {art: 'zaehler'|'keine_alarmfaehig', schluessel, werte}
//   zuruecksetzen(vorlageId, vorlagen)               -> {ampel: Ampel (aufgeloest), auswahl: string[]}
//
// RED heute: ampelModell.ts und der Katalog wetter.json existieren nicht.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/ampelModell.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { ampelModell, ampelSchreiben, live, ohneOffene, pruefeKatalogModell, pythonAufloesung, wetterKatalog, type Json } from './wetterTabDaten.ts';

const GRUPPEN_FOLGE = ['temperature', 'wind', 'precip_thunder', 'sky_visibility', 'snow_height'];

async function umgebung(): Promise<{ m: Json; vorlagen: Json; eig: Json }> {
	const m = await ampelModell();
	const daten = live();
	return { m, vorlagen: m.vorlagenAusTemplates(daten.templates), eig: m.eigenschaftenAusKatalog(daten.metrics) };
}

const enabledIds = (ampel: Json): string[] =>
	Object.entries(ampel.metrics as Record<string, Json>).filter(([, e]) => e.enabled === true).map(([id]) => id).sort();

/** Aufgeloeste Ampel eines Eintrags (Abo-Sicht `{ampel}` oder Altbestand `{metrics}`), echtes Python (#2988). */
const aufgeloest = (eintrag: Json): Json => pythonAufloesung([eintrag])[0].ampel;

/** Abweichungen einer aufgeloesten Ampel gegen eine Vorlagen-Ampel, wie der Reiter sie zaehlt (#2988 S1):
 *  Eintraege der kleinsten Speichermenge plus Gewitter einmal; Auswahl = die eingeschalteten Zeilen. */
async function abweichungen(vorlage: Json, ampel: Json): Promise<number> {
	const { m } = await umgebung();
	const menge = (await ampelSchreiben()).abweichungsMenge(vorlage, ampel, m.aktiveMetriken(ampel));
	return Object.keys(menge.metrics ?? {}).length + (menge.thunder ? 1 : 0);
}

// ── Daten-Adapter ────────────────────────────────────────────────────────────

describe('Adapter: Vorlagen und Eigenschaften kommen aus /api/templates und /api/metrics', () => {
	test('vorlagenAusTemplates liefert alle 7 Systemvorlagen mit vollstaendiger Ampel', async () => {
		const { vorlagen } = await umgebung();
		const ids = live().templates.map((t: Json) => t.id).sort();
		assert.equal(ids.length, 7, 'Messaufbau: /api/templates liefert nicht 7 Vorlagen');
		assert.deepEqual(Object.keys(vorlagen).sort(), ids);
		for (const id of ids) {
			assert.equal(vorlagen[id].template, id);
			assert.ok(Object.keys(vorlagen[id].metrics).length >= 10, `${id}: Ampel unvollstaendig`);
			assert.ok(vorlagen[id].thunder?.mittel && vorlagen[id].thunder?.hoch, `${id}: Gewitterfarben fehlen`);
		}
	});

	test('eigenschaftenAusKatalog liest die AC-27-Felder je Metrik unveraendert', async () => {
		const { eig } = await umgebung();
		for (const liste of Object.values(live().metrics) as Json[][]) {
			for (const k of liste) {
				const e = eig[k.id];
				assert.ok(e, `${k.id} fehlt`);
				for (const f of ['group', 'alertable', 'is_precursor', 'allowed_sides', 'display_only', 'unit']) {
					assert.deepEqual(e[f], k[f], `${k.id}.${f}: ${JSON.stringify(e[f])} != Katalog ${JSON.stringify(k[f])}`);
				}
			}
		}
	});
});

// ── AC-17: Reihenfolge-Regeln ────────────────────────────────────────────────

describe('AC-17: Reihenfolge-Regeln der Grenzen (Fehlerschluessel statt Text)', () => {
	test('ac17_gueltige_grenzen_ohne_fehler', async () => {
		const { m } = await umgebung();
		assert.deepEqual(m.grenzenFehler({ upper: { yellow: 40, orange: 60, red: 75 } }), []);
		assert.deepEqual(m.grenzenFehler({ lower: { red: -10, orange: -5, yellow: 0 }, upper: { yellow: 26, orange: 30, red: 33 } }), []);
		assert.deepEqual(m.grenzenFehler({ upper: { yellow: null, orange: 50, red: null } }), [], 'leeres Feld = keine Grenze, kein Fehler');
		assert.deepEqual(m.grenzenFehler({ lower: { yellow: 20 }, upper: { yellow: 20 } }), [], 'Gleichheitsrand ist gueltig (wie validate_ampel)');
	});

	const FAELLE: Array<[string, Json]> = [
		['oben_gelb_50_orange_40', { upper: { yellow: 50, orange: 40 } }],
		['unten_gelb_0_orange_5', { lower: { orange: 5, yellow: 0 } }],
		['unten_rot_ueber_orange', { lower: { red: 0, orange: -5, yellow: 5 } }],
		['unten_ueber_oben', { lower: { yellow: 30 }, upper: { yellow: 20 } }]
	];
	for (const [name, e] of FAELLE) {
		test(`ac17_${name}_liefert_katalogschluessel`, async () => {
			const { m } = await umgebung();
			const f = m.grenzenFehler(e);
			assert.ok(Array.isArray(f) && f.length > 0, `AC-17: ${JSON.stringify(e)} gilt als gueltig`);
			const de = wetterKatalog('de');
			for (const k of f) {
				assert.match(k, /^wetter\.[a-z0-9_.]+$/, `AC-17: Fehler ist kein Katalogschluessel: ${k}`);
				assert.ok(k in de, `AC-17: Fehlerschluessel ${k} fehlt in de/wetter.json`);
			}
		});
	}

	test('ac17_oben_unten_und_kreuz_haben_eigene_schluessel', async () => {
		const { m } = await umgebung();
		const oben = m.grenzenFehler(FAELLE[0][1]);
		const unten = m.grenzenFehler(FAELLE[1][1]);
		const kreuz = m.grenzenFehler(FAELLE[3][1]);
		assert.notDeepEqual(oben, unten, 'oben und unten melden denselben Fehler');
		assert.notDeepEqual(kreuz, oben, '„unten ueber oben“ meldet denselben Fehler wie die obere Reihenfolge');
	});
	// #2988 S4: die Regelgleichheit der ganzen Ampel (validate_ampel, Windrichtung) prueft nur noch
	// Python/Go; der Frontend-Spiegel `ampelFehler` ist entfernt. Sektoren-Abweichung: #3230.
});

// ── AC-18: Gewitter-Regeln ───────────────────────────────────────────────────

describe('AC-18: Gewitter (mittel gelb·orange·rot, hoch orange·rot, kein „Alarm ab Gelb“)', () => {
	test('ac18_gewitter_farbwahl_je_stufe', async () => {
		const { m } = await umgebung();
		assert.deepEqual(m.gewitterFarben('mittel'), ['yellow', 'orange', 'red']);
		assert.deepEqual(m.gewitterFarben('hoch'), ['orange', 'red']);
	});

	test('ac18_gewitter_kein_alarm_ab_gelb', async () => {
		const { m, eig } = await umgebung();
		assert.deepEqual(m.alarmAbOptionen('thunder', eig.thunder), ['never', 'orange', 'red']);
		assert.deepEqual(m.alarmAbOptionen('gust', eig.gust), ['never', 'yellow', 'orange', 'red']);
	});

	test('ac18_nicht_alarmfaehige_metriken_ohne_alarm_ab_wahl', async () => {
		const { m, eig } = await umgebung();
		for (const id of ['humidity', 'rain_probability', 'wind_direction']) {
			assert.deepEqual(m.alarmAbOptionen(id, eig[id]), [], `${id}: bietet „Alarm ab“ an, obwohl nicht alarmfaehig`);
		}
	});

	test('ac18_gewitter_farbregeln', async () => {
		const { m } = await umgebung();
		assert.deepEqual(m.gewitterFehler({ mittel: 'yellow', hoch: 'orange' }), []);
		assert.deepEqual(m.gewitterFehler({ mittel: 'red', hoch: 'red' }), []);
		assert.ok(m.gewitterFehler({ mittel: 'red', hoch: 'orange' }).length > 0, 'hoch schwaecher als mittel gilt als gueltig');
		assert.ok(m.gewitterFehler({ mittel: 'yellow', hoch: 'yellow' }).length > 0, 'hoch gelb gilt als gueltig');
	});
});

// ── AC-15/AC-16/AC-18: „gruen: …“-Zeile und Erklaersatz (nur Schluessel + Platzhalter) ──────

describe('AC-15: „gruen: …“-Zeile', () => {
	const FAELLE: Array<[string, string, (v: Json) => Json, string, Record<string, unknown>]> = [
		['beidseitig', 'temperature', (v) => v.wandern.metrics.temperature, 'von_bis', { von: 0, bis: 26, einheit: '°C' }],
		['nur_oben', 'gust', (v) => v.wandern.metrics.gust, 'bis', { bis: 40, einheit: 'km/h' }],
		// nur_unten (visibility aus der Vorlage): Erwartung korrigiert auf 'm', siehe Block #2946 unten
		['keine_grenze', 'humidity', (v) => v.wandern.metrics.humidity, 'immer', {}],
		['mildeste_gesetzte_grenze', 'gust', () => ({ upper: { yellow: null, orange: 50, red: null } }), 'bis', { bis: 50, einheit: 'km/h' }]
	];
	for (const [name, id, eintrag, art, werte] of FAELLE) {
		test(`ac15_gruen_${name}`, async () => {
			const { m, vorlagen, eig } = await umgebung();
			const z = m.gruenZeile(eintrag(vorlagen), eig[id]);
			assert.equal(z.art, art, `${name}: Art ${z.art}`);
			assert.deepEqual(z.werte ?? {}, werte);
			pruefeKatalogModell(z, `gruenZeile ${name}`);
		});
	}
});

describe('AC-15/AC-16/AC-18: Erklaersatz-Modell', () => {
	test('ac16_normal_oben_orange_aus_der_vorlage', async () => {
		const { m, vorlagen, eig } = await umgebung();
		const s = m.erklaersatz('gust', vorlagen.wandern.metrics.gust, eig.gust);
		assert.equal(s.art, 'normal');
		assert.equal(s.werte.oben, 60);
		assert.equal(s.werte.einheit, 'km/h');
		assert.equal(s.werte.stufe, 'orange');
		assert.equal('unten' in s.werte, false);
		pruefeKatalogModell(s, 'Erklaersatz normal oben');
	});

	test('ac16_normal_folgt_der_geaenderten_grenze_50', async () => {
		const { m, vorlagen, eig } = await umgebung();
		const e = structuredClone(vorlagen.wandern.metrics.gust);
		e.upper.orange = 50;
		const s = m.erklaersatz('gust', e, eig.gust);
		assert.equal(s.werte.oben, 50, 'AC-16: Erklaersatz zeigt nicht „ueber 50 km/h“');
	});

	test('ac15_normal_beidseitig_nennt_oben_und_unten', async () => {
		const { m, vorlagen, eig } = await umgebung();
		const s = m.erklaersatz('temperature', vorlagen.wandern.metrics.temperature, eig.temperature);
		assert.equal(s.art, 'normal');
		assert.equal(s.werte.oben, 30);
		assert.equal(s.werte.unten, -5);
		pruefeKatalogModell(s, 'Erklaersatz normal beidseitig');
	});

	test('ac15_nie_vorbote_anzeige_ohne_grenze', async () => {
		const { m, vorlagen, eig } = await umgebung();
		const nie = m.erklaersatz('gust', { ...vorlagen.wandern.metrics.gust, alarm_ab: 'never' }, eig.gust);
		assert.equal(nie.art, 'nie');
		pruefeKatalogModell(nie, 'Erklaersatz nie');
		const vorbote = m.erklaersatz('humidity', vorlagen.wandern.metrics.humidity, eig.humidity);
		assert.equal(vorbote.art, 'vorbote');
		pruefeKatalogModell(vorbote, 'Erklaersatz Vorbote');
		const anzeige = m.erklaersatz('wind_direction', vorlagen.wandern.metrics.wind_direction, eig.wind_direction);
		assert.equal(anzeige.art, 'anzeige');
		pruefeKatalogModell(anzeige, 'Erklaersatz Anzeige');
		const ohne = m.erklaersatz('gust', { enabled: true, alarm_ab: 'orange', lower: {}, upper: { yellow: null, orange: null, red: null } }, eig.gust);
		assert.equal(ohne.art, 'ohne_grenze');
		assert.deepEqual(ohne.werte, { stufe: 'orange' });
		pruefeKatalogModell(ohne, 'Erklaersatz ohne Grenze');
	});

	test('ac18_gewitter_wassersport_alarm_ab_rot_steigt_auf_mittel', async () => {
		const { m, vorlagen, eig } = await umgebung();
		const v = vorlagen.wassersport;
		const s = m.erklaersatz('thunder', { ...v.metrics.thunder, alarm_ab: 'red' }, eig.thunder, v.thunder);
		assert.equal(s.art, 'gewitter');
		// #2955 AC-2: greift schon „mittel“, lautet das Token `mittel_ab` („mittel oder hoch“).
		assert.deepEqual(s.werte, { gewitter_stufe: 'mittel_ab', stufe: 'red' });
		pruefeKatalogModell(s, 'Erklaersatz Gewitter');
	});

	test('ac18_gewitter_allgemein_alarm_ab_rot_steigt_auf_hoch', async () => {
		const { m, vorlagen, eig } = await umgebung();
		const v = vorlagen.allgemein;
		const s = m.erklaersatz('thunder', { ...v.metrics.thunder, alarm_ab: 'red' }, eig.thunder, v.thunder);
		assert.deepEqual(s.werte, { gewitter_stufe: 'hoch', stufe: 'red' });
	});

	test('ac18_gewitter_farben_erreichen_stufe_nie', async () => {
		const { m, vorlagen, eig } = await umgebung();
		const s = m.erklaersatz('thunder', { ...vorlagen.allgemein.metrics.thunder, alarm_ab: 'red' }, eig.thunder, { mittel: 'yellow', hoch: 'orange' });
		assert.equal(s.art, 'gewitter_nie');
		assert.deepEqual(s.werte, { stufe: 'red' });
		pruefeKatalogModell(s, 'Erklaersatz Gewitter nie');
	});
});

// ── AC-15: Gruppen ───────────────────────────────────────────────────────────

describe('AC-15: Metrik-Zeilen in fuenf Gruppen (aus /api/metrics), keine CAPE-Zeile', () => {
	test('ac15_gruppen_feste_folge_nur_belegte_unbekannte_fallen_weg', async () => {
		const { m, vorlagen, eig } = await umgebung();
		const auswahl = [...enabledIds(vorlagen['alpen-trekking']), 'cape', 'gibt_es_nicht'];
		const g = m.zeilenGruppen(auswahl, eig) as Array<{ gruppe: string; metriken: string[] }>;
		const folge = g.map((x) => x.gruppe);
		assert.deepEqual(folge, GRUPPEN_FOLGE.filter((x) => folge.includes(x)), `Gruppenfolge ${folge.join(',')}`);
		for (const x of g) {
			assert.ok(x.metriken.length > 0, `leere Gruppe ${x.gruppe}`);
			for (const id of x.metriken) assert.equal(eig[id].group, x.gruppe, `${id} in falscher Gruppe ${x.gruppe}`);
		}
		const alle = g.flatMap((x) => x.metriken);
		assert.ok(!alle.includes('cape'), 'CAPE-Zeile vorhanden');
		assert.ok(!alle.includes('gibt_es_nicht'), 'unbekannte Metrik als Zeile');
		assert.deepEqual([...alle].sort(), enabledIds(vorlagen['alpen-trekking']));
	});
});

// ── AC-37/AC-39: Auswahl-Ableitung und Fallbacks ─────────────────────────────

describe('AC-37/AC-39: Auswahl lesen', () => {
	test('ac37_aktive_metriken_aus_aufgeloester_ampel', async () => {
		const { m, vorlagen } = await umgebung();
		for (const id of Object.keys(vorlagen)) {
			const a = aufgeloest({ ampel: { template: id } });
			assert.deepEqual([...m.aktiveMetriken(a)].sort(), enabledIds(vorlagen[id]), `Vorlage ${id}`);
		}
	});

	test('ac37_trip_auswahl_aus_metrics_enabled_in_listenreihenfolge', async () => {
		const { m, vorlagen } = await umgebung();
		const a = aufgeloest({ ampel: { template: 'allgemein' } });
		const dc = { metrics: [{ metric_id: 'wind', enabled: true }, { metric_id: 'gust', enabled: false }, { metric_id: 'humidity', enabled: true }] };
		assert.deepEqual(m.auswahlLesen('route', dc, a), ['wind', 'humidity'], 'Trip liest metrics[], nicht die Ampel');
	});

	test('ac37_vergleich_auswahl_aus_active_metrics_eindeutig_in_reihenfolge', async () => {
		const { m, vorlagen } = await umgebung();
		const a = aufgeloest({ ampel: { template: 'allgemein' } });
		const dc = {
			active_metrics: [
				{ metric_id: 'temperature', aggregation: 'max' },
				{ metric_id: 'temperature', aggregation: 'min' },
				{ metric_id: 'gust', aggregation: 'max' }
			]
		};
		assert.deepEqual(m.auswahlLesen('vergleich', dc, a), ['temperature', 'gust']);
	});

	test('ac39_vergleich_ohne_active_metrics_liest_aufgeloeste_ampel', async () => {
		const { m, vorlagen } = await umgebung();
		const a = aufgeloest({ ampel: { template: 'wandern', metrics: { dewpoint: { enabled: true } } } });
		for (const dc of [{}, undefined, null, { ampel: { template: 'wandern' } }]) {
			const aus = m.auswahlLesen('vergleich', dc, a);
			assert.ok(aus.length > 0, `AC-39: leere Auswahl bei display_config=${JSON.stringify(dc)}`);
			assert.deepEqual([...aus].sort(), [...enabledIds(vorlagen.wandern), 'dewpoint'].sort());
		}
	});

	test('ac39_vergleich_bewusst_leere_active_metrics_bleibt_leer', async () => {
		const { m, vorlagen } = await umgebung();
		assert.deepEqual(m.auswahlLesen('vergleich', { active_metrics: [] }, aufgeloest({ ampel: { template: 'allgemein' } })), []);
	});

	test('ac39_eigene_vorlage_ohne_ampel_nutzt_allgemein_mit_enabled_aus_metriken', async () => {
		const { m, vorlagen } = await umgebung();
		const preset = { name: 'Alt', metrics: [
			{ metric_id: 'wind', enabled: true, use_friendly_format: false },
			{ metric_id: 'humidity', enabled: true, use_friendly_format: false },
			{ metric_id: 'gust', enabled: false, use_friendly_format: false }
		] };
		// #2988 S4: der Altbestand wird vom Server aufgeloest (Eintrag nur mit `metrics`, wie eintragAusVorlage).
		const a = aufgeloest({ metrics: preset.metrics.map((x) => ({ metric_id: x.metric_id, enabled: x.enabled })) });
		assert.deepEqual([...m.aktiveMetriken(a)].sort(), ['humidity', 'wind']);
		assert.deepEqual(ohneOffene(a).metrics.gust.upper, ohneOffene(vorlagen.allgemein).metrics.gust.upper, 'Grenzen nicht aus „allgemein“');
		assert.equal(a.metrics.gust.alarm_ab, vorlagen.allgemein.metrics.gust.alarm_ab);
		assert.deepEqual(a.thunder, vorlagen.allgemein.thunder);
		// Abweichungen zaehlen gegen DIESE Ableitung, nicht gegen „allgemein“
		const mit = (id: string, enabled: boolean) => ({ ...a, metrics: { ...a.metrics, [id]: { ...a.metrics[id], enabled } } });
		assert.equal(await abweichungen(a, mit('wind', true)), 0);
		assert.equal(await abweichungen(a, mit('gust', true)), 1);
		assert.equal(await abweichungen(a, mit('temperature', false)), 0, 'temperature ist in der Ableitung aus');
	});

	test('ac39_eigene_vorlage_mit_ampel_wird_aufgeloest', async () => {
		const { vorlagen } = await umgebung();
		const a = aufgeloest({ ampel: { template: 'wandern', metrics: { gust: { alarm_ab: 'red' } } } });
		assert.equal(a.metrics.gust.alarm_ab, 'red');
		assert.deepEqual(ohneOffene(a).metrics.wind, ohneOffene(vorlagen.wandern).metrics.wind);
	});
});

// ── AC-14: „Alarm ab fuer alle“ und Zaehler-Modell ───────────────────────────

describe('AC-14: „Alarm ab fuer alle“ wirkt nur auf gewaehlte alarmfaehige Metriken', () => {
	test('ac14_alarm_ab_fuer_alle_rot', async () => {
		const { m, vorlagen, eig } = await umgebung();
		const vorlage = vorlagen.wandern;
		const auswahl = [...enabledIds(vorlage), 'wind_direction'];
		const vorher = aufgeloest({ ampel: { template: 'wandern' } });
		const nachher = m.alarmAbFuerAlle(vorher, auswahl, 'red', eig);
		let geaendert = 0;
		for (const [id, e] of Object.entries(nachher.metrics as Record<string, Json>)) {
			const gewaehltUndFaehig = auswahl.includes(id) && eig[id]?.alertable === true;
			if (gewaehltUndFaehig) {
				assert.equal(e.alarm_ab, 'red', `${id}: nicht auf Rot gestellt`);
				if (vorlage.metrics[id].alarm_ab !== 'red') geaendert++;
			} else {
				assert.equal(e.alarm_ab, vorher.metrics[id].alarm_ab, `${id}: nicht alarmfaehig oder nicht gewaehlt, wurde aber geaendert`);
			}
		}
		assert.ok(geaendert > 0, 'Messaufbau: nichts geaendert');
		assert.equal(await abweichungen(vorlage, nachher), geaendert, 'AC-14: jede geaenderte Metrik zaehlt als eine Abweichung');
		assert.equal(vorher.metrics.gust.alarm_ab, 'orange', 'alarmAbFuerAlle mutiert die Eingabe');
	});

	test('ac14_alarm_ab_fuer_alle_gelb_laesst_gewitter_nie_gelb', async () => {
		const { m, vorlagen, eig } = await umgebung();
		const a = m.alarmAbFuerAlle(aufgeloest({ ampel: { template: 'wandern' } }), enabledIds(vorlagen.wandern), 'yellow', eig);
		assert.equal(a.metrics.gust.alarm_ab, 'yellow');
		assert.notEqual(a.metrics.thunder.alarm_ab, 'yellow', 'Gewitter darf nie „Alarm ab Gelb“ bekommen');
		// Der Server nimmt das Ergebnis an (eine ungueltige Ampel ignoriert er, dann stuende Boeen auf der Vorlage).
		const r = aufgeloest({ ampel: a });
		assert.equal(r.metrics.gust.alarm_ab, 'yellow', 'Ergebnis waere serverseitig ungueltig');
		assert.equal(r.metrics.thunder.alarm_ab, a.metrics.thunder.alarm_ab, 'Ergebnis waere serverseitig ungueltig');
	});

	test('ac14_zaehler_x_von_y_z_ohne', async () => {
		const { m, vorlagen, eig } = await umgebung();
		const auswahl = [...enabledIds(vorlagen.wandern), 'wind_direction'];
		const a = m.alarmAbFuerAlle(aufgeloest({ ampel: { template: 'wandern' } }), auswahl, 'orange', eig);
		const faehig = auswahl.filter((id) => eig[id].alertable);
		const z = m.alarmZaehler(a, auswahl, eig);
		assert.equal(z.art, 'zaehler');
		// #2955 AC-5: zweite Zahl = alle ausgewaehlten Metriken.
		assert.deepEqual(z.werte, { ausloesend: faehig.length, ausgewaehlt: auswahl.length, ohne: auswahl.length - faehig.length });
		pruefeKatalogModell(z, 'Alarm-Zaehler');
	});

	test('ac14_zaehler_nie_zaehlt_nicht_als_ausloesend', async () => {
		const { m, vorlagen, eig } = await umgebung();
		const auswahl = ['gust', 'wind', 'humidity'];
		const a = m.alarmAbFuerAlle(aufgeloest({ ampel: { template: 'wandern' } }), auswahl, 'never', eig);
		const z = m.alarmZaehler(a, auswahl, eig);
		assert.equal(z.art, 'zaehler');
		assert.deepEqual(z.werte, { ausloesend: 0, ausgewaehlt: 3, ohne: 1 }); // #2955 AC-5
	});

	test('ac14_nur_vorboten_ergibt_keine_alarmfaehige_metrik', async () => {
		const { m, vorlagen, eig } = await umgebung();
		const z = m.alarmZaehler(aufgeloest({ ampel: { template: 'wandern' } }), ['humidity', 'rain_probability'], eig);
		assert.equal(z.art, 'keine_alarmfaehig');
		pruefeKatalogModell(z, 'Alarm-Zaehler keine alarmfaehige');
		assert.equal(
			wetterKatalog('de')[z.schluessel],
			'Keine der gewählten Metriken kann einen Alarm auslösen. Nimm z.B. Wind, Böen oder Gewitter dazu.'
		);
	});
});

// ── AC-12: Zuruecksetzen ─────────────────────────────────────────────────────

describe('AC-12: Zuruecksetzen auf die Vorlage ergibt 0 Abweichungen', () => {
	for (const id of ['alpen-trekking', 'wandern', 'wassersport', 'allgemein']) {
		test(`ac12_zuruecksetzen_${id}`, async () => {
			const { m, vorlagen } = await umgebung();
			const r = m.zuruecksetzen(id, vorlagen);
			assert.deepEqual(ohneOffene(r.ampel), ohneOffene(aufgeloest({ ampel: { template: id } })));
			assert.deepEqual([...r.auswahl].sort(), enabledIds(vorlagen[id]));
			assert.equal(await abweichungen(vorlagen[id], r.ampel), 0);
		});
	}
});

// ── #2946: Sichtweite-Einheit (Grenzwerte in Meter, Anzeige-Einheit km nur fuer Layout) ──
// Spec: docs/specs/modules/fix_2946_sichtweite_einheit.md — AC-1, AC-3, AC-5, AC-6, AC-7
// Eingabe ist die echte Python-Antwort von /api/metrics (live()), keine handgeschriebene Eigenschaft.

describe('#2946: Sichtweite-Zeile nennt die Einheit der Grenzwerte (m), nicht die Anzeige-Einheit (km)', () => {
	const nachId = (): Record<string, Json> => {
		const aus: Record<string, Json> = {};
		for (const liste of Object.values(live().metrics) as Json[][]) for (const k of liste) aus[k.id] = k;
		return aus;
	};

	test('ac6_api_visibility_unit_km_threshold_unit_m', () => {
		const v = nachId().visibility;
		assert.equal(v.unit, 'km', 'AC-4: Anzeige-Einheit fuer Layout/Mail bleibt km');
		assert.equal(v.threshold_unit, 'm', 'AC-6: /api/metrics liefert threshold_unit=m fuer visibility');
	});

	test('ac15_gruen_nur_unten_visibility_aus_vorlage_ab_2000_m', async () => {
		const { m, vorlagen, eig } = await umgebung();
		const z = m.gruenZeile(vorlagen.wandern.metrics.visibility, eig.visibility);
		assert.equal(z.art, 'ab');
		assert.deepEqual(z.werte, { ab: 2000, einheit: 'm' }, 'vorher festgeschrieben als km (Fehler #2946)');
		pruefeKatalogModell(z, 'gruenZeile nur_unten');
	});

	test('ac1_gruenzeile_visibility_ab_1000_m', async () => {
		const { m, eig } = await umgebung();
		const z = m.gruenZeile({ lower: { yellow: 1000, orange: 500, red: 300 } }, eig.visibility);
		assert.equal(z.art, 'ab');
		assert.deepEqual(z.werte, { ab: 1000, einheit: 'm' }, 'AC-1: „gruen: ab 1000 m“, nicht km');
	});

	test('ac1_ac3_untertitel_visibility_m_minimum_in_de_und_en', async () => {
		const { m, eig } = await umgebung();
		const de = m.untertitel('visibility', eig.visibility, () => 'Minimum');
		const en = m.untertitel('visibility', eig.visibility, () => 'minimum');
		assert.equal(de, 'm · Minimum', `AC-1: Untertitel DE „${de}“`);
		assert.equal(en, 'm · minimum', `AC-3: Untertitel EN „${en}“ (Einheiten-Token sprachneutral)`);
		assert.ok(!de.includes('km') && !en.includes('km'));
	});

	test('ac1_erklaersatz_visibility_unter_300_m', async () => {
		const { m, eig } = await umgebung();
		const s = m.erklaersatz('visibility', { enabled: true, alarm_ab: 'red', lower: { yellow: 1000, orange: 500, red: 300 } }, eig.visibility);
		assert.equal(s.art, 'normal');
		assert.equal(s.werte.unten, 300);
		assert.equal(s.werte.einheit, 'm', 'AC-1: Erklaersatz „unter 300 m“, nicht km');
	});

	test('ac5_metriken_ohne_display_unit_unveraendert', async () => {
		const { m, eig } = await umgebung();
		const katalog = nachId();
		let geprueft = 0;
		for (const [id, k] of Object.entries(katalog)) {
			if (id === 'visibility') continue;
			assert.equal(k.threshold_unit, k.unit, `AC-5/AC-6: ${id} threshold_unit == unit`);
			const z = m.gruenZeile({ lower: { yellow: 1 } }, eig[id]);
			assert.equal(z.werte.einheit, k.unit, `AC-5: ${id} Gruenzeile-Einheit unveraendert`);
			geprueft++;
		}
		assert.ok(geprueft >= 10, 'Messaufbau: zu wenige Metriken im Katalog');
	});

	test('ac7_aeltere_antwort_ohne_threshold_unit_faellt_auf_unit_zurueck', async () => {
		const { m } = await umgebung();
		const alt = structuredClone(live().metrics) as Record<string, Json[]>;
		for (const liste of Object.values(alt)) for (const k of liste) delete k.threshold_unit;
		const eig = m.eigenschaftenAusKatalog(alt);
		const z = m.gruenZeile({ lower: { yellow: 1000 } }, eig.visibility);
		assert.equal(z.werte.einheit, 'km', 'AC-7: ohne threshold_unit gilt unit (Rueckfall)');
		assert.equal(m.untertitel('temperature', eig.temperature, () => 'x'), '°C · x', 'AC-7: keine leere Einheit');
	});

	test('ac7_eigenschaften_ohne_threshold_unit_direkt_einheit_ist_unit', async () => {
		// Direkt an gruenZeile/untertitel/erklaersatz, OHNE den Rueckfall in eigenschaftenAusKatalog:
		// die Rueckfall-Stufe in der Grenz-Einheit selbst muss greifen (Adversary F001).
		const { m, eig } = await umgebung();
		const ohne = structuredClone(eig.temperature) as Json;
		delete ohne.threshold_unit;
		assert.equal(ohne.unit, '°C', 'Messaufbau: temperature hat unit °C');
		assert.equal(ohne.alertable, true, 'Messaufbau: temperature ist alarmfaehig');
		assert.ok(!('threshold_unit' in ohne), 'Messaufbau: threshold_unit fehlt');

		const z = m.gruenZeile({ lower: { yellow: 0 }, upper: { yellow: 30 } }, ohne);
		assert.equal(z.werte.einheit, '°C', 'AC-7: Gruenzeile ohne threshold_unit nennt unit');
		assert.equal(m.untertitel('temperature', ohne, () => 'x'), '°C · x', 'AC-7: Untertitel ohne threshold_unit nennt unit');
		const s = m.erklaersatz('temperature', { enabled: true, alarm_ab: 'red', upper: { yellow: 30, orange: 33, red: 36 } }, ohne);
		assert.equal(s.art, 'normal');
		assert.equal(s.werte.einheit, '°C', 'AC-7: Erklaersatz ohne threshold_unit nennt unit');
	});
});
