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
//   vorlageIdVon(abo, vorlagen)                      -> string  (abo.template, unbekannt/fehlt -> 'allgemein')
//   verschmelzen(vorlage: Ampel, abo?: Ampel|null)   -> Ampel   (Spiegel app.ampel._verschmelzen, mutiert nichts)
//   zaehleAbweichungen(abo, vorlagen)                -> number  (Spiegel deviation_count; siehe Paritaets-Test)
//   zaehleAbweichungenGegen(vorlage: Ampel, abo)     -> number  (gleiche Zaehlung gegen eine gegebene Vorlagen-Ampel)
//   ampelFehler(ampel)                               -> string[] (leer = gueltig; Regelgleichheit validate_ampel)
//   grenzenFehler({lower, upper})                    -> string[] Katalogschluessel wetter.* (AC-17)
//   gewitterFarben('mittel'|'hoch')                  -> Farbe[]  (mittel: gelb·orange·rot, hoch: orange·rot)
//   gewitterFehler(thunder)                          -> string[] (leer = gueltig)
//   alarmAbOptionen(id, eig)                         -> AlarmAb[] (Gewitter ohne 'yellow'; nicht alarmfaehig -> [])
//   gruenZeile(eintrag, eig)                         -> {art: 'von_bis'|'ab'|'bis'|'immer', schluessel, werte}
//   erklaersatz(id, eintrag, eig, thunder?)          -> {art: 'normal'|'gewitter'|'gewitter_nie'|'nie'|'vorbote'|'anzeige'|'ohne_grenze', schluessel, werte}
//   zeilenGruppen(auswahl, eig)                      -> {gruppe, metriken: string[]}[] (feste Gruppenfolge, nur belegte, unbekannte Ids fallen weg)
//   aktiveMetriken(aufgeloest)                       -> string[] (enabled === true)
//   auswahlLesen(context, displayConfig, aufgeloest) -> string[] (Trip: metrics[].enabled; Vergleich: active_metrics, fehlt -> aus Ampel)
//   eigeneVorlageAmpel(preset, vorlagen)             -> Ampel (vollstaendig; ohne ampel: 'allgemein' mit enabled aus preset.metrics)
//   alarmAbFuerAlle(ampel, auswahl, stufe, eig)      -> Ampel (nur gewaehlte alarmfaehige Metriken; Gewitter nie 'yellow')
//   alarmZaehler(ampel, auswahl, eig)                -> {art: 'zaehler'|'keine_alarmfaehig', schluessel, werte}
//   zuruecksetzen(vorlageId, vorlagen)               -> {ampel: Ampel (aufgeloest), auswahl: string[]}
//
// RED heute: ampelModell.ts und der Katalog wetter.json existieren nicht.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/ampelModell.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { ampelModell, fixture, live, ohneOffene, pruefeKatalogModell, pythonAufloesen, wetterKatalog, type Json } from './wetterTabDaten.ts';

const GRUPPEN_FOLGE = ['temperature', 'wind', 'precip_thunder', 'sky_visibility', 'snow_height'];

async function umgebung(): Promise<{ m: Json; vorlagen: Json; eig: Json }> {
	const m = await ampelModell();
	const daten = live();
	return { m, vorlagen: m.vorlagenAusTemplates(daten.templates), eig: m.eigenschaftenAusKatalog(daten.metrics) };
}

const enabledIds = (ampel: Json): string[] =>
	Object.entries(ampel.metrics as Record<string, Json>).filter(([, e]) => e.enabled === true).map(([id]) => id).sort();

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

	test('vorlageIdVon: template bekannt -> template, unbekannt/fehlt -> allgemein', async () => {
		const { m, vorlagen } = await umgebung();
		assert.equal(m.vorlageIdVon({ template: 'wandern' }, vorlagen), 'wandern');
		assert.equal(m.vorlageIdVon({ template: 'gibt-es-nicht' }, vorlagen), 'allgemein');
		assert.equal(m.vorlageIdVon(null, vorlagen), 'allgemein');
		assert.equal(m.vorlageIdVon({}, vorlagen), 'allgemein');
	});
});

// ── Aufloesung: Spiegel von _verschmelzen ────────────────────────────────────

