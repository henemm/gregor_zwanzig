// TDD RED — Issue #2422 S3, AC-22 (Bein c, TypeScript).
// Spec: docs/specs/modules/fix_2422_s3_kanal_an_aus_kette.md
//
// AC-22: Given die `report_config` aus Golden D geladen / When der Payload-Baustein
// der Editoren ohne Aenderung laeuft / Then entspricht das Ergebnis strukturell der
// eingefrorenen `report_config_nach_speichern_golden_d.json` einschliesslich des
// unbekannten Schluessels und aller vier Kanal-Schalter; schaltet der Nutzer
// "Abend" aus, steht enabled=true, evening_enabled=false, morning_enabled=true;
// schaltet er beide aus, steht enabled=false. Jede Abweichung macht den Test rot.
//
// ── Warum ein neues Modul ───────────────────────────────────────────────────
// Der Payload-Bau (`enabled = morning || evening`, Feldmenge, `toHHMMSS`) und der
// Startzustand aus dem geladenen Blob stehen heute NUR im `$effect`- bzw.
// `onMount`-Rumpf von VersandTab.svelte (:163-211) und
// MailInhaltCard.svelte (:165-173, :277-279). `$effect`/`onMount` laufen
// unter svelte/server nie, `mergeReportConfig` allein ist nicht die Payload-
// Funktion. In /50 wird der Bau VERHALTENSGLEICH in ein reines Modul gezogen
// (Vorbild weatherMetricsSavePayload.ts); beide Komponenten rufen es auf:
//
//   frontend/src/lib/components/shared/versand-tab/reportConfigPayload.ts
//
//   export interface ReportZustand {
//     morning_enabled: boolean;  evening_enabled: boolean;
//     morning_time: string;      evening_time: string;        // 'HH:MM'
//     send_email: boolean;  send_telegram: boolean;  send_sms: boolean;  send_premium_sms: boolean;
//     telegram_style: 'rich' | 'kurzform';
//     multi_day_trend_morning: boolean;  multi_day_trend_evening: boolean;
//   }
//   /** onMount-/Erzeugungs-Logik: Zustand aus dem geladenen Blob. Slots via
//    *  reportSlotAktiv (AC-24), Defaults wie bisher (07:00/18:00, E-Mail an, Rest aus,
//    *  telegram_style 'rich', Trends aus multi_day_trend_* bzw. multi_day_trend_reports). */
//   export function ladeReportZustand(rc: ReportConfig | null | undefined): ReportZustand;
//   /** $effect-Rumpf: mergeReportConfig({ snapshot, live, own: {...} }) mit
//    *  enabled = morning_enabled || evening_enabled, toHHMMSS auf beide Zeiten,
//    *  multi_day_trend_reports aus den beiden Trend-Flags. */
//   export function baueReportConfigPayload(eingabe: {
//     snapshot?: Record<string, unknown> | null;
//     live: Record<string, unknown> | null | undefined;
//     zustand: ReportZustand;
//   }): Record<string, unknown>;
//
// Das Modul existiert heute NICHT => Import scheitert => RED aus dem richtigen
// Grund (klare Meldung, kein Kompilierfehler; dynamisch geladen, damit die
// Golden-D-Meldung unabhaengig davon eindeutig bleibt).
//
// ── Golden D ────────────────────────────────────────────────────────────────
// `tests/fixtures/einstellung_auslieferung/report_config_nach_speichern_golden_d.json`
// existiert ABSICHTLICH NOCH NICHT: sie entsteht in /50 NACH den Fixes aus der
// echten Helferkette (Generator analog
// weather-metrics-tab/__tests__/erzeuge_nach_dateien.ts) — vorher wuerde sie den
// alten Stand einfrieren. Fehlt sie, scheitert der Test mit
// "Golden-D-Datei fehlt — wird in /50 erzeugt" (nie ein stilles Ueberspringen).
//
// Messgrenze (-> E2E AC-26): dieser Test beweist die Funktion, nicht dass die
// Komponenten sie im `$effect` auch wirklich aufrufen; Klick, Speichern und
// Rueckladen laufen nur im Browser.
//
// Kein Mock. Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/versand-tab/__tests__/report_config_serialisierung_golden.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> versand-tab -> shared -> components -> lib -> src -> frontend -> Repo-Wurzel
const REPO = path.resolve(HERE, '../../../../../../..');
const FIXTURES = path.join(REPO, 'tests', 'fixtures', 'einstellung_auslieferung');
const GOLDEN_D = path.join(FIXTURES, 'golden_d.json');
const GOLDEN_D_NACH = path.join(FIXTURES, 'report_config_nach_speichern_golden_d.json');

