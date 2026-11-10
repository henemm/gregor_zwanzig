// Pruefstand-Daten fuer die node-Tests des Reiters Wetter (Issue #2794 S3a, Teil-PR 3).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md
//
// Keine .test.ts-Datei: wird nur von den Tests unter wetter-tab/__tests__/ importiert.
//
// Grundsatz (Spec, Implementation Details §1): Vorlagen-Ampeln und Metrik-Eigenschaften
// kommen NIE aus einer Frontend-Kopie. Die Tests holen sie deshalb aus denselben
// Python-Funktionen, die `/api/templates` und `/api/metrics` im Betrieb beantworten
// (Muster metricKuerzelLegende.test.ts: `uv run python3 -c …` im Repo-Wurzelverzeichnis).
//
// Die Module des Reiters werden DYNAMISCH geladen: fehlt ein Modul (TDD RED), wird
// jeder Test einzeln mit „Modul fehlt“ rot statt die ganze Datei beim Import abzubrechen.

import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HIER = dirname(fileURLToPath(import.meta.url));
/** __tests__ -> wetter-tab -> shared -> components -> lib -> src -> frontend -> Repo */
export const REPO = resolve(HIER, '..', '..', '..', '..', '..', '..', '..');
export const WETTER_TAB = resolve(HIER, '..');
export const FRONTEND = join(REPO, 'frontend');
export const FIXTURES = join(REPO, 'tests', 'fixtures');

export type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any

const PY = [
	'import sys, json',
	"sys.path.insert(0, 'src'); sys.path.insert(0, '.')",
	'from api.routers.config import get_metrics, get_templates',
	"print(json.dumps({'metrics': get_metrics(), 'templates': get_templates()}, ensure_ascii=False))"
].join('\n');

let cache: { metrics: Json; templates: Json[] } | null = null;

/** Die echten Antworten von `/api/metrics` und `/api/templates` (Python-Core). */
export function live(): { metrics: Record<string, Json[]>; templates: Json[] } {
	if (!cache) {
		const stdout = execFileSync('uv', ['run', 'python3', '-c', PY], {
			cwd: REPO,
			encoding: 'utf-8',
			maxBuffer: 32 * 1024 * 1024
		});
		cache = JSON.parse(stdout.trim());
	}
	return structuredClone(cache!);
}

const PY_VERGLEICHS_KATALOG = [
	'import sys, json',
	"sys.path.insert(0, 'src'); sys.path.insert(0, '.')",
	'from output.renderers.compare_metric_catalog import get_compare_metric_catalog',
	"print(json.dumps({'metrics': get_compare_metric_catalog(lang='de')}, ensure_ascii=False))"
].join('\n');

let vergleichsCache: Json | null = null;

/** Die echte Antwort von `GET /api/compare/metrics` (Python-Core, Fix-Loop 4). */
export function liveVergleichsKatalog(): Json {
	if (!vergleichsCache) {
		vergleichsCache = JSON.parse(
			execFileSync('uv', ['run', 'python3', '-c', PY_VERGLEICHS_KATALOG], { cwd: REPO, encoding: 'utf-8', maxBuffer: 32 * 1024 * 1024 }).trim()
		);
	}
	return structuredClone(vergleichsCache);
}

/** Ersetzt `globalThis.fetch` fuer `/api/compare/metrics` (Katalog-Lader des WetterTab nutzt das
 *  globale `api`); `ok()` steuert, ob der Abruf gelingt. Rueckgabe: Wiederherstellen. */
export function vergleichsKatalogFetch(ok: () => boolean = () => true): () => void {
	const vorher = globalThis.fetch;
	(globalThis as { fetch: unknown }).fetch = async (input: unknown) => {
		const pfad = new URL(String(input), 'http://gz.invalid').pathname;
		if (pfad === '/api/compare/metrics') {
			return ok()
				? new Response(JSON.stringify(liveVergleichsKatalog()), { status: 200, headers: { 'Content-Type': 'application/json' } })
				: new Response('{"detail":"kaputt"}', { status: 503, headers: { 'Content-Type': 'application/json' } });
		}
		return new Response('{}', { status: 404 });
	};
	return () => {
		(globalThis as { fetch: unknown }).fetch = vorher;
	};
}

