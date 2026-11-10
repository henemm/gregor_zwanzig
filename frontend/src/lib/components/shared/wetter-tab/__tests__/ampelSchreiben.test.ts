// TDD RED — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter), Speicher-Payloads `ampelSchreiben.ts`.
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md — AC-11, AC-12, AC-37, AC-38, AC-39 (+ AC-20, AC-21 Felder)
//
// Der Reiter schreibt die Auswahl in ZWEI Quellen konsistent (Implementation Details §2):
//   - `metrics[]` (Trip) bzw. `active_metrics` (Orts-Briefing) als vollstaendige Liste
//     (Reihenfolge der bestehenden Liste, neu hinzugefuegte Metriken hinten),
//   - `ampel` als VOLLSTAENDIGE minimale Abweichungsmenge gegen die gewaehlte Vorlage
//     (der Server ersetzt `ampel` als Ganzes, mergeConfigMap), mit `ampel.metrics.<id>.enabled`
//     NUR dort, wo die Auswahl von der Vorlage abweicht.
// Vorlagenwechsel/Zuruecksetzen ersetzen Auswahl, Grenzen, Alarmstufen und lassen Zustellung,
// Etappen und Orte unberuehrt. Tagesfenster: Trip in `report_config`, Orts-Briefing top-level.
//
// Festgelegte API (ampelSchreiben.ts), Typen aus ampelModell.ts:
//   abweichungsMenge(vorlage: Ampel, aufgeloest: Ampel, auswahl: string[]): Ampel
//       {template: vorlage.template, metrics?: nur abweichende Felder je Metrik, thunder?: nur abweichende Farben}
//   tripSpeicherPayload({vorlage, aufgeloest, auswahl, displayConfig, reportConfig, warnFelder, warnungenAn, tagesfenster: {start, end}})
//       -> { weatherConfig: {ampel, metrics, ...unveraenderte display_config-Schluessel erlaubt},   // PUT /api/trips/{id}/weather-config
//            tripFelder: {official_alerts_enabled, official_warnings, report_config} }             // Trip-Felder (siehe Befund im Bericht)
//   vergleichSpeicherPayload({vorlage, aufgeloest, auswahl, displayConfig, aggregationFuer, warnFelder, warnungenAn, radarAn, tagesfenster})
//       -> { display_config: {...displayConfig, ampel, active_metrics}, official_alerts_enabled, official_warnings,
//            radar_alert_enabled, day_window_start_hour, day_window_end_hour }                     // enqueueHubWrite (PUT /api/compare/presets/{id})
//
// RED heute: ampelSchreiben.ts / ampelModell.ts existieren nicht.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/ampelSchreiben.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { ampelModell, ampelSchreiben, amtlicheWarnungen, live, ohneOffene, type Json } from './wetterTabDaten.ts';

async function umgebung(): Promise<{ m: Json; s: Json; w: Json; vorlagen: Json; eig: Json }> {
	const m = await ampelModell();
	const s = await ampelSchreiben();
	const w = await amtlicheWarnungen();
	const daten = live();
	return { m, s, w, vorlagen: m.vorlagenAusTemplates(daten.templates), eig: m.eigenschaftenAusKatalog(daten.metrics) };
}

const enabledIds = (ampel: Json): string[] =>
	Object.entries(ampel.metrics as Record<string, Json>).filter(([, e]) => e.enabled === true).map(([id]) => id).sort();

const sortiert = (a: string[]) => [...a].sort();

/** Jeder Eintrag der Menge ist eine echte Abweichung (sonst ist sie nicht minimal). */
function pruefeMinimal(m: Json, vorlage: Json, menge: Json, wo: string): void {
	assert.equal(menge.template, vorlage.template, `${wo}: template fehlt oder falsch`);
	const ohne = { enabled: false, lower: {}, upper: {}, alarm_ab: 'never' };
	for (const [id, e] of Object.entries((menge.metrics ?? {}) as Record<string, Json>)) {
		const v = vorlage.metrics[id] ?? ohne;
		assert.ok(Object.keys(e).length > 0, `${wo}: leerer Eintrag ${id}`);
		for (const [k, wert] of Object.entries(e)) {
			if (k === 'lower' || k === 'upper') {
				assert.notDeepEqual(ohneOffene({ metrics: { x: { [k]: wert } } }).metrics.x[k], ohneOffene({ metrics: { x: { [k]: v[k] } } }).metrics.x[k], `${wo}: ${id}.${k} gleich der Vorlage, steht trotzdem in der Menge`);
			} else {
				assert.notDeepEqual(wert, v[k], `${wo}: ${id}.${k} gleich der Vorlage (${JSON.stringify(wert)}), steht trotzdem in der Menge`);
			}
		}
	}
	for (const [k, wert] of Object.entries((menge.thunder ?? {}) as Record<string, unknown>)) {
		assert.notEqual(wert, vorlage.thunder[k], `${wo}: thunder.${k} gleich der Vorlage`);
	}
}

