// TDD RED — Issue #1453, AC-7: die Konfiguration zeigt je Wettergroesse ALLE
// DREI Namensformen (ausgeschriebener deutscher Name · englische Fachkurzform ·
// SMS-Kuerzel) — und zwar in ALLEN VIER Editoren, nicht nur im Touren-Editor.
//
// Warum: ein Kuerzel in einer Mail ("Dew") oder einer SMS ("DP") muss an
// mindestens einer Stelle in der Oberflaeche aufloesbar sein. Alle drei Formen
// liegen im zentralen Register und werden von GET /api/metrics bereits
// ausgeliefert (`label`/`col_label`/`sms_code`) — AC-7 ist eine
// Darstellungs-, keine Datenaufgabe. Heute zeigt nur der Touren-Editor die
// englische Kurzform als Marke (WeatherV2Reihenfolge.svelte:80-81); das
// SMS-Kuerzel erscheint nirgends, und die drei Compare-Flaechen bauen ihre
// Zeilen-Eintraege ganz ohne `col_label`/`sms_code` auf.
//
// Die vier Editoren:
//   1. Touren-Editor            WeatherMetricsTab.svelte (context="route")
//   2. Compare-Uebersicht       WeatherMetricsTab.svelte (context="vergleich")
//   3. Compare-Stundenverlauf   CompareHourlyLayoutControls.svelte
//   4. Compare-Ausblick         CompareOutlookLayoutControls.svelte
//
// DIE DARSTELLUNGSFORM IST BEWUSST OFFEN (Spec, Implementation Details 5):
// Zeile je Groesse ODER ausklappbare Legende am Ende des Reiters — das
// entscheidet der PO am fertigen Bildschirm. Dieser Test prueft deshalb NUR
// die ANWESENHEIT aller drei Formen, nicht ihre Anordnung, nicht ihr Markup,
// nicht ihre Reihenfolge.
//
// Grund fuer AST statt DOM: dieses Repo hat kein vitest/jsdom (package.json
// "test": node --test). Der Test parst die Komponenten mit dem ECHTEN
// Svelte-5-Compiler und inspiziert Template-/Instance-Script-AST — kein
// verbotener Dateiinhalt-Vergleich.
//
// Spec: docs/specs/modules/fix_1453_namensformen.md (AC-7)
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/weather_metric_name_forms_visible.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const SHARED = join(here, '..');
const LIB = resolve(here, '..', '..', '..'); // frontend/src/lib

/** Die drei Namensformen, die eine Zeile je Groesse zeigen muss.
 *
 *  #1719 S4: die dritte Form heisst nicht mehr `sms_code`. Der Wert war eine
 *  ANNAHME dieses Waechters ("sms_code IST das SMS-Kuerzel") — und genau die
 *  war bei 5 von 25 Groessen falsch: die Trip-SMS sendet fuer
 *  `temperature_night` ein `N`, das Register fuehrt `TN`. Seit S4 richtet
 *  sich die Quelle nach der FLAECHE (Touren: /api/sms-symbols ueber
 *  `kuerzelById`; Vergleich: Register-`sms_code`, ebenfalls ueber
 *  `kuerzelById`), weil Trip und Vergleich aus verschiedenen Tabellen senden.
 *
 *  Geprueft wird unveraendert die ANWESENHEIT aller drei Formen je Editor —
 *  nur nicht mehr die Herkunft der dritten. Teil 2 dieses Waechters (unten)
 *  prueft weiterhin namentlich `sms_code`: dort geht es um die
 *  Datengrundlage der Vergleichs-Eintraege, und die ist das Register. */
const FORMEN = ['label', 'col_label', 'kurzform'] as const;

/** Namen, unter denen die Kurzform-Kuerzel in eine Zeile gelangen. Mehrere,
 *  weil die Quelle flaechenabhaengig ist (s.o.) — nicht als Aufweichung: es
 *  muss weiterhin GENAU EINE Flaeche je Editor geben, die alle drei Formen
 *  traegt. */
