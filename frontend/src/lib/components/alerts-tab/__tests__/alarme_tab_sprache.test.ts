// Issue #2656 (i18n F7, Epic #2644) — AC-1 … AC-6: der Alarme-Reiter (Trip UND
// Ortsvergleich), der Alarm-Kanal-Picker und alle Bausteine unter alerts-tab/
// sprechen die Sprache des angemeldeten Nutzers. Echte SSR-Renders
// (svelte/server, Pruefstand f7Pruefstand.ts):
//   * AC-6: Deutsch ist byte-gleich zur Ausgabe VOR der Umstellung
//     (tests/golden/f7_alarme_tab/*.de.html und funktionen.de.txt),
//   * AC-1: Reiter in beiden Kontexten englisch; Schwellen, Einheiten,
//     Vergleichssymbole und Kanalnamen unveraendert,
//   * AC-2: alertMetricLabel je Sprache, unit/comparison gleich,
//   * AC-3: Katalog-Namen ohne label_en bleiben deutsch, Doppelnamen getrennt,
//   * AC-4: zwei Nutzer (en/de) durch den ECHTEN Layout-Loader (+layout.server.ts);
//     ersetzt ist nur die Netzgrenze (fetch je Sitzungs-Cookie),
//   * AC-5: Premium-SMS-Hinweis aus demselben Schluessel wie im Versand-Reiter.
// Jeder en-Fall rendert zuerst de und schaltet dann OHNE Neuladen auf en.
// Englische und deutsche Texte sind als feste Literale verankert (f7KatalogAnker.ts).
// Spec: docs/specs/modules/i18n_f7_alarme_tab_2656.md
//
//   cd frontend && npm test -- src/lib/components/alerts-tab/__tests__/alarme_tab_sprache.test.ts

import { test, describe, before, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import {
	FRONTEND,
	GOLDEN_DIR,
	REGELN,
	VERGLEICH_KATALOG,
	VERGLEICH_AKTIV,
	ALLE_ALARM_METRIKEN,
	locale,
	trFor,
	labels,
	amt,
	vorschau,
	sektionen,
	kanal,
	gate,
	katalogAbl,
	lieferung,
	premiumVersand,
	trip,
	wizard,
	alarmeRoute,
	alarmeVergleich,
	zustaendeRendern,
	bausteineRendern,
	htmlFaelle,
	funktionsTabelle,
	schreibeGolden
} from './f7Pruefstand.ts';
import { F7_ANKER } from './f7KatalogAnker.ts';

const base = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, base);
register(pathToFileURL(path.join(FRONTEND, 'src/routes/admin/__tests__/server-load-resolve.hooks.mjs')).href, base);
const layoutLoad = (await import(pathToFileURL(path.join(FRONTEND, 'src/routes/+layout.server.ts')).href)).load;

before(() => {
	// Die de-Golden sind der Ist-Stand VOR der Umstellung und werden nie neu geschrieben;
	// nur die en-Ansicht (Review-Hilfe, nicht verglichen) wird aktualisiert.
	if (process.env.GZ_GOLDEN_SCHREIBEN === 'en') schreibeGolden('en');
});
afterEach(() => locale.set('de'));

// Einzige Normalisierung: jede Leerraumfolge wird EIN Leerzeichen (mehrzeilige
// Fliesstexte standen vorher mit Zeilenumbruch+Tabs im Markup). Sonst byte-gleich.
const leerraum = (s: string) => s.replace(/\s+/g, ' ');
const sichtbar = (h: string) =>
	leerraum(h.replace(/<style[\s\S]*?<\/style>/g, ' ').replace(/<(?:"[^"]*"|'[^']*'|[^'">])*>/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<')).trim();
const hat = (text: string, teil: string) => assert.ok(text.includes(teil), `fehlt: „${teil}"\nin: ${text.slice(0, 4000)}`);
const hatNicht = (text: string, teil: string) => assert.ok(!text.includes(teil), `steht noch: „${teil}"`);

function deDannEn<T>(f: () => T): { de: T; en: T } {
	locale.set('de');
	const de = f();
	locale.set('en');
	const en = f();
	return { de, en };
}

