// Pruefstand fuer die node-Tests der Karte „Inhalt je Kanal und Fläche" (#3031, A1).
// Spec: docs/specs/modules/feat_3031_inhalt_je_kanal_listen.md
//
// Keine .test.ts-Datei — nur Aufbauhilfen fuer:
//   organisms/__tests__/kanal_inhalt_3031_modell.test.ts
//   organisms/__tests__/kanal_inhalt_3031_karte.test.ts
//   shared/wetter-tab/__tests__/kanal_inhalt_3031_speicherung.test.ts
//
// Grundsaetze (wie wetterTabDaten.ts):
//   - Metrik-Eigenschaften (col_label, sms_code, format_modes, default_format_mode,
//     has_friendly_format) kommen aus dem ECHTEN Katalog (`/api/metrics` = Python
//     `get_metrics()`), nie aus einer Frontend-Kopie.
//   - Was „wirkt", misst die ECHTE Python-Kaskade: `load_trip` +
//     `get_metrics_for_channel(kanal, 'evening')` liefert je Kanal die Metriken in der
//     Reihenfolge und mit der Roh/Einfach-Wahl, die die Renderer ausgeben (Orakel).
//   - Neue Module werden DYNAMISCH geladen: fehlt eins (TDD RED), wird jeder Test einzeln
//     mit „Modul fehlt" rot statt die ganze Datei beim Import abzubrechen.

import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

import { live, REPO, type Json } from './wetterTabDaten.ts';

/** organisms/wetter-tab — Heimat der neuen Karte und ihres Zeilenmodells (Spec „Source"). */
export const ORGANISMUS = resolve(REPO, 'frontend', 'src', 'lib', 'components', 'organisms', 'wetter-tab');

async function ladeOrganismus(datei: string): Promise<Json> {
	const pfad = join(ORGANISMUS, datei);
	if (!existsSync(pfad)) assert.fail(`TDD RED: organisms/wetter-tab/${datei} fehlt (Modul noch nicht angelegt)`);
	return import(pathToFileURL(pfad).href);
}

/** Zeilenmodell, Normalisierung, Adapter (Spec: kanalInhalt.ts). */
export const kanalInhalt = () => ladeOrganismus('kanalInhalt.ts');
/** Beispielwerte Roh/Einfach je Metrik, DE/EN (Spec: kanalInhaltBeispiele.ts). */
export const kanalInhaltBeispiele = () => ladeOrganismus('kanalInhaltBeispiele.ts');

export type KatalogEintrag = {
	id: string;
	label: string;
	col_label?: string;
	sms_code?: string;
	format_modes?: string[];
	default_format_mode?: string;
	has_friendly_format?: boolean;
};

/** Echter Metrik-Katalog nach Kennung (`/api/metrics`, Gruppen flach gezogen). */
export function katalogNachId(): Record<string, KatalogEintrag> {
	const aus: Record<string, KatalogEintrag> = {};
	for (const liste of Object.values(live().metrics)) for (const e of liste as KatalogEintrag[]) aus[e.id] = e;
	return aus;
}

/** Standard-Darstellung einer neuen Zeile laut Katalog: `default_format_mode` ≠ raw ⇒ Einfach. */
export function formatAusKatalog(id: string): 'roh' | 'einfach' {
	const e = katalogNachId()[id];
	return e && e.default_format_mode && e.default_format_mode !== 'raw' ? 'einfach' : 'roh';
}

/** Hat die Metrik laut Katalog eine echte Roh/Einfach-Wahl? (mehr als ein Format-Modus) */
export function hatWahlLautKatalog(e: KatalogEintrag): boolean {
	return (e.format_modes ?? []).length > 1 || e.has_friendly_format === true;
}

export type OrakelZeile = [id: string, einfach: boolean];
export type OrakelStand = Record<'email' | 'telegram' | 'sms', OrakelZeile[]>;

const PY_ORAKEL = [
	'import sys, json',
	"sys.path.insert(0, 'src'); sys.path.insert(0, '.')",
	'from app.loader import load_trip',
	'e = json.loads(sys.stdin.read())',
	"t = load_trip({'id': 'orakel-3031', 'name': 'orakel', 'stages': [], 'display_config': e['display_config']}, user_id='orakel-3031')",
	'dc = t.display_config',
	"print(json.dumps({ch: [[m.metric_id, bool(m.use_friendly_format)] for m in dc.get_metrics_for_channel(ch, 'evening')] for ch in ('email', 'telegram', 'sms')}))"
].join('\n');

/**
 * Was die Renderer je Kanal ausliefern wuerden (Trip): echte Python-Kaskade auf einer
 * gespeicherten `display_config` — Reihenfolge (nach Python-Sortierregel), Auswahl
 * (Schnitt gegen die Wetter-Liste, enabled) und Roh/Einfach (`use_friendly_format`).
 */
export function pythonKanalStand(displayConfig: Json): OrakelStand {
	const stdout = execFileSync('uv', ['run', 'python3', '-c', PY_ORAKEL], {
		cwd: REPO,
		encoding: 'utf-8',
		input: JSON.stringify({ display_config: displayConfig }),
		maxBuffer: 32 * 1024 * 1024
	});
	return JSON.parse(stdout.trim());
}

/** Go-Merge des Trip-Wetter-PUT (`mergeConfigMap`, config_merge.go): Top-Level-Schluessel ersetzen. */
export function goMergeDisplayConfig(dc: Json, teil: Json): Json {
	return { ...structuredClone(dc ?? {}), ...structuredClone(teil ?? {}) };
}

/** Kennung eines Eintrags in `channel_active_metrics` (String oder `{metric_id}`). */
export function aktivId(e: unknown): string {
	return typeof e === 'string' ? e : String((e as { metric_id?: string })?.metric_id);
}