type Blob = Record<string, unknown>;
interface PayloadModul {
	ladeReportZustand: (rc: Blob | null | undefined) => Record<string, unknown>;
	baueReportConfigPayload: (e: {
		snapshot?: Blob | null;
		live: Blob | null | undefined;
		zustand: Record<string, unknown>;
	}) => Blob;
}

async function ladeModul(): Promise<PayloadModul> {
	const datei = path.join(HERE, '..', 'reportConfigPayload.ts');
	if (!existsSync(datei)) {
		assert.fail(
			'reportConfigPayload.ts fehlt — reine Payload-Funktion (ladeReportZustand + ' +
				'baueReportConfigPayload) entsteht in /50 durch verhaltensgleiches Herausziehen aus ' +
				'VersandTab.svelte/MailInhaltCard.svelte (shared/versand-tab/reportConfigPayload.ts)'
		);
	}
	const mod = await import(pathToFileURL(datei).href);
	assert.equal(typeof mod.ladeReportZustand, 'function', 'ladeReportZustand ist nicht exportiert');
	assert.equal(typeof mod.baueReportConfigPayload, 'function', 'baueReportConfigPayload ist nicht exportiert');
	return mod as PayloadModul;
}

/** Ein Speichern OHNE Nutzereingabe: Zustand aus dem geladenen Blob, Blob zurueckgeschrieben. */
function speichernOhneAenderung(mod: PayloadModul, rc: Blob): Blob {
	const zustand = mod.ladeReportZustand(rc);
	return mod.baueReportConfigPayload({ snapshot: rc, live: rc, zustand });
}

/** D-1-foermiger Blob (Spec "Golden D"): Abend AUS, alle vier Kanaele an, unbekannter Schluessel. */
function d1Blob(): Blob {
	return {
		trip_id: 'inline-d1',
		enabled: true,
		morning_enabled: true,
		evening_enabled: false,
		morning_time: '06:00:00',
		evening_time: '20:00:00',
		send_email: true,
		send_telegram: true,
		send_sms: true,
		send_premium_sms: true,
		telegram_style: 'kurzform',
		email_format: 'compact',
		change_threshold_wind_kmh: 25
	};
}

describe('AC-22 — Golden D: Speichern ohne Aenderung schreibt den eingefrorenen Blob', () => {
	test('golden_d_roundtrip_gleich_eingefrorener_datei', async () => {
		// Reihenfolge bewusst: ZUERST die Golden-D-Dateien, damit die Meldung eindeutig bleibt.
		if (!existsSync(GOLDEN_D_NACH)) {
			assert.fail(
				'Golden-D-Datei fehlt — wird in /50 erzeugt: ' +
					'tests/fixtures/einstellung_auslieferung/report_config_nach_speichern_golden_d.json ' +
					'(aus der echten Helferkette NACH den Fixes, nicht vorher einfrieren)'
			);
		}
		assert.ok(existsSync(GOLDEN_D), `Golden-D-Eingabe fehlt: ${GOLDEN_D}`);
		const mod = await ladeModul();
		const golden = JSON.parse(readFileSync(GOLDEN_D, 'utf-8'));
		const erwartet = JSON.parse(readFileSync(GOLDEN_D_NACH, 'utf-8'));
		assert.deepEqual(
			speichernOhneAenderung(mod, golden.report_config),
			erwartet,
			'Speichern ohne Aenderung weicht vom eingefrorenen Blob ab (verlorener/veraenderter Schluessel?)'
		);
	});
});