/** Deutsche Festteile (>= 4 Buchstaben) der Paket-Schluessel, die im englischen Text stehen. */
function deutscheReste(text: string, ausnahmen: string[] = []): string[] {
	const reste: string[] = [];
	for (const [k, de, en] of F7_ANKER) {
		if (de === en || ausnahmen.some((a) => k === a || (a.endsWith('.') && k.startsWith(a)))) continue;
		const enTeile = new Set(en.split(/<[a-z0-9_]+>/).map((s) => s.trim()));
		for (const teil of de.split(/<[a-z0-9_]+>/).map((s) => s.trim())) {
			if ((teil.match(/[A-Za-zÄÖÜäöüß]/g) ?? []).length < 4 || enTeile.has(teil)) continue;
			if (text.includes(teil)) reste.push(`${k}: ${teil}`);
		}
	}
	return reste;
}
/** Vergleichs-Katalog ohne label_en (Luftfeuchtigkeit): der deutsche Name ist Fallback (AC-3). */
const OHNE_LABEL_EN = ['alarme.metrik.humidity', 'alarme.preset.zeile.humidity'];
/** Die Preset-Zeilen nennen dieselben Woerter wie die Metrik-Namen; im Reiter stehen nur diese. */
const PRESET_ZEILEN = ['alarme.preset.zeile.'];

/** Schwellen, Einheiten, Vergleichssymbole, Zeiten und Eingabewerte eines Renders. */
function zahlenUndEinheiten(h: string): string[] {
	const muster = [
		/data-testid="alert-threshold-[^"]*"[^>]*>([^<]*)</g,
		/class="(?:threshold-unit|metric-unit|unit|threshold-label)[^"]*"[^>]*>([^<]*)</g,
		/value="([^"]*)"/g,
		/data-level="([^"]*)"/g
	];
	const aus: string[] = [];
	for (const m of muster) for (const x of h.matchAll(m)) aus.push(x[1]);
	return aus;
}

describe('AC-6: Deutsch byte-gleich zum Ist-Stand vor der Umstellung (Golden golden-de)', () => {
	const FAELLE = htmlFaelle();
	for (const fall of Object.keys(FAELLE)) {
		test(`${fall}.de.html`, () => {
			const golden = readFileSync(path.join(GOLDEN_DIR, `${fall}.de.html`), 'utf-8');
			const { de } = deDannEn(() => FAELLE[fall]());
			locale.set('de');
			assert.equal(leerraum(FAELLE[fall]() + '\n'), leerraum(golden));
			assert.equal(leerraum(de + '\n'), leerraum(golden));
		});
	}
	test('funktionen.de.txt: Funktionsergebnisse unveraendert (byte-gleich, ohne Normalisierung)', () => {
		const golden = readFileSync(path.join(GOLDEN_DIR, 'funktionen.de.txt'), 'utf-8');
		locale.set('en');
		funktionsTabelle();
		locale.set('de');
		assert.equal(funktionsTabelle() + '\n', golden);
	});
	test('Messaufbau: Golden enthaelt die deutschen Texte aller Bausteine', () => {
		const alle = Object.keys(FAELLE).map((f) => readFileSync(path.join(GOLDEN_DIR, `${f}.de.html`), 'utf-8')).join('');
		for (const s of ['Amtliche &amp; Radar-Warnungen', 'Radar-Alarm', 'Alert-Kanäle', 'Premium-SMS ab Level Premium verfügbar', 'Tarif wird geprüft', 'kein Kanal — Alerts gehen nirgends hin', 'sofortiger Push', '(Ortszeit des ersten Orts)', '(Ortszeit der Trip)', 'Stille Stunden über Mitternacht (22:00 bis 07:00 des nächsten Tages).', 'Für diese Größen gibt es keinen Alarm', 'Keine der gewählten Größen', 'Wähle im Tab „Wetter-Metriken"', 'Schwellwerte nach Preset', 'Tiefsttemperatur', 'title="Richtwert — wird je Wettermodell und Gebiet umgerechnet"', 'Lade…', 'title="Alert-Vorschau E-Mail"', 'Melde ab Änderung:', '— deaktiviert —', '1 von 2 · gemischt', '5 von 5 aktiv', 'Noch keine Orte konfiguriert', 'Standard-Konfiguration übernehmen'])
			assert.ok(alle.includes(s), s);
	});
});