// ── Abweichungsmenge ─────────────────────────────────────────────────────────

describe('AC-37/AC-38: ampel ist die vollstaendige minimale Abweichungsmenge', () => {
	test('ac37_unveraendert_nur_template', async () => {
		const { m, s, vorlagen } = await umgebung();
		for (const id of Object.keys(vorlagen)) {
			const r = m.zuruecksetzen(id, vorlagen);
			const menge = s.abweichungsMenge(vorlagen[id], r.ampel, r.auswahl);
			assert.equal(menge.template, id);
			assert.deepEqual(menge.metrics ?? {}, {}, `${id}: unveraendertes Abo schreibt Metrik-Eintraege`);
			assert.equal(menge.thunder, undefined, `${id}: unveraendertes Abo schreibt Gewitterfarben`);
		}
	});

	test('ac37_enabled_nur_bei_abweichung_von_der_vorlage', async () => {
		const { m, s, vorlagen } = await umgebung();
		const v = vorlagen.wandern;
		const r = m.zuruecksetzen('wandern', vorlagen);
		const auswahl = [...r.auswahl.filter((x: string) => x !== 'gust'), 'dewpoint'];
		const menge = s.abweichungsMenge(v, r.ampel, auswahl);
		assert.deepEqual(menge.metrics.gust, { enabled: false }, 'entfernte Metrik: nur enabled=false');
		assert.deepEqual(menge.metrics.dewpoint, { enabled: true }, 'hinzugefuegte Metrik: nur enabled=true');
		assert.equal('wind' in menge.metrics, false, 'unveraenderte Metrik steht in der Menge');
		assert.equal(m.zaehleAbweichungen(menge, vorlagen), 2);
		pruefeMinimal(m, v, menge, 'gust−/dewpoint+');
	});

	test('ac37_aufgeloeste_menge_aktiver_metriken_gleich_auswahl_ueber_alle_vorlagen', async () => {
		const { m, s, vorlagen } = await umgebung();
		for (const id of Object.keys(vorlagen)) {
			const r = m.zuruecksetzen(id, vorlagen);
			const raus = r.auswahl[0];
			const rein = Object.keys(vorlagen[id].metrics).find((x) => !r.auswahl.includes(x))!;
			const auswahl = [...r.auswahl.filter((x: string) => x !== raus), rein];
			const menge = s.abweichungsMenge(vorlagen[id], r.ampel, auswahl);
			const zurueck = m.verschmelzen(vorlagen[id], menge);
			assert.deepEqual(sortiert(m.aktiveMetriken(zurueck)), sortiert(auswahl), `${id}: aufgeloeste Auswahl ≠ Auswahlliste`);
			pruefeMinimal(m, vorlagen[id], menge, id);
		}
	});

	test('ac38_mehrere_aenderungen_stehen_alle_in_der_menge', async () => {
		const { m, s, eig, vorlagen } = await umgebung();
		const v = vorlagen['alpen-trekking'];
		const r = m.zuruecksetzen('alpen-trekking', vorlagen);
		let a = structuredClone(r.ampel);
		a.metrics.gust.upper = { yellow: 36, orange: 50, red: 70 };
		a = m.alarmAbFuerAlle(a, ['uv_index'], 'red', eig);
		a.thunder = { ...a.thunder, mittel: 'red' };
		const menge = s.abweichungsMenge(v, a, r.auswahl);
		assert.deepEqual(ohneOffene(menge).metrics.gust, { lower: {}, upper: { yellow: 36, orange: 50, red: 70 } });
		assert.deepEqual(menge.metrics.uv_index, { alarm_ab: 'red' });
		assert.deepEqual(menge.thunder, { mittel: 'red' });
		assert.equal(m.zaehleAbweichungen(menge, vorlagen), 3, 'AC-11-Ausgang: 3 Abweichungen von Alpen-Trekking');
		const zurueck = m.verschmelzen(v, menge);
		assert.deepEqual(ohneOffene(zurueck), ohneOffene({ ...a, template: 'alpen-trekking' }), 'Menge ergibt aufgeloest nicht den Bearbeitungsstand');
	});

	test('ac38_offene_seite_wird_als_null_gesendet', async () => {
		const { m, s, vorlagen } = await umgebung();
		const r = m.zuruecksetzen('wandern', vorlagen);
		const a = structuredClone(r.ampel);
		a.metrics.gust.upper = { yellow: null, orange: null, red: null };
		const menge = s.abweichungsMenge(vorlagen.wandern, a, r.auswahl);
		assert.ok('upper' in menge.metrics.gust, 'geleerte Seite fehlt in der Menge — die Vorlagen-Grenze kaeme zurueck');
		const zurueck = m.verschmelzen(vorlagen.wandern, menge);
		assert.deepEqual(ohneOffene(zurueck).metrics.gust.upper, {}, 'geleerte Seite ist nach dem Aufloesen nicht offen');
	});
});

