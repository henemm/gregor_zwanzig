// erzeuge_report_config_nach_speichern.ts -- Issue #2422 S3 (AC-22): Generator
// fuer die eingefrorene Datei
// tests/fixtures/einstellung_auslieferung/report_config_nach_speichern_golden_d.json
//
// SPEC: docs/specs/modules/fix_2422_s3_kanal_an_aus_kette.md ("Golden D").
//
// KEIN Test-Modul (kein `.test.`-Suffix -> node:test sammelt es nicht ein,
// Konvention wie weather-metrics-tab/__tests__/erzeuge_nach_dateien.ts).
// Nutzt AUSSCHLIESSLICH die echte Helferkette der Editoren
// (`ladeReportZustand` -> `baueReportConfigPayload`, reportConfigPayload.ts) --
// dieselbe, die report_config_serialisierung_golden.test.ts prueft.
//
// PFLICHT-REIHENFOLGE (Spec): erst NACH den Produktivfixes ausfuehren, sonst
// friert die Datei den alten Stand ein.
//
// Lauf (Opt-in-Umgebungsvariable -- verhindert versehentliches Schreiben):
//   cd frontend && GZ_ERZEUGE_NACH_DATEIEN=1 node --import ./test-lib-loader.mjs \
//     --experimental-strip-types \
//     src/lib/components/shared/versand-tab/__tests__/erzeuge_report_config_nach_speichern.ts

import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { baueReportConfigPayload, ladeReportZustand } from '../reportConfigPayload.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE_DIR = path.resolve(__dirname, '../../../../../../../tests/fixtures/einstellung_auslieferung');

if (process.env.GZ_ERZEUGE_NACH_DATEIEN !== '1') {
	console.error('Abbruch: GZ_ERZEUGE_NACH_DATEIEN=1 setzen, um die eingefrorene Datei zu schreiben.');
	process.exit(1);
}

const golden = JSON.parse(readFileSync(path.join(FIXTURE_DIR, 'golden_d.json'), 'utf-8'));
const rc = golden.report_config as Record<string, unknown>;
const nach = baueReportConfigPayload({ snapshot: rc, live: rc, zustand: ladeReportZustand(rc) });

const ziel = path.join(FIXTURE_DIR, 'report_config_nach_speichern_golden_d.json');
writeFileSync(ziel, JSON.stringify(nach, null, 2) + '\n', 'utf-8');
console.log(`geschrieben: ${ziel}`);