describe('AC-1: Alarme-Reiter englisch in Trip und Ortsvergleich, Zahlen und Symbole unveraendert', () => {
	test('Trip: erst de, dann ohne Neuladen en', () => {
		const { de, en } = deDannEn(() => alarmeRoute());
		const text = sichtbar(en);
		hat(sichtbar(de), 'Stille Stunden');
		for (const s of [
			'Official warnings',
			'Official warnings trigger an alert',
			'Set all metrics to:',
			'3 of 4 · mixed',
			'Metric',
			'Sensitivity',
			'Threshold',
			'Wind gusts',
			'Temperature (minimum)',
			'Thunderstorm energy (CAPE)',
			'Thunderstorm (onset)',
			'Off',
			'Relaxed',
			'Relax.',
			'Sensitive',
			'Alert channels',
			'Urgency threshold',
			'2 active',
			'Alerts are short instant notifications — Telegram/SMS are ideal for them. The planned briefing (the table) continues separately over its own channels.',
			'low moderate high',
			'Premium SMS is available from the Premium level',
			'Cooldown',
			'minutes',
			'Minimum gap between two alerts for the same metric — prevents spam from fluctuating values.',
			'Quiet hours',
			'Active',
			'Do not send alerts in this period (local time of the trip) — queued alerts go out with the next morning briefing.',
			'From',
			'To',
			'Quiet hours across midnight (22:00 to 07:00 of the next day).',
			'Example warning',
			'Load preview'
		])
			hat(text, s);
		hat(en, 'title="Guide value — converted per weather model and area"');
		hat(en, 'aria-label="Urgency threshold Telegram"');
		hat(en, 'aria-label="Toggle Premium-SMS (Garmin inReach)"');
		// Kanalnamen sind Eigennamen: in beiden Sprachen gleich.
		for (const s of ['Telegram', 'SMS', 'Premium-SMS (Garmin inReach)', 'Email']) hat(text, s);
		assert.deepEqual(deutscheReste(text, PRESET_ZEILEN), []);
		assert.deepEqual(zahlenUndEinheiten(en), zahlenUndEinheiten(de));
		assert.ok(zahlenUndEinheiten(de).includes('Δ ≥ ~1200 J/kg'), 'Messaufbau: Schwellen fehlen');
	});
	test('Ortsvergleich: erst de, dann ohne Neuladen en (Radar, Gruppe, Ortszeit-Bezug)', () => {
		const { de, en } = deDannEn(() => alarmeVergleich());
		const text = sichtbar(en);
		for (const s of [
			'Official & radar warnings',
			'Official warnings trigger an alert',
			'Rain alert (radar)',
			'2 of 3 · mixed',
			'Wind gusts',
			'There is no alert for these metrics: Luftfeuchtigkeit, Gefühlte Temperatur (Minimum), Gefühlte Temperatur (Maximum). They still appear in the briefing but do not trigger a warning.',
			'Checking your level — the channel cannot be switched for a moment.',
			'Alert channels',
			'Quiet hours',
			'Do not send alerts in this period (local time of the first location) — queued alerts go out with the next morning briefing.',
			'Quiet hours across midnight (23:00 to 06:30 of the next day).',
			'Example warning'
		])
			hat(text, s);
		hatNicht(text, 'Ortszeit');
		assert.deepEqual(deutscheReste(text, [...PRESET_ZEILEN, ...OHNE_LABEL_EN]), []);
		assert.deepEqual(zahlenUndEinheiten(en), zahlenUndEinheiten(de));
	});
	test('Leer- und Sonderzustaende englisch (Reiter, Kanal-Picker, Beispiel-Warnung, Stille Stunden)', () => {
		const { en } = deDannEn(() => zustaendeRendern());
		const text = sichtbar(en);
		for (const s of [
			'Select metrics in the “Weather metrics” tab to configure alert thresholds.',
			'None of the selected metrics can trigger an alert: Luftfeuchtigkeit, Gefühlte Temperatur (Minimum), Gefühlte Temperatur (Maximum). They still appear in the briefing but do not trigger a warning.',
			'no channel — alerts go nowhere',
			'instant push',
			'instant · ≤ 140 chars',
			'satellite · works without mobile network',
			'optional · slower than push',
			'The preview with real data is available after saving.',
			'No locations configured yet — add candidates in the Locations tab.',
			'Activate at least one alert rule to load the preview.',
			'No alert-capable weather metrics active. First activate weather metrics (e.g. wind gusts, temperature) in the Weather metrics tab.',
			'Do not send alerts in this period (local time of the trip)'
		])
			hat(text, s);
		hat(en, '<a href="?tab=wetter-metriken" data-testid="alert-preview-no-metrics-link"><strong>Weather metrics</strong></a>');
		assert.deepEqual(deutscheReste(text, [...PRESET_ZEILEN, ...OHNE_LABEL_EN]), []);
	});
	test('Bausteine unter alerts-tab/ englisch (Alerts-Reiter, Karte, Tabellen, Preset, Vorschau)', () => {
		const { de, en } = deDannEn(() => bausteineRendern());
		const text = sichtbar(en);
		for (const s of [
			'Alerts · instant notification',
			'Instant notifications between briefings',
			'No alerts configured.',
			'Apply standard configuration',
			'Select metrics above to configure alert thresholds.',
			'5 of 5 active',
			'1 of 2 · mixed',
			'No alertable metrics active. Select metrics in the Weather metrics tab.',
			'Notify from change of:',
			'Channel:',
			'Δ change (since last briefing)',
			'Absolute threshold',
			'— disabled —',
			'Info Warning Critical',
			'Off Relaxed Standard Sensitive',
			'Thresholds by preset',
			'Low temperature',
			'High temperature',
			'Temperature (change)',
			'Loading…',
			'Load preview'
		])
			hat(text, s);
		hat(en, 'aria-label="Show threshold overview"');
		hat(en, 'aria-label="Close"');
		hat(en, 'title="Alert preview email"');
		// Optionswerte (value) bleiben die Kennungen.
		for (const v of ['value="info"', 'value="warning"', 'value="critical"', 'value="deaktiviert"', 'value="entspannt"']) hat(en, v);
		assert.deepEqual(deutscheReste(text), []);
		assert.deepEqual(zahlenUndEinheiten(en), zahlenUndEinheiten(de));
	});
});