describe('AC-22 — Payload-Regeln (unabhaengig von der Golden-D-Datei, D-1-foermiger Blob inline)', () => {
	test('ohne_aenderung_erhaelt_unbekannten_schluessel_und_alle_vier_kanaele', async () => {
		const mod = await ladeModul();
		const rc = d1Blob();
		const nach = speichernOhneAenderung(mod, rc);
		assert.equal(nach.change_threshold_wind_kmh, 25, 'unbekannter Schluessel verloren');
		assert.equal(nach.email_format, 'compact', 'Mail-Inhalt-Schluessel verloren');
		assert.equal(nach.send_email, true, 'send_email verloren/veraendert');
		assert.equal(nach.send_telegram, true, 'send_telegram verloren/veraendert');
		assert.equal(nach.send_sms, true, 'send_sms verloren/veraendert');
		assert.equal(nach.send_premium_sms, true, 'send_premium_sms verloren/veraendert');
		assert.equal(nach.telegram_style, 'kurzform', 'telegram_style verloren/veraendert');
		// Ohne Nutzereingabe bleibt der Slot-Zustand des Blobs bestehen.
		assert.equal(nach.enabled, true);
		assert.equal(nach.morning_enabled, true);
		assert.equal(nach.evening_enabled, false, 'Abend aus wurde beim Zurueckschreiben umgedreht');
		assert.equal(nach.morning_time, '06:00:00');
		assert.equal(nach.evening_time, '20:00:00');
	});

	test('abend_aus_schreibt_enabled_true_evening_false_morning_true', async () => {
		const mod = await ladeModul();
		// Ausgangslage: beide Slots an (Altdaten ohne Per-Slot-Schluessel, enabled=true).
		const rc: Blob = { enabled: true, morning_time: '07:00:00', evening_time: '18:00:00', send_email: true };
		const zustand = { ...mod.ladeReportZustand(rc), evening_enabled: false };
		const nach = mod.baueReportConfigPayload({ snapshot: rc, live: rc, zustand });
		assert.equal(nach.enabled, true, 'Abend aus darf den Gesamtschalter NICHT abschalten');
		assert.equal(nach.evening_enabled, false, 'evening_enabled muss false sein');
		assert.equal(nach.morning_enabled, true, 'morning_enabled muss true bleiben');
	});

	test('beide_aus_schreibt_enabled_false', async () => {
		const mod = await ladeModul();
		const rc = d1Blob();
		const zustand = { ...mod.ladeReportZustand(rc), morning_enabled: false, evening_enabled: false };
		const nach = mod.baueReportConfigPayload({ snapshot: rc, live: rc, zustand });
		assert.equal(nach.enabled, false, 'beide aus => enabled=false');
		assert.equal(nach.morning_enabled, false);
		assert.equal(nach.evening_enabled, false);
		// Unbekannter Schluessel und Kanaele ueberleben auch das Abschalten.
		assert.equal(nach.change_threshold_wind_kmh, 25);
		assert.equal(nach.send_premium_sms, true);
	});

	test('nutzeraenderung_erhaelt_unbekannten_schluessel_und_kanal_schalter', async () => {
		const mod = await ladeModul();
		const rc = d1Blob();
		// Nutzer schaltet nur die Morgen-Zeit um — alles andere darf nicht wackeln.
		const zustand = { ...mod.ladeReportZustand(rc), morning_time: '08:00' };
		const nach = mod.baueReportConfigPayload({ snapshot: rc, live: rc, zustand });
		assert.equal(nach.morning_time, '08:00:00', 'HH:MM muss als HH:MM:SS geschrieben werden');
		assert.equal(nach.change_threshold_wind_kmh, 25, 'unbekannter Schluessel verloren');
		for (const k of ['send_email', 'send_telegram', 'send_sms', 'send_premium_sms']) {
			assert.equal(nach[k], true, `${k} verloren/veraendert`);
		}
	});

	test('lade_zustand_folgt_der_slot_regel_bei_altdaten_ohne_per_slot_schluessel', async () => {
		const mod = await ladeModul();
		// AC-24 (Startzustand der Hydration): enabled=true ohne Per-Slot, ohne Zeiten => beide an.
		const an = mod.ladeReportZustand({ enabled: true });
		assert.equal(an.morning_enabled, true, 'Morgen muss an sein');
		assert.equal(an.evening_enabled, true, 'Abend muss an sein');
		const aus = mod.ladeReportZustand({ enabled: false, morning_enabled: true, evening_enabled: true });
		assert.equal(aus.morning_enabled, false, 'Gesamtschalter aus ueberstimmt Per-Slot an');
		assert.equal(aus.evening_enabled, false, 'Gesamtschalter aus ueberstimmt Per-Slot an');
	});
});
