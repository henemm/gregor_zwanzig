// Issue #2794 S3a, Teil-PR 2 (Fix-Loop, Adversary-Findings F015 + F017 — Schluss mit Einzelfunden).
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md — AC-6 (Anlege-Kette: kein Schritt fuehrt
// auf einen falschen Reiter; Trip route → etappen → wegpunkte → wetter → zustellung, Vergleich
// vergleich → orte → wetter → zustellung).
//
// EIN umfassender Waechter statt Knopf-fuer-Knopf: In TripNewEditor.svelte UND CompareNewEditor.svelte
// wird JEDER Schritt-Zweig gesucht — `{#if|:else if activeTab === '<schritt>'}` (Desktop-Inhalt,
// Handy-Inhalt, Sticky-Fuss) und die dauerhaft gemounteten Behaelter
// `style:display={activeTab === '<schritt>' ? '' : 'none'}` — und darin JEDER Knopf (Element oder
// Komponente) mit `onclick`. Jeder onclick-Ausdruck wird zur LAUFZEIT gegen das ECHTE Instanz-Skript
// des Editors ausgefuehrt (svelteInstanzPruefstand), mit `activeTab = <schritt>` als Ausgangslage;
// das gemessene Ergebnis (neuer Reiter / bleibt / Abschluss) muss der unten AUSGESCHRIEBENEN
// Soll-Tabelle entsprechen — Knopf fuer Knopf, in Quelltext-Reihenfolge.
//
// Rot wird der Test, wenn
//   - ein Knopf ein anderes Ziel hat als in der Soll-Tabelle (z. B. „Wetter direkt" → 'zustellung', F017),
//   - ein Zweig oder ein Knopf hinzukommt oder wegfaellt (Anzahl je Zweig und Zweig-Liste festgeschrieben),
//   - ein Knopf sich nicht ausfuehren laesst und dabei einen Reiterwechsler nennt (switchTab,
//     make*ContinueHandler, handleMobileNext …) — ungemessene Navigation gibt es nicht.
//
// Zurueck-Knoepfe gibt es in den Schritt-Zweigen beider Editoren derzeit nicht; kaemen welche dazu,
// faellt der Test ueber die Knopf-Zaehlung rot und die Soll-Tabelle muss sie (Ziel = Vorgaenger) aufnehmen.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/s3a2794_anlege_weiter_ziele.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseExpressionAt } from 'acorn';

import { attribut, type Knoten } from './s3a2794Ast.ts';
import { umgebungFuer, werte } from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const KOMP = join(HIER, '..', '..');
register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const TRIP_NEU = join(KOMP, 'trip-new', 'TripNewEditor.svelte');
const VERGLEICH_NEU = join(KOMP, 'compare-new', 'CompareNewEditor.svelte');

/** Ergebnis eines Klicks: Ziel-Reiter, 'bleibt' (kein Reiterwechsel), 'abschluss' (Speichern/Aktivieren,
 *  nicht ausgefuehrt — Netzweg), 'ohne-navigation' (im Schleifenkontext, nicht ausfuehrbar, nennt
 *  nachweislich keinen Reiterwechsler). */
type Ergebnis = string;

// ─────────────────────────── SOLL-TABELLEN (AC-6) ───────────────────────────
// Schluessel: `<schritt>#<n>` — n zaehlt die Zweige desselben Schritts in Quelltext-Reihenfolge.
// Wert: Ergebnis je onclick-Knopf in Quelltext-Reihenfolge.

const SOLL_TRIP: Record<string, Ergebnis[]> = {
	// ── Desktop ──
	'route#0': ['etappen'], // „Weiter zu Etappen"
	'etappen#0': [
		'ohne-navigation', // GPX entfernen (je Etappe)
		'ohne-navigation', // Etappe entfernen (je Etappe)
		'bleibt', // Etappe hinzufuegen
		'wetter', // „Wetter direkt" (F017)
		'wegpunkte' // „Wegpunkte pruefen"
	],
	'wegpunkte#0': ['wetter', 'wetter', 'wetter', 'wetter'], // Banner + Fuss: Ueberspringen / Uebernehmen (F015)
	'wetter|zustellung#0': [], // geteilte Wetter-/Versand-Instanz
	'zustellung#0': [], // Mail-Inhalt (Desktop)
	'wetter#0': ['zustellung'], // „Zustellung einrichten"
	'zustellung#1': [], // Alarme (Desktop)
	// ── Handy-Inhalt ──
	'route#1': [],
	'etappen#1': [
		'ohne-navigation', // Etappen-Sheet oeffnen
		'ohne-navigation', // Etappe entfernen
		'ohne-navigation', // GPX entfernen
		'bleibt', // Etappe hinzufuegen
		'bleibt' // Sheet: Uebernehmen
	],
	'wegpunkte#1': [],
	'wetter|zustellung#1': [],
	'zustellung#2': [], // Mail-Inhalt (Handy)
	'wetter#1': [], // Korridore (Handy)
	'zustellung#3': [], // Alarme (Handy)
	// ── Handy Sticky-Fuss ──
	'zustellung#4': ['abschluss'], // Trip speichern
	'route#2': ['etappen'],
	'etappen#2': ['wegpunkte', 'wetter'], // „Wegpunkte pruefen", „Wetter direkt" (F017, :1205)
	'wegpunkte#2': ['wetter', 'wetter'], // Uebernehmen / Ueberspringen
	'wetter#2': ['zustellung']
};

const SOLL_VERGLEICH: Record<string, Ergebnis[]> = {
	// ── Desktop ──
	'vergleich#0': ['ohne-navigation', 'orte'], // Profil waehlen (je Profil), „Orte hinzufuegen"
	'orte#0': ['wetter'], // „Wetter-Metriken"
	'wetter#0': ['zustellung'], // „Zustellung einrichten"
	'zustellung#0': [],
	// ── Handy-Inhalt ──
	'vergleich#1': ['ohne-navigation'], // Profil waehlen
	'orte#1': [],
	'wetter#1': [],
	'zustellung#1': [],
	// ── Handy Sticky-Fuss ──
	'zustellung#2': ['abschluss'], // Briefing aktivieren
	'vergleich#2': ['orte'],
	'orte#2': ['wetter'],
	'wetter#2': ['zustellung']
};

/** Speichern/Aktivieren: Netzweg, wird nicht ausgefuehrt — nur genau diese Ausdruecke gelten als Abschluss. */
const ABSCHLUSS = new Set(['onSave', 'handleActivate']);
/** Bezeichner, die den Reiter wechseln (bzw. Handler dafuer bauen). */
const WECHSLER = /^(switchTab|handleMobileNext|make\w*(Continue|Tab|Jump)\w*Handler)$/;

// ─────────────────────────── Messaufbau ───────────────────────────

const IF_WEICHE = /^activeTab\s*===\s*['"](\w+)['"]$/;
const DISPLAY_WEICHE = /^((?:activeTab\s*===\s*['"]\w+['"]\s*(?:\|\|\s*)?)+)\?\s*['"]{2}\s*:\s*['"]none['"]$/;

function kinder(k: Knoten, f: (n: Knoten) => void): void {
	for (const [feld, v] of Object.entries(k)) {
		if (feld === 'parent' || feld === 'loc' || feld === 'metadata') continue;
		if (Array.isArray(v)) v.forEach((x) => x && typeof x === 'object' && f(x));
		else if (v && typeof v === 'object') f(v as Knoten);
	}
}

type Knopf = { wo: string; onclick: string };
type Zweig = { schluessel: string; schritt: string; knoepfe: Knopf[] };

function knoepfeIn(teil: Knoten | Knoten[], quelle: string, out: Knopf[]): void {
	(function lauf(n: Knoten): void {
		if ((n.type === 'Component' || n.type === 'RegularElement') && Array.isArray(n.attributes)) {
			const oc = attribut(n, quelle, 'onclick');
			if (oc) {
				// Ein onclick ohne auswertbaren Ausdruck waere eine ungemessene Stelle — laut scheitern.
				assert.ok(oc.ausdruck, `Messaufbau: onclick ohne Ausdruck an ${n.name}@${n.start}`);
				out.push({ wo: `${n.name}@${n.start}`, onclick: oc.ausdruck! });
			}
		}
		kinder(n, lauf);
	})(Array.isArray(teil) ? ({ type: 'Liste', teile: teil } as Knoten) : teil);
}

function displaySchritte(e: Knoten, quelle: string): string[] | null {
	for (const a of (e.attributes ?? []) as Knoten[]) {
		if (a.type !== 'StyleDirective' || a.name !== 'display') continue;
		const v = Array.isArray(a.value) ? a.value[0] : a.value;
		if (v?.type !== 'ExpressionTag') return null;
		const text = quelle.slice(v.expression.start, v.expression.end).trim();
		const m = DISPLAY_WEICHE.exec(text);
		if (!m) return null;
		return [...m[1].matchAll(/['"](\w+)['"]/g)].map((x) => x[1]);
	}
	return null;
}

/** Alle Schritt-Zweige in Quelltext-Reihenfolge, je mit ihren onclick-Knoepfen. */
function schrittZweige(ast: Knoten, quelle: string): Zweig[] {
	const roh: Array<{ start: number; schritt: string; knoepfe: Knopf[] }> = [];
	(function lauf(n: Knoten): void {
		if (n.type === 'IfBlock' && n.test) {
			const m = IF_WEICHE.exec(quelle.slice(n.test.start, n.test.end).trim());
			if (m) {
				const knoepfe: Knopf[] = [];
				knoepfeIn(n.consequent, quelle, knoepfe);
				roh.push({ start: n.start, schritt: m[1], knoepfe });
			}
		}
		if (n.type === 'RegularElement') {
			const schritte = displaySchritte(n, quelle);
			if (schritte) {
				const knoepfe: Knopf[] = [];
				knoepfeIn(n.fragment, quelle, knoepfe);
				roh.push({ start: n.start, schritt: schritte.join('|'), knoepfe });
			}
		}
		kinder(n, lauf);
	})(ast.fragment);
	roh.sort((a, b) => a.start - b.start);
	const zaehler: Record<string, number> = {};
	return roh.map((z) => {
		const n = zaehler[z.schritt] ?? 0;
		zaehler[z.schritt] = n + 1;
		return { schluessel: `${z.schritt}#${n}`, schritt: z.schritt, knoepfe: z.knoepfe };
	});
}

/** Nennt der onclick-Ausdruck (AST, kein Textmuster) einen Reiterwechsler? */
function nenntWechsler(ausdruck: string): string | null {
	const ast = parseExpressionAt(ausdruck, 0, { ecmaVersion: 'latest' }) as unknown as Knoten;
	let treffer: string | null = null;
	(function lauf(n: unknown): void {
		if (treffer || n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach(lauf);
		const k = n as Knoten;
		if (k.type === 'Identifier' && WECHSLER.test(String(k.name))) treffer = String(k.name);
		for (const key of Object.keys(k)) if (key !== 'loc') lauf(k[key]);
	})(ast);
	return treffer;
}

/** Fuehrt einen Klick aus und misst das Ergebnis. `vorbereiten` setzt die Ausgangslage. */
function klickErgebnis(u: Knoten, schritt: string, knopf: Knopf, vorbereiten: () => void): Ergebnis {
	if (ABSCHLUSS.has(knopf.onclick.trim())) return 'abschluss';
	vorbereiten();
	u.activeTab = schritt;
	try {
		const handler = werte(knopf.onclick, u);
		assert.equal(typeof handler, 'function', `${knopf.wo} (${knopf.onclick}) liefert keinen Handler`);
		(handler as () => unknown)();
	} catch (e) {
		if (e instanceof assert.AssertionError) throw e;
		// Nur Knoepfe im Schleifenkontext (je Etappe/Profil) duerfen hier scheitern — und nur, wenn sie
		// keinen Reiterwechsler nennen. Sonst ist das eine ungemessene Navigation.
		const w = nenntWechsler(knopf.onclick);
		assert.equal(w, null, `${knopf.wo} (${knopf.onclick}) nennt '${w}', laesst sich aber nicht ausfuehren: ${(e as Error).message}`);
		return 'ohne-navigation';
	}
	return u.activeTab === schritt ? 'bleibt' : String(u.activeTab);
}

function pruefe(
	editor: string,
	zweige: Zweig[],
	soll: Record<string, Ergebnis[]>,
	u: Knoten,
	vorbereiten: () => void
): void {
	assert.deepEqual(
		zweige.map((z) => z.schluessel),
		Object.keys(soll),
		`${editor}: Schritt-Zweige weichen von der Soll-Tabelle ab (neuer/entfallener Zweig?)`
	);
	for (const z of zweige) {
		const s = soll[z.schluessel];
		assert.equal(
			z.knoepfe.length,
			s.length,
			`${editor} ${z.schluessel}: ${z.knoepfe.length} onclick-Knoepfe gefunden, Soll-Tabelle kennt ${s.length} (${z.knoepfe.map((k) => `${k.wo}: ${k.onclick}`).join(' | ')})`
		);
		z.knoepfe.forEach((k, i) => {
			const schritt = z.schritt.split('|')[0];
			const ist = klickErgebnis(u, schritt, k, vorbereiten);
			assert.equal(ist, s[i], `${editor} ${z.schluessel} Knopf ${i + 1} ${k.wo} (${k.onclick}): Ergebnis '${ist}', Soll '${s[i]}'`);
		});
	}
}

describe('AC-6 (F015/F017): jeder Knopf in jedem Schritt-Zweig der Anlege-Editoren fuehrt auf den Reiter laut Kette', () => {
	test('s3a2794_trip_anlegen_alle_weiter_ziele_laut_soll_tabelle', async () => {
		const { u, ast, quelle } = await umgebungFuer(
			TRIP_NEU,
			{
				untrack: (f: () => unknown) => f(),
				stateOverride: { activeTab: 'route', name: 'GR20', startDate: '2026-07-01' }
			},
			{ jsAlsTs: true }
		);
		assert.equal(typeof u.switchTab, 'function', 'Messaufbau: switchTab nicht im Instanz-Skript ausgewertet');
		pruefe('Trip', schrittZweige(ast, quelle), SOLL_TRIP, u, () => {
			u.editorStages = [];
			u.stages = [];
			u.name = 'GR20';
			u.startDate = '2026-07-01';
			u.mobileSheetStageId = null;
		});
	});

	test('s3a2794_vergleich_anlegen_alle_weiter_ziele_laut_soll_tabelle', async () => {
		const { u, ast, quelle } = await umgebungFuer(
			VERGLEICH_NEU,
			{
				untrack: (f: () => unknown) => f(),
				stateOverride: { activeTab: 'vergleich', name: 'Alpen', pickedIds: ['a', 'b'], metrikenVisited: true, zustellungVisited: true }
			},
			{ jsAlsTs: true }
		);
		assert.equal(typeof u.switchTab, 'function', 'Messaufbau: switchTab nicht im Instanz-Skript ausgewertet');
		assert.ok(Array.isArray(u.TAB_DEFS) && u.TAB_DEFS.length === 4, 'Messaufbau: TAB_DEFS (Kette) nicht ausgewertet');
		// Freischaltung ist nicht Gegenstand dieses Tests (eigene Tests) — alle Schritte offen, damit das ZIEL messbar ist.
		pruefe('Vergleich', schrittZweige(ast, quelle), SOLL_VERGLEICH, u, () => {
			u.unlocked = new Set(['vergleich', 'orte', 'wetter', 'zustellung']);
			u.canContinue = true;
			u.orteContinueReady = true;
		});
	});
});