const KURZFORM_QUELLEN = ['sms_code', 'kuerzelById', 'sms_symbols'];

/** Die vier Editoren. `WeatherMetricsTab.svelte` traegt zwei davon (Touren-
 *  Editor und Compare-Uebersicht) — dieselbe Datei, zwei Kontexte. */
const EDITOREN: { name: string; datei: string }[] = [
	{ name: 'Touren-Editor (context="route")', datei: 'WeatherMetricsTab.svelte' },
	{ name: 'Compare-Uebersicht (context="vergleich")', datei: 'WeatherMetricsTab.svelte' },
	{ name: 'Compare-Stundenverlauf', datei: 'CompareHourlyLayoutControls.svelte' },
	{ name: 'Compare-Ausblick', datei: 'CompareOutlookLayoutControls.svelte' }
];

function parseComponent(path: string): any {
	return parse(readFileSync(path, 'utf-8'), { modern: true });
}

function walk(node: unknown, visit: (n: Record<string, any>) => void): void {
	if (node === null || typeof node !== 'object') return;
	if (Array.isArray(node)) {
		node.forEach((n) => walk(n, visit));
		return;
	}
	const n = node as Record<string, any>;
	visit(n);
	for (const key of Object.keys(n)) {
		if (key === 'parent' || key === 'loc') continue;
		walk(n[key], visit);
	}
}

/** Welche der drei Formen liest dieser Teilbaum? `label`/`col_label` als
 *  Eigenschaft eines Objekts (`m.col_label`), die Kurzform zusaetzlich als
 *  eigener Bezeichner — sie reist seit #1719 S4 in einer eigenen Zuordnung
 *  (`kuerzelById[id]`, rechnender Zugriff) statt als Feld am Metrik-Objekt. */
function geleseneFormen(subtree: unknown): Set<string> {
	const gefunden = new Set<string>();
	walk(subtree, (n) => {
		if (n.type === 'MemberExpression' && !n.computed && n.property?.type === 'Identifier') {
			// `label`/`col_label` unveraendert streng: nur als Objekt-Eigenschaft.
			if ((FORMEN as readonly string[]).includes(n.property.name)) gefunden.add(n.property.name);
			if (KURZFORM_QUELLEN.includes(n.property.name)) gefunden.add('kurzform');
		}
		if (n.type === 'Identifier' && KURZFORM_QUELLEN.includes(n.name)) gefunden.add('kurzform');
	});
	return gefunden;
}

/** Direkt eingebundene Svelte-Komponenten (ein Schritt tief) + die Datei
 *  selbst. Mehr Tiefe braucht es nicht: eine Auflösung, die der Nutzer in
 *  diesem Reiter sieht, haengt entweder im Reiter selbst oder in einem
 *  Bauteil, das er unmittelbar einbindet. */
function anzeigeflaechen(datei: string): string[] {
	const pfad = join(SHARED, datei);
	const ast = parseComponent(pfad);
	const pfade = [pfad];
	for (const stmt of (ast?.instance?.content?.body as any[]) ?? []) {
		if (stmt.type !== 'ImportDeclaration') continue;
		const quelle = String(stmt.source?.value ?? '');
		if (!quelle.endsWith('.svelte')) continue;
		pfade.push(
			quelle.startsWith('$lib/')
				? join(LIB, quelle.slice('$lib/'.length))
				: resolve(dirname(pfad), quelle)
		);
	}
	return pfade;
}