// ── Trip-Payload ─────────────────────────────────────────────────────────────

const TRIP_DC = {
	preset_name: 'wandern',
	metrics: [
		{ metric_id: 'wind', enabled: true, format_mode: 'raw', bucket: 'primary', order: 1 },
		{ metric_id: 'gust', enabled: true },
		{ metric_id: 'temperature', enabled: false, format_mode: 'scale' },
		{ metric_id: 'humidity', enabled: true, use_friendly_format: true }
	],
	channel_layouts: { email: { primary: ['wind'] } },
	metric_alert_levels: { wind: 'standard' },
	alarm_ab_migration: { version: 1 },
	ampel: { template: 'wandern', metrics: { wind: { alarm_ab: 'red' } } }
};
const TRIP_RC = { enabled: true, morning_enabled: true, morning_time: '06:00:00', evening_time: '18:00:00', send_email: true, day_window_start_hour: 4, day_window_end_hour: 19 };

async function tripFall(auswahlAenderung: (a: string[]) => string[], warnungenAn = true): Promise<{ p: Json; menge: Json; auswahl: string[]; u: Json }> {
	const u = await umgebung();
	const v = u.vorlagen.wandern;
	const aufgeloest = u.m.verschmelzen(v, TRIP_DC.ampel);
	const auswahl = auswahlAenderung(u.m.auswahlLesen('route', TRIP_DC, aufgeloest));
	const eingabe = {
		vorlage: v,
		aufgeloest,
		auswahl,
		displayConfig: structuredClone(TRIP_DC),
		reportConfig: structuredClone(TRIP_RC),
		warnFelder: { official_alerts_enabled: true, official_warnings: { enabled: false, sources: ['dwd'] } },
		warnungenAn,
		tagesfenster: { start: 6, end: 20 }
	};
	const p = u.s.tripSpeicherPayload(eingabe);
	return { p, menge: u.s.abweichungsMenge(v, aufgeloest, auswahl), auswahl, u };
}