describe('AC-2: alertMetricLabel je Sprache, unit/comparison unveraendert', () => {
	const ERWARTET: Record<string, [string, string]> = {
		wind_gust: ['Böen', 'Wind gusts'],
		precipitation_sum: ['Niederschlag', 'Precipitation'],
		thunder_level: ['Gewitter', 'Thunderstorm'],
		snow_line: ['Schneefallgrenze', 'Snow line'],
		temperature_min: ['Temperatur (Minimum)', 'Temperature (minimum)'],
		temperature_max: ['Temperatur (Maximum)', 'Temperature (maximum)'],
		temperature_change: ['Temperatur (Änderung)', 'Temperature (change)'],
		wind_change: ['Wind (Änderung)', 'Wind (change)'],
		precipitation_change: ['Niederschlag (Änderung)', 'Precipitation (change)'],
		fresh_snow: ['Neuschnee', 'Fresh snow'],
		cape: ['Gewitterenergie (CAPE)', 'Thunderstorm energy (CAPE)'],
		visibility: ['Sichtweite', 'Visibility'],
		humidity: ['Luftfeuchtigkeit', 'Humidity'],
		freezing_level: ['Nullgradgrenze', 'Freezing level'],
		thunder_onset: ['Gewitter (Beginn)', 'Thunderstorm (onset)'],
		precipitation_heavy_onset: ['Starkregen (Beginn)', 'Heavy rain (onset)']
	};
	test('Messaufbau: jede Alarm-Metrik der Tabelle steht in ERWARTET', () => {
		assert.deepEqual(Object.keys(labels.ALERT_METRIC_LABELS).sort(), Object.keys(ERWARTET).sort());
		assert.deepEqual([...ALLE_ALARM_METRIKEN].sort(), Object.keys(ERWARTET).sort());
	});
	for (const [m, [de, en]] of Object.entries(ERWARTET)) {
		test(m, () => {
			assert.equal(typeof labels.alertMetricLabel, 'function', 'alertMetricLabel fehlt');
			assert.equal(labels.alertMetricLabel(m, 'de'), de);
			assert.equal(labels.alertMetricLabel(m, 'en'), en);
			const e = labels.ALERT_METRIC_LABELS[m];
			assert.equal(e.label_de, de);
			assert.equal(e.label_en, en);
			const { de: d, en: n } = deDannEn(() => ({ unit: e.unit, comparison: e.comparison, label_de: e.label_de }));
			assert.deepEqual(n, d, 'unit/comparison/label_de haengen nicht an der Sprache');
		});
	}
	test('unbekannte Kennung: Fallback auf die Kennung, nie leer', () => {
		assert.equal(labels.alertMetricLabel('zukunft_metrik', 'en'), 'zukunft_metrik');
		assert.equal(labels.alertMetricLabel('zukunft_metrik', 'de'), 'zukunft_metrik');
	});
	test('Schweregrad und Kanal-Stufen je Sprache; SEVERITY_LABEL_DE bleibt deutsch', () => {
		assert.equal(typeof labels.severityLabel, 'function', 'severityLabel fehlt');
		assert.deepEqual(['info', 'warning', 'critical'].map((s) => labels.severityLabel(s, 'en')), ['Info', 'Warning', 'Critical']);
		assert.deepEqual(['info', 'warning', 'critical'].map((s) => labels.severityLabel(s, 'de')), ['Info', 'Warnung', 'Kritisch']);
		const { de, en } = deDannEn(() => ({ sev: { ...labels.SEVERITY_LABEL_DE }, stufen: { ...kanal.CHANNEL_THRESHOLD_LABELS } }));
		assert.deepEqual(en.sev, de.sev);
		assert.deepEqual(de.stufen, { LOW: 'gering', MODERATE: 'mittel', HIGH: 'hoch' });
		assert.deepEqual(en.stufen, { LOW: 'low', MODERATE: 'moderate', HIGH: 'high' });
	});
	test('Ueberschrift der Ausloeser-Gruppe, Richtwert-Hinweis und Schwellen je Sprache', () => {
		const { de, en } = deDannEn(() => ({
			route: sektionen.triggerGroupHeading('route'),
			vergleich: sektionen.triggerGroupHeading('vergleich'),
			titel: amt.thresholdTitle('cape'),
			ohne: amt.thresholdTitle('wind_gust'),
			schwellen: ALLE_ALARM_METRIKEN.map((m) => amt.levelToThreshold(m, 'standard'))
		}));
		assert.deepEqual(en, {
			route: 'Official warnings',
			vergleich: 'Official & radar warnings',
			titel: 'Guide value — converted per weather model and area',
			ohne: undefined,
			schwellen: de.schwellen
		});
		assert.equal(de.titel, 'Richtwert — wird je Wettermodell und Gebiet umgerechnet');
	});
	test('Vorschau-Fehler ohne Servertext: Rueckfall je Sprache, Servertext unveraendert', () => {
		assert.equal(typeof (vorschauFehler()), 'function', 'vorschauFehlerText fehlt in alertPreviewHelpers.ts');
		const f = vorschauFehler();
		const { de, en } = deDannEn(() => [f(new Error('')), f({ error: 'HTTP 503' }), f(new Error('Zeitlimit')), f(42)]);
		assert.deepEqual(de, ['Vorschau konnte nicht geladen werden', 'HTTP 503', 'Zeitlimit', 'Vorschau konnte nicht geladen werden']);
		assert.deepEqual(en, ['Preview could not be loaded', 'HTTP 503', 'Zeitlimit', 'Preview could not be loaded']);
	});
});