// ═══════════════════════════════════════════════════════════════════════════
// AC-7, Teil 1 — die drei Formen sind sichtbar
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-7: jeder der vier Editoren zeigt alle drei Namensformen', () => {
	for (const { name, datei } of EDITOREN) {
		test(`${name}: eine Anzeigeflaeche rendert deutschen Namen, Kurzform UND SMS-Kuerzel`, () => {
			const treffer: { datei: string; formen: string[] }[] = [];
			for (const pfad of anzeigeflaechen(datei)) {
				let ast: any;
				try {
					ast = parseComponent(pfad);
				} catch {
					continue; // nicht auflösbarer Import: fuer diese Frage unerheblich
				}
				const formen = geleseneFormen(ast.fragment);
				if (formen.size > 0) treffer.push({ datei: pfad, formen: [...formen].sort() });
			}

			const vollstaendig = treffer.filter((t) => FORMEN.every((f) => t.formen.includes(f)));
			assert.ok(
				vollstaendig.length >= 1,
				`AC-7 FAIL (RED): ${name} — keine Anzeigeflaeche zeigt alle drei Namensformen ` +
					`(${FORMEN.join(', ')}). Gefunden wurde je Flaeche nur: ` +
					`${treffer.map((t) => `${t.datei.split('/').pop()}=[${t.formen.join(',')}]`).join(' ')}. ` +
					`Ein Kuerzel aus Mail oder SMS ist damit in diesem Reiter nicht aufloesbar.`
			);
		});
	}
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-7, Teil 2 — die Anzeige bekommt die Werte auch wirklich geliefert
//
// Ohne diesen zweiten Teil genuegte ein `{m.sms_code}` im Markup, das immer
// leer bliebe: die drei Compare-Editoren bauen ihre Metrik-Eintraege heute
// von Hand aus wenigen Feldern zusammen (WeatherMetricsTab.svelte:822-831,
// CompareHourlyLayoutControls.svelte:116-124,
// CompareOutlookLayoutControls.svelte:65-73) — dort fehlt die Datengrundlage,
// nicht nur die Anzeige.
// ═══════════════════════════════════════════════════════════════════════════

/** Objekt-Literale, die in eine Zuordnung geschrieben werden
 *  (`map[schluessel] = { … }`) — so bauen alle drei Compare-Editoren ihre
 *  Metrik-Eintraege. Ein `as MetricEntry` wird abgestreift. */
function eintragsLiterale(ast: any): any[] {
	const gefunden: any[] = [];
	walk(ast?.instance?.content?.body, (n) => {
		if (n.type !== 'AssignmentExpression') return;
		if (n.left?.type !== 'MemberExpression' || !n.left.computed) return;
		let rechts = n.right;
		while (rechts && (rechts.type === 'TSAsExpression' || rechts.type === 'TSSatisfiesExpression')) {
			rechts = rechts.expression;
		}
		if (rechts?.type === 'ObjectExpression') gefunden.push(rechts);
	});
	return gefunden;
}

describe('AC-7: die Metrik-Eintraege der Compare-Editoren fuehren alle drei Formen', () => {
	for (const datei of [
		'WeatherMetricsTab.svelte',
		'CompareHourlyLayoutControls.svelte',
		'CompareOutlookLayoutControls.svelte'
	]) {
		test(`${datei}: jedes gebaute Metrik-Objekt traegt Kurzform und SMS-Kuerzel`, () => {
			const ast = parseComponent(join(SHARED, datei));
			const literale = eintragsLiterale(ast);
			assert.ok(
				literale.length >= 1,
				`${datei}: kein von Hand gebautes Metrik-Objekt gefunden — der Test greift ` +
					`ins Leere und muesste an die neue Bauart angepasst werden.`
			);

			for (const objekt of literale) {
				const eigenschaften = new Set<string>();
				let hatSpread = false;
				for (const prop of objekt.properties ?? []) {
					if (prop.type === 'SpreadElement') hatSpread = true;
					else if (prop.key?.type === 'Identifier') eigenschaften.add(prop.key.name);
				}
				// Ein Spread reicht: dann wird der vollstaendige Katalog-Eintrag
				// durchgereicht und traegt alle Formen von selbst.
				if (hatSpread) continue;
				for (const form of ['col_label', 'sms_code']) {
					assert.ok(
						eigenschaften.has(form),
						`AC-7 FAIL (RED): ${datei} baut einen Metrik-Eintrag ohne '${form}' ` +
							`(vorhanden: ${[...eigenschaften].join(', ')}). Die Anzeige koennte die ` +
							`Form dann nur leer lassen — die Datengrundlage fehlt, nicht nur die Anzeige.`
					);
				}
			}
		});
	}
});