describe('Aufloesung Vorlage -> Abo = Python resolve_ampel', () => {
	test('verschmelzen ergibt fuer alle Fixture-Faelle dieselbe Ampel wie resolve_ampel', async () => {
		const { m, vorlagen } = await umgebung();
		const faelle = (fixture('ampel_deviation_cases.json').cases as Json[]).filter((f) => f.ampel !== null);
		const soll = pythonAufloesen(faelle.map((f) => f.ampel));
		faelle.forEach((f, i) => {
			const ist = m.verschmelzen(vorlagen[m.vorlageIdVon(f.ampel, vorlagen)], structuredClone(f.ampel));
			assert.deepEqual(ohneOffene(ist), ohneOffene(soll[i]), `Fall ${f.name}: Aufloesung weicht von resolve_ampel ab`);
		});
	});

	test('verschmelzen: offene Seite (null) im Abo heisst „keine Grenze“, mutiert die Vorlage nicht', async () => {
		const { m, vorlagen } = await umgebung();
		const vorher = JSON.stringify(vorlagen.wandern);
		const r = m.verschmelzen(vorlagen.wandern, { template: 'wandern', metrics: { gust: { upper: null } } });
		assert.deepEqual(ohneOffene(r).metrics.gust.upper, {});
		assert.equal(JSON.stringify(vorlagen.wandern), vorher, 'verschmelzen mutiert die Vorlage');
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

	test('ac17_regelgleich_mit_python_und_go_ueber_gemeinsame_vektoren', async () => {
		const { m } = await umgebung();
		for (const v of fixture('ampel_validierung_vektoren.json').vektoren as Json[]) {
			const f = m.ampelFehler(structuredClone(v.ampel));
			assert.equal(f.length === 0, v.gueltig, `Vektor ${v.name}: Frontend ${f.length === 0 ? 'gueltig' : 'ungueltig'} (${JSON.stringify(f)}), erwartet ${v.gueltig}`);
		}
	});
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
		['nur_unten', 'visibility', (v) => v.wandern.metrics.visibility, 'ab', { ab: 2000, einheit: 'km' }],
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
		assert.deepEqual(s.werte, { gewitter_stufe: 'mittel', stufe: 'red' });
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
			const a = m.verschmelzen(vorlagen[id], null);
			assert.deepEqual([...m.aktiveMetriken(a)].sort(), enabledIds(vorlagen[id]), `Vorlage ${id}`);
		}
	});

	test('ac37_trip_auswahl_aus_metrics_enabled_in_listenreihenfolge', async () => {
		const { m, vorlagen } = await umgebung();
		const a = m.verschmelzen(vorlagen.allgemein, null);
		const dc = { metrics: [{ metric_id: 'wind', enabled: true }, { metric_id: 'gust', enabled: false }, { metric_id: 'humidity', enabled: true }] };
		assert.deepEqual(m.auswahlLesen('route', dc, a), ['wind', 'humidity'], 'Trip liest metrics[], nicht die Ampel');
	});

	test('ac37_vergleich_auswahl_aus_active_metrics_eindeutig_in_reihenfolge', async () => {
		const { m, vorlagen } = await umgebung();
		const a = m.verschmelzen(vorlagen.allgemein, null);
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
		const a = m.verschmelzen(vorlagen.wandern, { template: 'wandern', metrics: { dewpoint: { enabled: true } } });
		for (const dc of [{}, undefined, null, { ampel: { template: 'wandern' } }]) {
			const aus = m.auswahlLesen('vergleich', dc, a);
			assert.ok(aus.length > 0, `AC-39: leere Auswahl bei display_config=${JSON.stringify(dc)}`);
			assert.deepEqual([...aus].sort(), [...enabledIds(vorlagen.wandern), 'dewpoint'].sort());
		}
	});

	test('ac39_vergleich_bewusst_leere_active_metrics_bleibt_leer', async () => {
		const { m, vorlagen } = await umgebung();
		assert.deepEqual(m.auswahlLesen('vergleich', { active_metrics: [] }, m.verschmelzen(vorlagen.allgemein, null)), []);
	});

	test('ac39_eigene_vorlage_ohne_ampel_nutzt_allgemein_mit_enabled_aus_metriken', async () => {
		const { m, vorlagen } = await umgebung();
		const preset = { name: 'Alt', metrics: [
			{ metric_id: 'wind', enabled: true, use_friendly_format: false },
			{ metric_id: 'humidity', enabled: true, use_friendly_format: false },
			{ metric_id: 'gust', enabled: false, use_friendly_format: false }
		] };
		const a = m.eigeneVorlageAmpel(preset, vorlagen);
		assert.deepEqual([...m.aktiveMetriken(a)].sort(), ['humidity', 'wind']);
		assert.deepEqual(ohneOffene(a).metrics.gust.upper, ohneOffene(vorlagen.allgemein).metrics.gust.upper, 'Grenzen nicht aus „allgemein“');
		assert.equal(a.metrics.gust.alarm_ab, vorlagen.allgemein.metrics.gust.alarm_ab);
		assert.deepEqual(a.thunder, vorlagen.allgemein.thunder);
		// Abweichungen zaehlen gegen DIESE Ableitung, nicht gegen „allgemein“
		assert.equal(m.zaehleAbweichungenGegen(a, { metrics: { wind: { enabled: true } } }), 0);
		assert.equal(m.zaehleAbweichungenGegen(a, { metrics: { gust: { enabled: true } } }), 1);
		assert.equal(m.zaehleAbweichungenGegen(a, { metrics: { temperature: { enabled: false } } }), 0, 'temperature ist in der Ableitung aus');
	});

	test('ac39_eigene_vorlage_mit_ampel_wird_aufgeloest', async () => {
		const { m, vorlagen } = await umgebung();
		const a = m.eigeneVorlageAmpel({ name: 'Neu', metrics: [], ampel: { template: 'wandern', metrics: { gust: { alarm_ab: 'red' } } } }, vorlagen);
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
		const vorher = m.verschmelzen(vorlage, null);
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
		assert.equal(m.zaehleAbweichungenGegen(vorlage, nachher), geaendert, 'AC-14: jede geaenderte Metrik zaehlt als eine Abweichung');
		assert.equal(vorher.metrics.gust.alarm_ab, 'orange', 'alarmAbFuerAlle mutiert die Eingabe');
	});

	test('ac14_alarm_ab_fuer_alle_gelb_laesst_gewitter_nie_gelb', async () => {
		const { m, vorlagen, eig } = await umgebung();
		const a = m.alarmAbFuerAlle(m.verschmelzen(vorlagen.wandern, null), enabledIds(vorlagen.wandern), 'yellow', eig);
		assert.equal(a.metrics.gust.alarm_ab, 'yellow');
		assert.notEqual(a.metrics.thunder.alarm_ab, 'yellow', 'Gewitter darf nie „Alarm ab Gelb“ bekommen');
		assert.deepEqual(m.ampelFehler(a), [], 'Ergebnis waere serverseitig ungueltig');
	});

	test('ac14_zaehler_x_von_y_z_ohne', async () => {
		const { m, vorlagen, eig } = await umgebung();
		const auswahl = [...enabledIds(vorlagen.wandern), 'wind_direction'];
		const a = m.alarmAbFuerAlle(m.verschmelzen(vorlagen.wandern, null), auswahl, 'orange', eig);
		const faehig = auswahl.filter((id) => eig[id].alertable);
		const z = m.alarmZaehler(a, auswahl, eig);
		assert.equal(z.art, 'zaehler');
		assert.deepEqual(z.werte, { ausloesend: faehig.length, alarmfaehig: faehig.length, ohne: auswahl.length - faehig.length });
		pruefeKatalogModell(z, 'Alarm-Zaehler');
	});

	test('ac14_zaehler_nie_zaehlt_nicht_als_ausloesend', async () => {
		const { m, vorlagen, eig } = await umgebung();
		const auswahl = ['gust', 'wind', 'humidity'];
		const a = m.alarmAbFuerAlle(m.verschmelzen(vorlagen.wandern, null), auswahl, 'never', eig);
		const z = m.alarmZaehler(a, auswahl, eig);
		assert.equal(z.art, 'zaehler');
		assert.deepEqual(z.werte, { ausloesend: 0, alarmfaehig: 2, ohne: 1 });
	});

	test('ac14_nur_vorboten_ergibt_keine_alarmfaehige_metrik', async () => {
		const { m, vorlagen, eig } = await umgebung();
		const z = m.alarmZaehler(m.verschmelzen(vorlagen.wandern, null), ['humidity', 'rain_probability'], eig);
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
			assert.deepEqual(ohneOffene(r.ampel), ohneOffene(m.verschmelzen(vorlagen[id], null)));
			assert.deepEqual([...r.auswahl].sort(), enabledIds(vorlagen[id]));
			assert.equal(m.zaehleAbweichungenGegen(vorlagen[id], r.ampel), 0);
			assert.equal(m.zaehleAbweichungen({ ...r.ampel, template: id }, vorlagen), 0);
		});
	}
});