/** alertPreviewHelpers.vorschauFehlerText (Namensraum-Import im Pruefstand). */
const vorschauFehler = () => vorschau.vorschauFehlerText as (e: unknown) => string;

describe('AC-3: Katalog-Namen ohne label_en bleiben deutsch, Doppelnamen bleiben getrennt', () => {
	const MIT_EN = VERGLEICH_KATALOG.map((e) =>
		e.label === 'Temperatur' ? { ...e, label_en: 'Temperature' } : e.label === 'Gefühlte Temperatur' ? { ...e, label_en: 'Feels-like temperature' } : e
	);
	const DOPPEL = [
		{ metric: 'temp_min_c', label: 'Temperatur', label_en: 'Temperature', aggregation: 'min', aggregation_label: 'Minimum', alertMetric: null },
		{ metric: 'temp_max_c', label: 'Temperatur', label_en: 'Temperature', aggregation: 'max', aggregation_label: 'Maximum', alertMetric: null },
		{ metric: 'humidity_avg_pct', label: 'Luftfeuchtigkeit', label_en: '', aggregation: 'avg', aggregation_label: 'Mittel', alertMetric: null }
	];
	const namen = (keys: string[], kat: unknown[], lang: 'de' | 'en') => katalogAbl.deriveUnalertableSelectedMetricNames(keys, kat, lang);
	test('en: label_en gewinnt, fehlend/leer -> deutscher Name; Auswertung in Klammern aus dem Katalog', () => {
		assert.deepEqual(namen(VERGLEICH_AKTIV, MIT_EN, 'en'), ['Luftfeuchtigkeit', 'Feels-like temperature (Minimum)', 'Feels-like temperature (Maximum)']);
		assert.deepEqual(namen(['temp_min_c', 'temp_max_c', 'humidity_avg_pct'], DOPPEL, 'en'), ['Temperature (Minimum)', 'Temperature (Maximum)', 'Luftfeuchtigkeit']);
	});
	test('de: wortgleich wie bisher (label_en wird ignoriert)', () => {
		assert.deepEqual(namen(VERGLEICH_AKTIV, MIT_EN, 'de'), ['Luftfeuchtigkeit', 'Gefühlte Temperatur (Minimum)', 'Gefühlte Temperatur (Maximum)']);
		assert.deepEqual(namen(['temp_min_c', 'temp_max_c', 'humidity_avg_pct'], DOPPEL, 'de'), ['Temperatur (Minimum)', 'Temperatur (Maximum)', 'Luftfeuchtigkeit']);
	});
	test('kein Eintrag ergibt einen leeren Namen', () => {
		for (const lang of ['de', 'en'] as const) for (const n of namen(VERGLEICH_AKTIV, VERGLEICH_KATALOG, lang)) assert.ok(n.trim().length > 0);
	});
	test('Wirkort: der Reiter zeigt die Namen der Nutzersprache (Render, Doppelname getrennt)', () => {
		const { de, en } = deDannEn(() => sichtbar(alarmeVergleich(wizard(), { catalog: MIT_EN })));
		hat(en, 'There is no alert for these metrics: Luftfeuchtigkeit, Feels-like temperature (Minimum), Feels-like temperature (Maximum).');
		hat(de, 'Für diese Größen gibt es keinen Alarm: Luftfeuchtigkeit, Gefühlte Temperatur (Minimum), Gefühlte Temperatur (Maximum).');
	});
	test('Alarm-Zeilen (Identitaeten) haengen nicht an der Sprache', () => {
		const { de, en } = deDannEn(() => katalogAbl.deriveActiveAlertMetricsFromCatalog(VERGLEICH_AKTIV, MIT_EN));
		assert.deepEqual(en, de);
		assert.deepEqual(de, ['wind_gust', 'temperature_min', 'cape']);
	});
});