describe('AC-37/AC-38: Trip-Payload (metrics[] + ampel + Warnungen + Tagesfenster)', () => {
	test('ac37_trip_metrics_vollstaendig_reihenfolge_bestehend_neue_hinten', async () => {
		const { p } = await tripFall((a) => [...a.filter((x) => x !== 'gust'), 'temperature', 'dewpoint']);
		const metrics = p.weatherConfig.metrics as Json[];
		const an = metrics.filter((x) => x.enabled === true).map((x) => x.metric_id);
		assert.deepEqual(sortiert(an), ['dewpoint', 'humidity', 'temperature', 'wind'], 'aktive Eintraege ≠ Auswahl');
		assert.ok(an.indexOf('wind') < an.indexOf('humidity'), 'Reihenfolge der bestehenden Liste verloren');
		assert.equal(an[an.length - 1], 'dewpoint', 'neue Metrik nicht hinten angehaengt');
		assert.ok(!metrics.some((x) => x.metric_id === 'gust' && x.enabled === true), 'entfernte Metrik weiter aktiv');
		const wind = metrics.find((x) => x.metric_id === 'wind');
		assert.deepEqual(wind, TRIP_DC.metrics[0], 'Felder der bestehenden Eintraege (format_mode, bucket, order) verloren');
		const temp = metrics.find((x) => x.metric_id === 'temperature');
		assert.equal(temp.format_mode, 'scale', 'format_mode einer wieder aufgenommenen Metrik verloren');
		const hum = metrics.find((x) => x.metric_id === 'humidity');
		assert.equal(hum.use_friendly_format, true);
		assert.equal(new Set(metrics.map((x) => x.metric_id)).size, metrics.length, 'Metrik doppelt in metrics[]');
	});

	test('ac38_trip_ampel_ist_die_abweichungsmenge', async () => {
		const { p, menge, u } = await tripFall((a) => [...a.filter((x) => x !== 'gust'), 'dewpoint']);
		assert.deepEqual(p.weatherConfig.ampel, menge);
		assert.deepEqual(p.weatherConfig.ampel.metrics.wind, { alarm_ab: 'red' }, 'bestehende Abweichung (wind Alarm ab Rot) ging verloren');
		assert.deepEqual(p.weatherConfig.ampel.metrics.gust, { enabled: false });
		const aktiv = u.m.aktiveMetriken(u.m.verschmelzen(u.vorlagen.wandern, p.weatherConfig.ampel));
		const liste = (p.weatherConfig.metrics as Json[]).filter((x) => x.enabled).map((x) => x.metric_id);
		assert.deepEqual(sortiert(aktiv), sortiert(liste), 'AC-37: Ampel-Auswahl und metrics[] laufen auseinander');
	});

	test('ac38_trip_weather_config_aendert_keine_fremden_display_config_schluessel', async () => {
		const { p } = await tripFall((a) => a);
		for (const [k, wert] of Object.entries(p.weatherConfig as Record<string, unknown>)) {
			if (k === 'ampel' || k === 'metrics') continue;
			assert.ok(k in TRIP_DC, `weatherConfig traegt fremden Schluessel ${k}`);
			assert.deepEqual(wert, (TRIP_DC as Json)[k], `display_config.${k} veraendert`);
		}
	});

	test('ac21_ac20_trip_felder_tagesfenster_in_report_config_und_warnungen_doppelt', async () => {
		const { p, u } = await tripFall((a) => a, false);
		assert.deepEqual(Object.keys(p.tripFelder).sort(), ['official_alerts_enabled', 'official_warnings', 'report_config']);
		assert.deepEqual(p.tripFelder.report_config, { ...TRIP_RC, day_window_start_hour: 6, day_window_end_hour: 20 }, 'report_config: Zustellungs-Felder veraendert oder Tagesfenster fehlt');
		assert.deepEqual(
			{ official_alerts_enabled: p.tripFelder.official_alerts_enabled, official_warnings: p.tripFelder.official_warnings },
			u.w.amtlicheWarnungenFelder(false, { official_alerts_enabled: true, official_warnings: { enabled: false, sources: ['dwd'] } })
		);
		assert.equal(p.tripFelder.official_alerts_enabled, false);
		assert.equal(p.tripFelder.official_warnings.enabled, false);
	});
});

// ── Vergleichs-Payload ───────────────────────────────────────────────────────

const VGL_DC = {
	active_metrics: [
		{ metric_id: 'temperature', aggregation: 'max' },
		{ metric_id: 'temperature', aggregation: 'min' },
		{ metric_id: 'gust', aggregation: 'max' },
		{ metric_id: 'wind', aggregation: 'avg' }
	],
	channel_active_metrics: { sms: [{ metric_id: 'wind', aggregation: 'avg' }] },
	channel_layouts: { email: { primary: ['wind'] } },
	metric_alert_levels: { gust: 'sensibel' },
	alarm_ab_migration: { version: 1 },
	region: 'Tirol',
	ampel: { template: 'allgemein', metrics: { gust: { upper: { yellow: 35, orange: 50, red: 65 } } } }
};
const AGG: Record<string, string> = { dewpoint: 'max', humidity: 'avg', visibility: 'min' };
const VGL_ERLAUBT = ['display_config', 'official_alerts_enabled', 'official_warnings', 'radar_alert_enabled', 'day_window_start_hour', 'day_window_end_hour'];

