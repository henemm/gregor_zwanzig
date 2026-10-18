// TDD RED/GUARD — Issue #2278 (Epic #2345 P3), AC-9 (+ AC-8: ReportConfigDialog existiert nicht mehr).
// Spec: docs/specs/modules/feat_2278_aktionsmodell.md — Implementation Details 4.
//
// Gemessener Defekt des Alt-Dialogs: `saveReportConfig` sendete `{...full, report_config: reportConfig}`
// und ERSETZTE `report_config` komplett; `send_premium_sms` und alle dem Dialog unbekannten Felder
// gingen verloren (Verstoss gegen Read-Modify-Write, CLAUDE.md "Daten-Schema-Reworks").
// Der Ersatz ist der geteilte Versand-Tab (`baueReportConfigPayload` -> `mergeReportConfig`).
//
//   - GUARD (heute schon gruen, bewacht den Ersatzweg): Roundtrip ueber den Versand-Tab-Payload
//     erhaelt send_premium_sms, die Alt-Schwellen change_threshold_*/alert_on_changes und ein
//     unbekanntes Feld. (Ortsvergleich hat keinen report_config-Blob; sein Versand-Speichern sendet nur
//     Eigenfelder, bewacht durch compare_reiter_nutzlast_nur_eigene_felder.test.ts.)
//   - RED: der Alt-Weg existiert noch: ReportConfigDialog.svelte liegt noch im Baum und wird von
//     routes/trips/+page.svelte importiert (Import per AST, nicht per Text-Grep).
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/versand-tab/__tests__/versand_speichern_erhaelt_report_config.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';

import { baueReportConfigPayload, ladeReportZustand } from '../reportConfigPayload.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> versand-tab -> shared -> components -> lib -> src
const SRC = path.resolve(HERE, '../../../../..');

const ALT_BESTAND = {
	enabled: true,
	send_email: true,
	send_telegram: false,
	send_sms: false,
	send_premium_sms: true,
	morning_time: '06:30:00',
	evening_time: '18:00:00',
	change_threshold_temp_c: 4.5,
	change_threshold_wind_kmh: 18,
	change_threshold_precip_mm: 2.5,
	alert_on_changes: true,
	dem_unbekanntes_dialog_feld: { nested: [1, 2, 3] }
};

describe('AC-9 (Guard): Speichern ueber den Versand-Tab erhaelt Bestandsfelder', () => {
	test('Roundtrip: send_premium_sms, Alt-Schwellen, alert_on_changes und Unbekanntes bleiben', () => {
		const zustand = ladeReportZustand(ALT_BESTAND);
		// Nutzer schaltet nur Telegram ein.
		const payload = baueReportConfigPayload({
			snapshot: ALT_BESTAND,
			live: ALT_BESTAND,
			zustand: { ...zustand, send_telegram: true }
		});
		assert.equal(payload.send_telegram, true, 'die Aenderung selbst ging verloren');
		assert.equal(payload.send_premium_sms, true);
		assert.equal(payload.change_threshold_temp_c, 4.5);
		assert.equal(payload.change_threshold_wind_kmh, 18);
		assert.equal(payload.change_threshold_precip_mm, 2.5);
		assert.equal(payload.alert_on_changes, true);
		assert.deepEqual(payload.dem_unbekanntes_dialog_feld, { nested: [1, 2, 3] });
	});

	test('Roundtrip ohne Aenderung: kein Feld des Bestands faellt weg', () => {
		const payload = baueReportConfigPayload({
			snapshot: ALT_BESTAND,
			live: ALT_BESTAND,
			zustand: ladeReportZustand(ALT_BESTAND)
		});
		for (const feld of Object.keys(ALT_BESTAND)) {
			assert.ok(feld in payload, `Feld ${feld} fehlt nach dem Speichern`);
		}
	});

	test('Instanz ohne Kanalzeige (Mail-Inhalt) schreibt send_premium_sms nicht zurueck', () => {
		const payload = baueReportConfigPayload({
			snapshot: ALT_BESTAND,
			live: ALT_BESTAND,
			zustand: { ...ladeReportZustand(ALT_BESTAND), send_premium_sms: false },
			showChannels: false,
			showSchedule: false
		});
		assert.equal(payload.send_premium_sms, true);
	});
});

describe('AC-9/AC-8 (RED): kein Weg in der Oberflaeche ersetzt report_config mehr komplett', () => {
	test('ReportConfigDialog.svelte ist geloescht', () => {
		assert.equal(
			existsSync(path.join(SRC, 'lib/components/molecules/ReportConfigDialog.svelte')),
			false,
			'molecules/ReportConfigDialog.svelte existiert noch (Replace-Weg auf report_config)'
		);
	});

	test('routes/trips/+page.svelte importiert weder ReportConfigDialog noch TestReportDialog', () => {
		const ast: any = parse(readFileSync(path.join(SRC, 'routes/trips/+page.svelte'), 'utf-8'), { modern: true });
		const quellen: string[] = [];
		(function visit(n: any) {
			if (n === null || typeof n !== 'object') return;
			if (Array.isArray(n)) return void n.forEach(visit);
			if (n.type === 'ImportDeclaration') {
				quellen.push(String(n.source.value));
				// Importe laufen auch ueber die Barrel-Datei molecules/index.ts: Namen zaehlen mit.
				for (const s of n.specifiers ?? []) quellen.push(String(s.local?.name ?? ''));
			}
			for (const k of Object.keys(n)) if (k !== 'parent') visit(n[k]);
		})(ast.instance);
		assert.ok(!quellen.some((q) => /ReportConfigDialog/.test(q)), 'ReportConfigDialog wird noch importiert');
		assert.ok(!quellen.some((q) => /TestReportDialog/.test(q)), 'TestReportDialog wird noch importiert');
	});
});