describe('AC-4: zwei Nutzer, zwei Sprachen, gleiche Alarm-Regeln, gleiche Speicher-Nutzlast', () => {
	const API: Record<string, Record<string, unknown>> = {
		A: { '/api/auth/profile': { id: 'anna', language: 'en' }, '/api/trips/anna-gr20': trip('anna-gr20') },
		B: { '/api/auth/profile': { id: 'bert', language: 'de' }, '/api/trips/bert-gr20': trip('bert-gr20') }
	};
	async function mitApi<T>(lauf: () => Promise<T>): Promise<T> {
		const echt = globalThis.fetch;
		globalThis.fetch = (async (u: string, init?: { headers?: Record<string, string> }) => {
			const sitzung = /gz_session=([^;]+)/.exec(init?.headers?.Cookie ?? '')?.[1] ?? '';
			const daten = API[sitzung]?.[new URL(String(u)).pathname];
			return new Response(JSON.stringify(daten ?? null), { status: daten === undefined ? 404 : 200 });
		}) as unknown as typeof fetch;
		try {
			return await lauf();
		} finally {
			globalThis.fetch = echt;
		}
	}
	const cookies = (s: string) => ({ get: (n: string) => (n === 'gz_session' ? s : undefined) });
	const holen = async (sitzung: string, pfad: string) => {
		const r = await fetch(`http://core${pfad}`, { headers: { Cookie: `gz_session=${sitzung}` } });
		return r.status === 200 ? await r.json() : null;
	};

	/** Echter Layout-Loader (Sprache) + Daten der Sitzung → Reiter, geaenderte Schwellen, Nutzlast. */
	async function sichtFuer(sitzung: 'A' | 'B', tripId: string) {
		const { lang, t, fremd } = await mitApi(async () => {
			const layout = await layoutLoad({ locals: { userId: sitzung, lang: 'de' }, cookies: cookies(sitzung) } as never);
			const fremdeId = sitzung === 'A' ? 'bert-gr20' : 'anna-gr20';
			return { lang: layout.lang as 'de' | 'en', t: await holen(sitzung, `/api/trips/${tripId}`), fremd: await holen(sitzung, `/api/trips/${fremdeId}`) };
		});
		locale.set(lang);
		const zeilen = amt.alertRulesToRowState(t.alert_rules, t.alert_rules);
		zeilen.wind_gust.deltaThreshold = 25;
		zeilen.temperature_min.severity = 'warning';
		const schwellen = kanal.applyThresholdChange(kanal.resolveAlertChannelThresholds({ telegram: 'MODERATE' }), 'sms', 'HIGH');
		const regeln = amt.rowStateToAlertRules(zeilen, t.alert_rules);
		const nutzlast = lieferung.buildAlarmeDeliveryPayload({
			officialWarningsEnabled: true,
			cooldownMinutes: t.alert_cooldown_minutes,
			quietFrom: t.alert_quiet_from,
			quietTo: t.alert_quiet_to,
			channels: { email: true, telegram: true, sms: true, premium_sms: false },
			channelThresholds: schwellen,
			metricLevels: { ...{ wind_gust: 'standard', temperature_min: 'sensibel' }, cape: 'entspannt' }
		});
		return { lang, fremd, reiter: sichtbar(alarmeRoute({ trip: t })), regeln, nutzlast };
	}

	test('A englisch, B deutsch; jeder nur eigene Daten; Nutzlast identisch und ohne Anzeige-Texte', async () => {
		locale.set('de');
		const a = await sichtFuer('A', 'anna-gr20');
		const b = await sichtFuer('B', 'bert-gr20');
		assert.equal(a.lang, 'en');
		assert.equal(b.lang, 'de');
		assert.equal(a.fremd, null, 'A liest den Trip von B');
		assert.equal(b.fremd, null, 'B liest den Trip von A');
		hat(a.reiter, 'Alert channels');
		hat(a.reiter, 'Wind gusts');
		hat(a.reiter, 'Quiet hours');
		hat(b.reiter, 'Alert-Kanäle');
		hat(b.reiter, 'Böen');
		hat(b.reiter, 'Stille Stunden');
		assert.deepEqual(deutscheReste(a.reiter, PRESET_ZEILEN), []);
		assert.equal(JSON.stringify(a.regeln), JSON.stringify(b.regeln));
		assert.equal(JSON.stringify(a.nutzlast), JSON.stringify(b.nutzlast));
		assert.equal(a.regeln.find((r: { id: string }) => r.id === 'r-gust-d').threshold, 25, 'geaenderte Schwelle gespeichert');
		assert.equal(a.nutzlast.alert_channel_thresholds.sms, 'HIGH');
		for (const s of [JSON.stringify(a.regeln), JSON.stringify(a.nutzlast)]) {
			for (const wort of ['Wind gusts', 'Böen', 'Warning', 'Warnung', 'Critical', 'Kritisch', 'high', 'hoch', 'label', 'Quiet', 'Stille']) hatNicht(s, wort);
		}
	});
});

