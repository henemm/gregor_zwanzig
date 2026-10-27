// erzeuge_nach_dateien.ts -- Issue #2422 S2a: Generator fuer die
// eingefrorenen "Speichern ohne Aenderung"- und "Aenderungspfad"-Dateien.
//
// SPEC: docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md
// ("Zweigliedrige ... Kette", "Vierter Baustein: Aenderungspfad").
//
// KEIN Test-Modul (kein `.test.`-Suffix -> node:test sammelt es nicht ein,
// Konvention wie `_editor_kette.ts`/`wetterMetrikenVergleichPruefstand.ts`).
// Nutzt AUSSCHLIESSLICH die geteilte Kette `_editor_kette.ts` -- dieselbe
// Nachbau-Logik wie AC-3/AC-4/AC-7/AC-14, damit Generator und Tests niemals
// auseinanderlaufen koennen.
//
// PFLICHT-REIHENFOLGE (Spec, "Implementierungsreihenfolge"): dieses Skript
// wird in /50 ERST NACH dem B9-Fix (trip_report.py) und dem K8-Fix
// (buildWeatherConfigMetrics/mergeAllChannelLayoutsForSave, 5.
// Parameter/Kanal-Parameter) ausgefuehrt -- sonst frieren die erzeugten
// Dateien den ALTEN, fehlerhaften Stand ein (AC-5 waere dann bei Golden C
// legitim rot, weil `nach_speichern_golden_c.json` selbst falsch waere).
//
// NICHT in dieser RED-Phase ausfuehren (Testauflage PO). Lauf NACH /50
// (Opt-in-Umgebungsvariable, s.u. -- verhindert versehentliches Schreiben):
//   cd frontend && GZ_ERZEUGE_NACH_DATEIEN=1 node --import ./test-lib-loader.mjs \
//     --experimental-strip-types \
//     src/lib/components/shared/weather-metrics-tab/__tests__/erzeuge_nach_dateien.ts

import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
	baueSpeichernPayload,
	berechneAnzeige,
	flacherMerge,
	ladeInEditorState,
	speichernOhneAenderung,
	wendeAenderungAn,
	type Aenderungsfall,
	type GoldenTrip,
	type MinimalCatalog,
} from './_editor_kette.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE_DIR = path.resolve(__dirname, '../../../../../../../tests/fixtures/einstellung_auslieferung');

function ladeGolden(name: string): GoldenTrip {
	return JSON.parse(readFileSync(path.join(FIXTURE_DIR, `${name}.json`), 'utf-8'));
}
function schreibeJson(dateiname: string, wert: unknown): void {
	const ziel = path.join(FIXTURE_DIR, dateiname);
	writeFileSync(ziel, JSON.stringify(wert, null, 2) + '\n', 'utf-8');
	console.log(`geschrieben: ${ziel}`);
}

const catalog: MinimalCatalog = JSON.parse(
	readFileSync(path.join(__dirname, 'fixtures', 'metric_catalog_selectable.json'), 'utf-8'),
);

function erzeugeNachSpeichern(): void {
	for (const name of ['golden_a', 'golden_b', 'golden_c']) {
		const golden = ladeGolden(name);
		schreibeJson(`nach_speichern_${name}.json`, speichernOhneAenderung(golden, catalog));
	}
}

function erzeugeNachAenderung(): void {
	const faelle: Record<string, Aenderungsfall & { golden: string }> = JSON.parse(
		readFileSync(path.join(FIXTURE_DIR, 'aenderungsfaelle.json'), 'utf-8'),
	);
	for (const [fall, definition] of Object.entries(faelle)) {
		const golden = ladeGolden(definition.golden);
		const stateVorher = ladeInEditorState(golden, catalog);
		const stateNachher = wendeAenderungAn(stateVorher, definition);

		const anzeige = berechneAnzeige(stateNachher);
		schreibeJson(`nach_aenderung_${fall}_anzeige.json`, { channels: anzeige });

		const payload = baueSpeichernPayload(golden, stateNachher, catalog);
		schreibeJson(`nach_aenderung_${fall}.json`, flacherMerge(golden, payload));
	}
}

function main(): void {
	erzeugeNachSpeichern();
	erzeugeNachAenderung();
}

// Sicherung gegen versehentliches Ausfuehren (z.B. falls ein Test-Runner-Glob
// diese Datei je erfassen sollte, obwohl sie -- wie `_editor_kette.ts` und
// `wetterMetrikenVergleichPruefstand.ts` -- bewusst KEIN `.test.`-Suffix
// traegt): nur bei explizitem Opt-in schreiben. Sonst wuerde ein
// versehentlicher Lauf VOR dem B9-/K8-Fix die `nach_*`-Dateien mit dem alten,
// fehlerhaften Stand einfrieren und AC-4/AC-14 falsch-gruen machen (sie
// vergleichen dann die Kette nur gegen sich selbst).
if (process.env.GZ_ERZEUGE_NACH_DATEIEN === '1') {
	main();
}
