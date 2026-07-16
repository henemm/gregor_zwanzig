// TDD RED — Issue #1269 (a): Mount-Kanonisierung darf nicht als "geändert"
// zählen (Trip-Inhalt-Tab + Ortsvergleich-Layout-Tab + Versand-Tab).
//
// Spec: docs/specs/modules/issue_1269_save_status_lie.md
//   § Implementation Details Punkt 3 ("Baseline-Korrektheit"),
//   § Acceptance Criteria AC-1/AC-3
// Kontext: docs/context/fix-1269-save-status-lie.md
//   Root-Cause (a): EditReportConfigSection.svelte / VersandTab.svelte
//   normalisieren die geladene report_config beim Mounten (u.a. `toHHMMSS`:
//   "07:00" → "07:00:00", Materialisierung fehlender Default-Felder wie
//   `daily_summary_metrics`) und schreiben das Ergebnis zurück. Die
//   Baseline-Vergleichsvariable (z.B. WeatherMetricsTab.svelte
//   `_lastReportConfigJson`) wurde VOR dieser Kanonisierung eingefroren →
//   der reine Formatunterschied wird fälschlich als Nutzeränderung gewertet.
//
// Das Modul `../reportConfigDirty.ts` existiert noch NICHT → der Import
// wirft einen Modul-Resolve-Fehler und ALLE Tests in dieser Datei scheitern
// (RED) — exakt das Muster aus
// `frontend/src/lib/components/compare/__tests__/compareAutosaveGate.test.ts`.
//
// Vorgeschlagene Signatur (Kontrakt für GREEN):
//   reportConfigChangedByUser(baseline: ReportConfig | undefined, current: ReportConfig | undefined): boolean
// Reine Funktion: kanonisiert BEIDE Seiten identisch (dieselbe Normalisierung
// wie EditReportConfigSection.svelte / VersandTab.svelte beim Mounten:
// `toHHMMSS`-Zeitformat, Default-Materialisierung) und vergleicht danach
// inhaltlich. Nur wenn nach Kanonisierung ein ECHTER Unterschied bleibt,
// liefert sie `true` — reine Formatunterschiede/Default-Ergänzungen (Mount-
// Kanonisierung) ergeben `false`.
//
// Reine Verhaltenstests (echter Funktionsaufruf, KEIN Mock, KEINE
// Datei-Inhalt-Prüfung).
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/reportConfigDirty.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import type { ReportConfig } from '$lib/types';

// Direkter Funktionsaufruf — kein Mock, kein DOM.
const { reportConfigChangedByUser } = await import('../reportConfigDirty.ts');

describe('AC-1/AC-3: reine Mount-Kanonisierung (Format + Default-Ergänzung) ist KEINE Nutzeränderung', () => {
	test('rohe geladene Config vs. ihre Mount-normalisierte Form (nur toHHMMSS + Default-Materialisierung) → false', () => {
		// So kommt report_config typischerweise vom Server (Legacy-Trip, Zeiten
		// ohne Sekunden, mehrere Default-Felder fehlen noch).
		const rawLoaded: ReportConfig = {
			enabled: true,
			morning_time: '07:00',
			evening_time: '18:00',
			send_email: true
		};

		// So sieht dieselbe Config aus, NACHDEM EditReportConfigSection.svelte /
		// VersandTab.svelte beim Mounten kanonisiert und zurückgeschrieben haben
		// (toHHMMSS: "07:00" → "07:00:00"; fehlende Felder werden mit ihren
		// UI-Defaults materialisiert) — OHNE dass der Nutzer etwas angefasst hat.
		const mountCanonicalized: ReportConfig = {
			enabled: true,
			morning_enabled: true,
			evening_enabled: true,
			morning_time: '07:00:00',
			evening_time: '18:00:00',
			send_email: true,
			send_telegram: false,
			send_sms: false,
			multi_day_trend_morning: false,
			multi_day_trend_evening: false,
			multi_day_trend_reports: [],
			show_compact_summary: true,
			show_daylight: true,
			wind_exposition_min_elevation_m: null,
			show_stage_stats: true,
			show_quick_take_tags: true,
			show_stability: true,
			show_highlights: true,
			daily_summary_metrics: ['precipitation', 'wind', 'visibility', 'thunder'],
			show_metrics_summary: false,
			show_outlook: true,
			email_format: 'full'
		};

		assert.equal(
			reportConfigChangedByUser(rawLoaded, mountCanonicalized),
			false,
			'AC-1/AC-3: reine Formatkonvertierung (HH:MM→HH:MM:SS) + Default-Ergänzung beim Mounten darf ' +
				'NICHT als Nutzeränderung gezählt werden — sonst zeigt der Tab faelschlich "Nicht gespeichert", ' +
				'obwohl der Nutzer nichts angefasst hat'
		);
	});

	test('identische, bereits kanonisierte Config gegen sich selbst → false (triviale Gegenprobe)', () => {
		const cfg: ReportConfig = {
			morning_enabled: true,
			evening_enabled: true,
			morning_time: '07:00:00',
			evening_time: '18:00:00',
			send_email: true,
			send_telegram: false,
			send_sms: false
		};
		assert.equal(reportConfigChangedByUser(cfg, { ...cfg }), false);
	});
});

describe('Gegenprobe: eine ECHTE inhaltliche Änderung bleibt "dirty" (darf NICHT durch die Kanonisierung verschluckt werden)', () => {
	test('morning_time "07:00" → "09:00" (echte Nutzeränderung, keine reine Formatfrage) → true', () => {
		const baseline: ReportConfig = {
			morning_enabled: true,
			evening_enabled: true,
			morning_time: '07:00:00',
			evening_time: '18:00:00',
			send_email: true,
			send_telegram: false,
			send_sms: false
		};
		const afterUserEdit: ReportConfig = {
			...baseline,
			morning_time: '09:00:00'
		};

		assert.equal(
			reportConfigChangedByUser(baseline, afterUserEdit),
			true,
			'eine tatsächlich geänderte Uhrzeit ist eine echte Nutzeränderung und MUSS weiterhin "dirty" auslösen — ' +
				'die Baseline-Korrektheit darf echte Änderungen nicht verschlucken (Silent-Data-Loss-Klasse, s. #1234)'
		);
	});

	test('send_telegram false → true (echter Kanal-Toggle) → true', () => {
		const baseline: ReportConfig = {
			morning_time: '07:00:00',
			send_email: true,
			send_telegram: false,
			send_sms: false
		};
		const afterUserEdit: ReportConfig = {
			...baseline,
			send_telegram: true
		};
		assert.equal(reportConfigChangedByUser(baseline, afterUserEdit), true);
	});
});
