// Issue #2654 (i18n F5, Epic #2644) — gemeinsamer Pruefstand der Metrik-Namen und
// Wertebereiche (SSR-Hooks, aufgezeichnete Katalog-Daten, Funktionstabelle).
// #3020 S1: nur lebende Bausteine. Den Alt-Reiter (WeatherMetricsTab + WeatherV2*) rendert
// f5Altbausteine.ts bis zu seiner Scheibe (S3).
// Echte Svelte-Komponenten, gerendert mit svelte/server; Lade- und Fehlerzustaende kommen
// ueber f5VarianteHook.mjs (exakte Umlenkung benannter `$state`-Startwerte).
// Nutzer `golden-de`, Katalog `fixtures/metric_catalog_selectable.json`, feste Zeit
// 2026-10-29T06:00+02:00 (Spec Implementation Details 6). Weitere Antworten sind
// aufgezeichnete Backend-Daten (fixtures/f5_*.json, erzeugt aus api/routers/*.py):
// Register-Namen (label_en, col_label, sms_code), /api/sms-symbols, /api/compare/metrics.
// Golden: tests/golden/f5_wertebereiche/<fall>.de.(html|txt) = Ist-Stand VOR der
// Umstellung (nie neu schreiben); <fall>.en.* = englische Referenz, ebenfalls verglichen
// (#3024); nach gepruefter absichtlicher Aenderung neu schreiben:
//   cd frontend && GZ_GOLDEN_SCHREIBEN=en npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts
// Spec: docs/specs/modules/i18n_f5_wertebereiche_tab_2654.md
// Pfadregel #1409: alles relativ zu DIESER Datei.

import { register } from 'node:module';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

process.env.TZ = 'Europe/Berlin';

export const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> weather-metrics-tab -> shared -> components -> lib -> src -> frontend
export const FRONTEND = path.resolve(HERE, '../../../../../..');
export const WMT = path.resolve(HERE, '..');
export const SHARED = path.resolve(WMT, '..');
export const GOLDEN_DIR = path.resolve(FRONTEND, '..', 'tests', 'golden', 'f5_wertebereiche');
const basis = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);
register(pathToFileURL(path.join(HERE, 'f5VarianteHook.mjs')).href, basis);

const { render } = await import('svelte/server');
const imp = async (datei: string) => await import(pathToFileURL(datei).href);
export const komp = async (datei: string) => (await imp(datei)).default;
export const variante = async (datei: string, ersetzungen: [string, string][]) =>
	(await import(`${pathToFileURL(datei).href}?f5variante=${Buffer.from(JSON.stringify(ersetzungen)).toString('base64url')}`)).default;
const ohneKommentare = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '');
export const html = (k: unknown, props: Record<string, unknown> = {}) => ohneKommentare(render(k as never, { props } as never).body);

export const { locale, tr, trFor } = await imp(path.join(FRONTEND, 'src/lib/i18n/index.ts'));
export const { toCompareSelectionEntries } = await imp(path.join(WMT, 'compareMetricSelection.ts'));
export const { resolveTripMetricsOverviewState } = await imp(path.join(SHARED, 'trip-metrics', 'tripActiveMetricNames.ts'));
export const loader = await imp(path.join(SHARED, 'wetter-tab', 'compareMetricCatalogLoader.ts'));

const fixture = (name: string) => JSON.parse(readFileSync(path.join(HERE, 'fixtures', name), 'utf-8'));
export type Eintrag = Record<string, unknown> & { id: string; label: string };
export type Katalog = Record<string, Eintrag[]>;

/** GET /api/metrics laut Spec-Fixture (nur `label`, wie vor P1). */
export const KATALOG_ALT: Katalog = fixture('metric_catalog_selectable.json');
/** Aufgezeichnete Register-Namen je Kennung (label_en, col_label, sms_code). */
export const REGISTER_NAMEN: Record<string, { label_en: string; col_label: string; sms_code: string }> = fixture('f5_register_namen.json');
export const SMS_SYMBOLE = fixture('f5_sms_symbols.json');
export const VERGLEICH_ANTWORT = fixture('f5_compare_metrics.json');

/** Katalog wie GET /api/metrics nach P1: zusaetzlich label_en, col_label, sms_code. */
export function katalogMitRegister(ohneLabelEn: string[] = []): Katalog {
	const k: Katalog = {};
	for (const [cat, liste] of Object.entries(KATALOG_ALT)) {
		k[cat] = liste.map((m) => {
			const r = REGISTER_NAMEN[m.id];
			const e: Eintrag = { ...m, label_de: m.label, col_label: r.col_label, sms_code: r.sms_code };
			if (!ohneLabelEn.includes(m.id)) e.label_en = r.label_en;
			return e;
		});
	}
	return k;
}

export const VERGLEICH_KATALOG = () => toCompareSelectionEntries(VERGLEICH_ANTWORT);

/** Funktionsergebnisse als Tabelle `Eingabe → Ausgabe` (eine Zeile je Fall). */
export function funktionsTabelle(): string {
	const j = (v: unknown) => JSON.stringify(v);
	const z: string[] = [];
	const metriken = (ids: string[]) => ids.map((id) => ({ metric_id: id, enabled: true }));
	z.push(`resolveTripMetricsOverviewState(auswahl) → ${j(resolveTripMetricsOverviewState(metriken(['temperature', 'gust', 'snow_depth', 'gibt_es_nicht']), katalogMitRegister()))}`);
	z.push(`resolveTripMetricsOverviewState(leer) → ${j(resolveTripMetricsOverviewState([{ metric_id: 'wind', enabled: false }], KATALOG_ALT))}`);
	z.push(`thunderThresholdLevelsFromCatalog → ${j(loader.thunderThresholdLevelsFromCatalog(VERGLEICH_KATALOG()))}`);
	z.push(`deriveThunderThresholdLevels([kein,leicht,mittel,hoch]) → ${j(loader.deriveThunderThresholdLevels(['kein', 'leicht', 'mittel', 'hoch']))}`);
	return z.join('\n');
}

/** Schreibt die Golden-Dateien einer Sprache (`faelle`: Golden-Faelle HTML). */
export function schreibeGolden(lang: 'de' | 'en', faelle: Record<string, () => string> = {}): void {
	mkdirSync(GOLDEN_DIR, { recursive: true });
	locale.set(lang);
	try {
		for (const [fall, f] of Object.entries(faelle)) writeFileSync(path.join(GOLDEN_DIR, `${fall}.${lang}.html`), f() + '\n');
		writeFileSync(path.join(GOLDEN_DIR, `funktionen.${lang}.txt`), funktionsTabelle() + '\n');
	} finally {
		locale.set('de');
	}
}