async function vergleichFall(dc: Json, auswahlAenderung: (a: string[]) => string[], radarAn = true): Promise<{ p: Json; menge: Json; u: Json; auswahl: string[] }> {
	const u = await umgebung();
	const v = u.vorlagen.allgemein;
	const aufgeloest = u.m.verschmelzen(v, dc.ampel ?? null);
	const auswahl = auswahlAenderung(u.m.auswahlLesen('vergleich', dc, aufgeloest));
	const p = u.s.vergleichSpeicherPayload({
		vorlage: v,
		aufgeloest,
		auswahl,
		displayConfig: structuredClone(dc),
		aggregationFuer: (id: string) => AGG[id] ?? 'max',
		warnFelder: { official_alerts_enabled: false, official_warnings: { enabled: true } },
		warnungenAn: true,
		radarAn,
		tagesfenster: { start: 7, end: 18 }
	});
	return { p, menge: u.s.abweichungsMenge(v, aufgeloest, auswahl), u, auswahl };
}

describe('AC-37/AC-38/AC-39: Vergleichs-Payload (active_metrics + ampel + Radar + Tagesfenster top-level)', () => {
	test('ac37_vergleich_active_metrics_bestehende_reihenfolge_entfernte_weg_neue_hinten', async () => {
		const { p } = await vergleichFall(VGL_DC, (a) => [...a.filter((x) => x !== 'gust'), 'dewpoint']);
		assert.deepEqual(p.display_config.active_metrics, [
			{ metric_id: 'temperature', aggregation: 'max' },
			{ metric_id: 'temperature', aggregation: 'min' },
			{ metric_id: 'wind', aggregation: 'avg' },
			{ metric_id: 'dewpoint', aggregation: 'max' }
		]);
	});

	test('ac38_vergleich_ampel_ist_abweichungsmenge_und_konsistent', async () => {
		const { p, menge, u } = await vergleichFall(VGL_DC, (a) => [...a.filter((x) => x !== 'gust'), 'dewpoint']);
		assert.deepEqual(p.display_config.ampel, menge);
		assert.deepEqual(ohneOffene(p.display_config.ampel).metrics.gust, { enabled: false, lower: {}, upper: { yellow: 35, orange: 50, red: 65 } }, 'bestehende Grenzen-Abweichung ging verloren');
		const aktiv = u.m.aktiveMetriken(u.m.verschmelzen(u.vorlagen.allgemein, p.display_config.ampel));
		const liste = [...new Set((p.display_config.active_metrics as Json[]).map((x) => x.metric_id))];
		assert.deepEqual(sortiert(aktiv), sortiert(liste), 'AC-37: Ampel-Auswahl und active_metrics laufen auseinander');
	});

	test('ac38_vergleich_fremde_display_config_schluessel_bleiben', async () => {
		const { p } = await vergleichFall(VGL_DC, (a) => a);
		for (const k of ['channel_active_metrics', 'channel_layouts', 'metric_alert_levels', 'alarm_ab_migration', 'region']) {
			assert.deepEqual(p.display_config[k], (VGL_DC as Json)[k], `display_config.${k} veraendert oder verloren`);
		}
	});

	test('ac21_ac20_vergleich_radar_warnungen_tagesfenster_top_level', async () => {
		const { p } = await vergleichFall(VGL_DC, (a) => a, false);
		for (const k of Object.keys(p)) assert.ok(VGL_ERLAUBT.includes(k), `Vergleichs-Payload traegt fremdes Feld ${k} (Zustellung/Orte?)`);
		assert.equal(p.radar_alert_enabled, false);
		assert.equal(p.day_window_start_hour, 7);
		assert.equal(p.day_window_end_hour, 18);
		assert.equal(p.official_alerts_enabled, true);
		assert.equal(p.official_warnings.enabled, true);
		assert.equal('report_config' in p, false, 'Vergleich schreibt das Tagesfenster nicht in report_config');
	});

	test('ac39_vergleich_ohne_active_metrics_schreibt_auswahl_beim_ersten_speichern_vollstaendig', async () => {
		const { p, u } = await vergleichFall({ ampel: { template: 'allgemein' } }, (a) => a);
		const soll = enabledIds(u.vorlagen.allgemein);
		const ids = (p.display_config.active_metrics as Json[]).map((x) => x.metric_id);
		assert.ok(ids.length > 0, 'AC-39: leere Auswahl geschrieben');
		assert.deepEqual(sortiert([...new Set(ids)]), soll);
		for (const e of p.display_config.active_metrics as Json[]) {
			assert.equal(typeof e.aggregation, 'string', `${e.metric_id}: ohne Auswertung`);
		}
	});
});