const PY_AUFLOESEN = [
	'import sys, json',
	"sys.path.insert(0, 'src'); sys.path.insert(0, '.')",
	'from app.ampel import resolve_ampel',
	'eingaben = json.loads(sys.stdin.read())',
	"print(json.dumps([resolve_ampel({'display_config': {'ampel': a}}) for a in eingaben], ensure_ascii=False))"
].join('\n');

/** Python-Referenz `resolve_ampel` fuer eine Liste von Abo-Ampeln (Vergleichswert fuer den Spiegel). */
export function pythonAufloesen(ampeln: Json[]): Json[] {
	const stdout = execFileSync('uv', ['run', 'python3', '-c', PY_AUFLOESEN], {
		cwd: REPO,
		encoding: 'utf-8',
		input: JSON.stringify(ampeln),
		maxBuffer: 32 * 1024 * 1024
	});
	return JSON.parse(stdout.trim());
}

/** Ampel ohne offene (null) Grenzwerte — Python kopiert `None`, ein Spiegel darf sie weglassen. */
export function ohneOffene(ampel: Json): Json {
	const k = structuredClone(ampel);
	for (const e of Object.values((k?.metrics ?? {}) as Record<string, Json>)) {
		for (const seite of ['lower', 'upper']) {
			const s = e[seite] ?? {};
			for (const f of Object.keys(s)) if (s[f] === null || s[f] === undefined) delete s[f];
			e[seite] = s;
		}
	}
	return k;
}

/** Lies eine JSON-Fixture aus `tests/fixtures/` (gemeinsam mit pytest). */
export function fixture(name: string): Json {
	const pfad = join(FIXTURES, name);
	assert.ok(existsSync(pfad), `Fixture fehlt: tests/fixtures/${name}`);
	return JSON.parse(readFileSync(pfad, 'utf-8'));
}

async function lade(datei: string): Promise<Json> {
	const pfad = join(WETTER_TAB, datei);
	if (!existsSync(pfad)) {
		assert.fail(`TDD RED: shared/wetter-tab/${datei} fehlt (Modul noch nicht angelegt)`);
	}
	return import(pathToFileURL(pfad).href);
}

export const ampelModell = () => lade('ampelModell.ts');
export const ampelSchreiben = () => lade('ampelSchreiben.ts');
export const amtlicheWarnungen = () => lade('amtlicheWarnungen.ts');

/** DE-/EN-Katalog des Bereichs `wetter` (Datei fehlt -> Test rot mit klarer Meldung). */
export function wetterKatalog(lang: 'de' | 'en'): Record<string, string> {
	const pfad = join(FRONTEND, 'src', 'lib', 'i18n', 'messages', lang, 'wetter.json');
	assert.ok(existsSync(pfad), `TDD RED: Katalog messages/${lang}/wetter.json fehlt`);
	return JSON.parse(readFileSync(pfad, 'utf-8'));
}

/** Platzhalter eines Katalogtexts (`{name}`), sortiert und ohne Doppelte. */
export function platzhalter(text: string): string[] {
	return [...new Set([...text.matchAll(/\{([a-z0-9_]+)\}/g)].map((m) => m[1]))].sort();
}

/**
 * Prueft ein „Katalogschluessel + Platzhalter“-Modell gegen den DE-Katalog: der Schluessel
 * existiert im Bereich `wetter`, und die Platzhalter des Texts sind genau die Schluessel von
 * `werte` (keine Satzkonkatenation, kein fehlender oder ueberzaehliger Wert).
 */
export function pruefeKatalogModell(modell: { schluessel: string; werte?: Record<string, unknown> }, wo: string): void {
	assert.equal(typeof modell?.schluessel, 'string', `${wo}: Modell ohne Katalogschluessel (${JSON.stringify(modell)})`);
	assert.match(modell.schluessel, /^wetter\.[a-z0-9_.]+$/, `${wo}: Schluessel nicht im Bereich wetter: ${modell.schluessel}`);
	const de = wetterKatalog('de');
	assert.ok(modell.schluessel in de, `${wo}: Schluessel ${modell.schluessel} fehlt in de/wetter.json`);
	assert.deepEqual(
		platzhalter(de[modell.schluessel]),
		Object.keys(modell.werte ?? {}).sort(),
		`${wo}: Platzhalter von ${modell.schluessel} („${de[modell.schluessel]}“) passen nicht zu werte ${JSON.stringify(modell.werte)}`
	);
}