describe('AC-5: Premium-SMS-Hinweis im Alarme- und im Versand-Reiter aus demselben Schluessel', () => {
	test('gleich in beiden Sprachen; en exakt', () => {
		const ohne = { premium_sms_allowed: false };
		const { de, en } = deDannEn(() => ({ alarm: gate.derivePremiumSmsAlarmGate(ohne).hint, versand: premiumVersand.premiumSmsChannelState(ohne).hint }));
		assert.equal(de.alarm, de.versand);
		assert.equal(en.alarm, en.versand);
		assert.equal(de.alarm, 'Premium-SMS ab Level Premium verfügbar');
		assert.equal(en.alarm, 'Premium SMS is available from the Premium level');
		assert.equal(gate.PREMIUM_SMS_ALARM_HINT_NO_TIER, 'versand.premium_sms.hinweis.nicht_verfuegbar', 'derselbe Katalogschluessel wie im Versand-Reiter');
	});
	test('Wirkort: die gesperrte Zeile im Reiter zeigt den Hinweis der Nutzersprache', () => {
		const { de, en } = deDannEn(() => alarmeRoute());
		const zeile = (h: string) => sichtbar(/data-testid="alert-channel-disabled-hint-premium_sms"[^>]*>([\s\S]*?)<\/div>/.exec(h)?.[1] ?? '');
		assert.equal(zeile(de), 'Premium-SMS ab Level Premium verfügbar');
		assert.equal(zeile(en), 'Premium SMS is available from the Premium level');
	});
});