// ── AC-11/AC-12: Vorlagenwechsel und Zuruecksetzen ───────────────────────────

describe('AC-11/AC-12: Vorlagenwechsel ersetzt Auswahl, Grenzen, Alarmstufen — nicht Zustellung/Etappen/Orte', () => {
	test('ac11_trip_wechsel_auf_wandern', async () => {
		const u = await umgebung();
		const vorher = { ...structuredClone(TRIP_DC), ampel: { template: 'alpen-trekking', metrics: { gust: { alarm_ab: 'red' }, uv_index: { alarm_ab: 'red' } }, thunder: { mittel: 'red' } } };
		assert.equal(u.m.zaehleAbweichungen(vorher.ampel, u.vorlagen), 3, 'Messaufbau: 3 Abweichungen von Alpen-Trekking');
		const neu = u.m.zuruecksetzen('wandern', u.vorlagen);
		const p = u.s.tripSpeicherPayload({
			vorlage: u.vorlagen.wandern,
			aufgeloest: neu.ampel,
			auswahl: neu.auswahl,
			displayConfig: vorher,
			reportConfig: structuredClone(TRIP_RC),
			warnFelder: {},
			warnungenAn: true,
			tagesfenster: { start: 4, end: 19 }
		});
		assert.equal(p.weatherConfig.ampel.template, 'wandern');
		assert.deepEqual(p.weatherConfig.ampel.metrics ?? {}, {}, 'alte Abweichungen ueberleben den Vorlagenwechsel');
		assert.equal(p.weatherConfig.ampel.thunder, undefined);
		const an = (p.weatherConfig.metrics as Json[]).filter((x) => x.enabled).map((x) => x.metric_id);
		assert.deepEqual(sortiert(an), enabledIds(u.vorlagen.wandern), 'Auswahl nicht aus der neuen Vorlage');
		assert.deepEqual(p.tripFelder.report_config, TRIP_RC, 'Zustellung (report_config) veraendert');
		for (const k of ['stages', 'name', 'location_ids']) assert.equal(k in p.tripFelder || k in p.weatherConfig, false, `${k} im Payload`);
		assert.deepEqual(p.weatherConfig.channel_layouts ?? TRIP_DC.channel_layouts, TRIP_DC.channel_layouts);
	});

	test('ac11_vergleich_wechsel_auf_wandern', async () => {
		const u = await umgebung();
		const neu = u.m.zuruecksetzen('wandern', u.vorlagen);
		const p = u.s.vergleichSpeicherPayload({
			vorlage: u.vorlagen.wandern,
			aufgeloest: neu.ampel,
			auswahl: neu.auswahl,
			displayConfig: structuredClone(VGL_DC),
			aggregationFuer: (id: string) => AGG[id] ?? 'max',
			warnFelder: {},
			warnungenAn: true,
			radarAn: true,
			tagesfenster: { start: 7, end: 18 }
		});
		assert.deepEqual(p.display_config.ampel.metrics ?? {}, {});
		assert.equal(p.display_config.ampel.template, 'wandern');
		const ids = [...new Set((p.display_config.active_metrics as Json[]).map((x) => x.metric_id))];
		assert.deepEqual(sortiert(ids), enabledIds(u.vorlagen.wandern));
		for (const k of Object.keys(p)) assert.ok(VGL_ERLAUBT.includes(k), `fremdes Feld ${k} (Orte/Zustellung?)`);
		assert.deepEqual(p.display_config.channel_layouts, VGL_DC.channel_layouts, 'Zustellung (channel_layouts) veraendert');
	});

	test('ac12_zuruecksetzen_schreibt_null_abweichungen', async () => {
		const u = await umgebung();
		const r = u.m.zuruecksetzen('allgemein', u.vorlagen);
		const menge = u.s.abweichungsMenge(u.vorlagen.allgemein, r.ampel, r.auswahl);
		assert.equal(u.m.zaehleAbweichungen(menge, u.vorlagen), 0);
	});
});