describe('Anker: jeder F7-Katalogwert ist als festes de/en-Literal verankert', () => {
	const params = (literal: string) => Object.fromEntries([...literal.matchAll(/<([a-z0-9_]+)>/g)].map((m) => [m[1], `<${m[1]}>`]));
	for (const [k, de, en] of F7_ANKER) {
		test(k, () => {
			assert.equal(trFor('de', k, params(de)), de, `de ${k}`);
			assert.equal(trFor('en', k, params(en)), en, `en ${k}`);
		});
	}
	test('statischer Gegencheck: Anker-Tabelle == Schluessel von alarme.json (de und en)', () => {
		const MSG = path.join(FRONTEND, 'src', 'lib', 'i18n', 'messages');
		for (const lang of ['de', 'en']) {
			const schluessel = Object.keys(JSON.parse(readFileSync(path.join(MSG, lang, 'alarme.json'), 'utf-8')));
			assert.deepEqual([...schluessel].sort(), F7_ANKER.map(([k]) => k).sort(), `${lang}: Schluessel ohne Anker oder Anker ohne Schluessel`);
		}
		assert.equal(new Set(F7_ANKER.map(([k]) => k)).size, F7_ANKER.length, 'doppelte Anker');
	});
	test('Metrik-Namen-Anker == ALERT_METRIC_LABELS (de wortgleich zur Golden-Funktionstabelle)', () => {
		const golden = readFileSync(path.join(GOLDEN_DIR, 'funktionen.de.txt'), 'utf-8');
		for (const [k, de] of F7_ANKER.filter(([k]) => k.startsWith('alarme.metrik.'))) {
			const m = k.slice('alarme.metrik.'.length);
			assert.ok(golden.includes(`ALERT_METRIC_LABELS(${m}) → {"label_de":${JSON.stringify(de)},`), k);
		}
	});
	test('Kanalnamen sind Eigennamen und stehen nicht im Katalog', () => {
		for (const [, de, en] of F7_ANKER) for (const name of ['Premium-SMS (Garmin inReach)']) assert.ok(!de.includes(name) && !en.includes(name));
	});
});

// Zur Sicherheit: die Regeln der Fixture sind Daten (keine Anzeige-Texte).
test('Messaufbau: Fixture-Regeln tragen keine Anzeige-Texte', () => {
	assert.ok(REGELN.every((r) => !('label' in r)));
});
