// TDD RED — Issue #1256 Scheibe S8d: Mobile-Editor-Fidelity, Gruppen B+C+Invariante
//
// Spec: docs/specs/modules/feat_1256_s8d_mobile_editor_fidelity.md (AC-6..AC-20)
// Soll: screen-compare-editor-mobile.jsx (Handoff-4, mobiler Editor),
//       claude-code-handoff/current/jsx/screen-compare-editor.jsx Z.146-347
//       (Desktop-CTA-Füße Orte/Wertebereiche/Layout)
//
// Source-Wächter (Kern-Schicht): prüfen den Soll-Zustand des Markups/der
// Copy-Strings über readFileSync + Struktur-Anker (Textfenster-Proximity),
// analog compare_hub_fidelity.test.ts (S8c). Verhaltensnachweis aus
// Nutzersicht folgt in Phase 6 per Playwright gegen Staging
// (frontend/e2e/compare-editor-fidelity-s8d.spec.ts) — ROT-Beleg gegen
// Staging ist für noch-nicht-deployten Stand unmöglich (S4-Lehre).
//
// RED-Erwartung (vor Implementation): AC-6..AC-18 FAIL; AC-19/AC-20-Wächter
// GREEN (Regressionsschutz laut Spec-Test-Plan).
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs \
//     --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_editor_mobile_fidelity.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const COMPARE_DIR = join(dirname(fileURLToPath(import.meta.url)), '..');
const EDITOR_FILE = join(COMPARE_DIR, 'CompareEditor.svelte');
const STEP2_FILE = join(COMPARE_DIR, 'steps', 'Step2Orte.svelte');

const editor = () => readFileSync(EDITOR_FILE, 'utf-8');
const step2 = () => readFileSync(STEP2_FILE, 'utf-8');

// ── Struktur-Anker-Helfer: Desktop-/Mobil-Zweig isoliert betrachten, damit
//    Assertions nicht versehentlich die jeweils andere (bereits bestehende)
//    Zweig-Fassung derselben Copy treffen (z.B. "Orte hinzufügen →" existiert
//    heute schon einmal im Desktop-Vergleich-Tab-CTA). ──────────────────────
function desktopBlock(code: string): string {
	const start = code.indexOf('class="cm-desktop"');
	const end = code.indexOf('<!-- /.cm-desktop -->');
	return start === -1 || end === -1 ? '' : code.slice(start, end);
}
function mobileBlock(code: string): string {
	const start = code.indexOf('class="cm-mobile"');
	const end = code.indexOf('<!-- /.cm-mobile -->');
	return start === -1 || end === -1 ? '' : code.slice(start, end);
}

describe('AC-6/AC-7: Step2Orte dense-Prop (LayoutTab.svelte-Muster)', () => {
	test('Step2Orte kennt eine dense-Prop', () => {
		assert.match(
			step2(),
			/dense\??:\s*boolean/,
			'AC-6/AC-7 FAIL: Step2Orte.svelte hat keine dense-Prop (Muster: LayoutTab.svelte:22 dense?: boolean)'
		);
	});

	test('dense-Kopfzeile „Im Vergleich · N" mit kompaktem Badge „viel — Empf. 3–5"', () => {
		assert.ok(
			step2().includes('viel — Empf. 3–5'),
			'AC-6 FAIL: dense-Badge-Kurzform „viel — Empf. 3–5" fehlt (Soll: JSX-M Z.234; Ist nur die lange Desktop-Form „viel — Empfehlung 3–5")'
		);
	});

	test('dense-Badge exaktes „min. 2" ohne „erforderlich"-Suffix', () => {
		assert.match(
			step2(),
			/(['"`])min\. 2\1/,
			'AC-6 FAIL: dense-Badge-Kurzform „min. 2" (ohne "erforderlich") fehlt (Soll: JSX-M Z.234; Ist nur "min. 2 erforderlich")'
		);
	});

	test('dense „Ort aus Bibliothek wählen"-Button ohne Zähler-Suffix', () => {
		assert.match(
			step2(),
			/Ort aus Bibliothek wählen(?!\s*\()/,
			'AC-6 FAIL: dense-Bibliotheks-Button „Ort aus Bibliothek wählen" (ohne "(N)"-Suffix) fehlt in Step2Orte.svelte (Soll: JSX-M Z.265; Ist nur als Duplikat mit Zähler in CompareEditor.svelte:1245)'
		);
	});

	test('Smart-Import-Panel ist hinter einem !dense-Gate versteckt', () => {
		const code = step2();
		const gateIdx = code.search(/!dense\b/);
		assert.notEqual(
			gateIdx,
			-1,
			'AC-7 FAIL: kein !dense-Gate in Step2Orte.svelte gefunden — Smart-Import/Inline-Bibliothek werden nicht dense-bedingt ausgeblendet'
		);
		const smartImportIdx = code.indexOf('compare-step2-smart-import-input');
		assert.ok(
			smartImportIdx > gateIdx,
			'AC-7 FAIL: Smart-Import-Input (compare-step2-smart-import-input) liegt nicht hinter einem !dense-Gate (Ist: Step2Orte.svelte:196-274 wird auch mobil ungegated mitgerendert)'
		);
	});

	test('Inline-Bibliothek ist hinter einem !dense-Gate versteckt', () => {
		const code = step2();
		const gateIdx = code.search(/!dense\b/);
		const libraryIdx = code.indexOf('data-testid="compare-step2-library"');
		assert.ok(
			gateIdx !== -1 && libraryIdx > gateIdx,
			'AC-7 FAIL: Inline-Bibliothek (compare-step2-library) liegt nicht hinter einem !dense-Gate (Ist: Step2Orte.svelte:319-356 wird auch mobil ungegated mitgerendert)'
		);
	});
});

describe('AC-8: Vergleich-Tab mobile Floating-CTA kontextuell (JSX-M Z.200-207)', () => {
	test('„Orte hinzufügen →" und „Name eingeben" im mobilen Zweig vorhanden', () => {
		const mob = mobileBlock(editor());
		assert.ok(
			mob.includes('Orte hinzufügen →'),
			'AC-8 FAIL: mobile CTA zeigt auf dem Vergleich-Tab kein „Orte hinzufügen →" (Ist: generisches „Weiter →" für alle Tabs, CompareEditor.svelte:1274)'
		);
		assert.ok(
			mob.includes('Name eingeben'),
			'AC-8 FAIL: mobile CTA zeigt bei leerem Namen kein „Name eingeben"-Disabled-Label (Ist: generisches „Weiter →" ohne Kontext-Label)'
		);
	});
});

describe('AC-9: Orte-Tab mobile Floating-CTA kontextuell (JSX-M Z.269-277)', () => {
	test('„Idealwerte festlegen →" und „noch N Ort… nötig"-Template im mobilen Zweig vorhanden', () => {
		const mob = mobileBlock(editor());
		assert.ok(
			mob.includes('Idealwerte festlegen →'),
			'AC-9 FAIL: mobile CTA zeigt auf dem Orte-Tab kein „Idealwerte festlegen →" (Ist: generisches „Weiter →")'
		);
		assert.match(
			mob,
			/noch[\s\S]{0,60}nötig/,
			'AC-9 FAIL: mobile CTA zeigt kein „noch N Ort(e) nötig"-Disabled-Label bei <2 Orten (Soll: JSX-M Z.275)'
		);
	});
});

describe('AC-10: Wertebereiche-Tab mobile Floating-CTA (JSX-M Z.323-327)', () => {
	test('„Layout einrichten →" im mobilen Zweig vorhanden', () => {
		assert.ok(
			mobileBlock(editor()).includes('Layout einrichten →'),
			'AC-10 FAIL: mobile CTA zeigt auf dem Wertebereiche-Tab kein „Layout einrichten →" (Ist: generisches „Weiter →")'
		);
	});
});

describe('AC-11: Layout-Tab mobile Floating-CTA (JSX-M Z.337-341)', () => {
	test('„Versand einrichten →" im mobilen Zweig vorhanden', () => {
		assert.ok(
			mobileBlock(editor()).includes('Versand einrichten →'),
			'AC-11 FAIL: mobile CTA zeigt auf dem Layout-Tab kein „Versand einrichten →" (Ist: generisches „Weiter →"; „Versand einrichten zum Aktivieren" ohne Pfeil existiert an anderer Stelle, zählt nicht)'
		);
	});
});

describe('AC-12: Versand-Tab hat KEINEN Boden-Floating-CTA (PO-Entscheid 2026-07-15)', () => {
	test('cm-mobile-cta ist auf dem Versand-Tab explizit ausgeschlossen', () => {
		const mob = mobileBlock(editor());
		const ctaIdx = mob.indexOf('data-testid="cm-mobile-cta"');
		assert.notEqual(ctaIdx, -1, 'AC-12 FAIL: cm-mobile-cta-Block wurde komplett entfernt statt Tab-bedingt ausgeschlossen');
		const before = mob.slice(Math.max(0, ctaIdx - 200), ctaIdx);
		assert.match(
			before,
			/activeTab\s*!==\s*['"]versand['"]/,
			'AC-12 FAIL: kein erkennbarer Versand-Tab-Ausschluss vor der cm-mobile-cta-Bedingung (Ist: nur {#if !isEdit}, CompareEditor.svelte:1270, ohne Tab-Filter)'
		);
	});
});

describe('AC-13: Profil-Häkchen mobil (JSX-M Z.190-194)', () => {
	function mobileProfileSection(code: string): string {
		const mob = mobileBlock(code);
		const start = mob.indexOf('Aktivitätsprofil');
		const end = mob.indexOf("{:else if activeTab === 'orte'}", start);
		return start === -1 ? '' : mob.slice(start, end === -1 ? undefined : end);
	}

	test('Auswahl-Häkchen-SVG (Pfad M2 6l3 3 5-6) in der mobilen Profil-Kartenliste', () => {
		const section = mobileProfileSection(editor());
		assert.ok(
			section.includes('M2 6l3 3 5-6'),
			'AC-13 FAIL: kein Auswahl-Häkchen-SVG in der mobilen Profil-Kartenliste (Soll: JSX-M Z.190-194; Ist: CompareEditor.svelte:1219-1233 ohne Häkchen)'
		);
	});
});

describe('AC-14: Metrik-Unterzeile mobil gekürzt (JSX-M Z.186-188)', () => {
	function mobileProfileSection(code: string): string {
		const mob = mobileBlock(code);
		const start = mob.indexOf('Aktivitätsprofil');
		const end = mob.indexOf("{:else if activeTab === 'orte'}", start);
		return start === -1 ? '' : mob.slice(start, end === -1 ? undefined : end);
	}

	test('slice(0, 4)-Kürzung in der mobilen Metrik-Unterzeile', () => {
		const section = mobileProfileSection(editor());
		assert.match(
			section,
			/\.slice\(0,\s*4\)/,
			'AC-14 FAIL: keine 4-Einträge-Kürzung (slice(0, 4)) in der mobilen Metrik-Unterzeile (Soll: JSX-M Z.187; Ist: profileMetricsLabel() ungekürzt, CompareEditor.svelte:1228)'
		);
	});
});

describe('AC-15: genau EINE App-Leiste im mobilen Editor (JSX-M Z.419-448)', () => {
	test('nachgebaute cm-mobile-appbar entfällt', () => {
		assert.ok(
			!editor().includes('data-testid="cm-mobile-appbar"'),
			'AC-15 FAIL: nachgebaute Editor-Kopfzeile (cm-mobile-appbar) existiert noch — soll durch die Befüllung der globalen Design-Kopfleiste ersetzt werden (CompareEditor.svelte:1122-1156)'
		);
	});

	test('cm-mobile-save/cm-mobile-activate entfallen (Pendants an der Design-Kopfleiste)', () => {
		const code = editor();
		assert.ok(
			!code.includes('data-testid="cm-mobile-save"'),
			'AC-15 FAIL: cm-mobile-save testid existiert noch (soll durch TopAppBar-Pendant ersetzt werden, s. AC-20)'
		);
		assert.ok(
			!code.includes('data-testid="cm-mobile-activate"'),
			'AC-15 FAIL: cm-mobile-activate testid existiert noch (soll durch TopAppBar-Pendant ersetzt werden, s. AC-20)'
		);
	});

	test('rechter App-Bar-Button zeigt bedingt „…" vor Bereitschaft / „Aktivieren" danach', () => {
		assert.match(
			editor(),
			/\?\s*['"]Aktivieren['"]\s*:\s*['"]…['"]/,
			'AC-15 FAIL: keine bedingte "Aktivieren"/"…"-Ternary für den rechten App-Bar-Button gefunden (Soll: JSX-M Z.444; Ist: immer „Aktivieren", nur farblich ausgegraut, CompareEditor.svelte:1149-1154)'
		);
	});
});

describe('AC-16: Desktop-Orte-Tab-Fuß (JSX Z.298-307)', () => {
	test('⊘-Hinweis + „Idealwerte festlegen →"-Button im Desktop-Zweig', () => {
		const desk = desktopBlock(editor());
		assert.ok(
			desk.includes('⊘ min. 2 Orte auswählen'),
			'AC-16 FAIL: Hinweis „⊘ min. 2 Orte auswählen" fehlt im Desktop-Orte-Tab-Fuß (Soll: JSX Z.300; Ist: kein Tab-Fuß, CompareEditor.svelte:1074-1075)'
		);
		assert.ok(
			desk.includes('Idealwerte festlegen →'),
			'AC-16 FAIL: Button „Idealwerte festlegen →" fehlt im Desktop-Orte-Tab-Fuß (Soll: JSX Z.304)'
		);
	});
});

describe('AC-17: Desktop-Wertebereiche-Tab-Fuß (JSX Z.322-328)', () => {
	test('„Layout einrichten →"-Button im Desktop-Zweig', () => {
		assert.ok(
			desktopBlock(editor()).includes('Layout einrichten →'),
			'AC-17 FAIL: Button „Layout einrichten →" fehlt im Desktop-Wertebereiche-Tab-Fuß (Soll: JSX Z.325; Ist: kein Tab-Fuß, CompareEditor.svelte:1076-1084)'
		);
	});
});

describe('AC-18: Desktop-Layout-Tab-Fuß (JSX Z.338-344)', () => {
	test('„Versand einrichten →"-Button im Desktop-Zweig', () => {
		assert.ok(
			desktopBlock(editor()).includes('Versand einrichten →'),
			'AC-18 FAIL: Button „Versand einrichten →" fehlt im Desktop-Layout-Tab-Fuß (Soll: JSX Z.341; Ist: kein Tab-Fuß, CompareEditor.svelte:1085-1086)'
		);
	});
});

describe('AC-19: Desktop-CTA-Füße nur im Create-Modus (Regressionsschutz — GREEN von Anfang an)', () => {
	test('neue Tab-Füße sind {#if !isEdit}-gegated (oder noch nicht implementiert)', () => {
		const desk = desktopBlock(editor());
		const labels = ['⊘ min. 2 Orte auswählen', 'Idealwerte festlegen →', 'Layout einrichten →', 'Versand einrichten →'];
		for (const label of labels) {
			const idx = desk.indexOf(label);
			// Vor Implementation (RED) existieren die Labels noch nicht — das ist
			// laut Spec-Test-Plan der erwartete, vacuously-grüne Ausgangszustand
			// für AC-19 (Regressionsschutz, kein Bugfix-Nachweis nötig).
			if (idx === -1) continue;
			const before = desk.slice(Math.max(0, idx - 400), idx);
			assert.match(
				before,
				/\{#if\s+!isEdit\}/,
				`AC-19 FAIL: "${label}" liegt nicht innerhalb eines {#if !isEdit}-Blocks — würde damit auch im Edit-Modus erscheinen (Verstoß gegen das bestehende Muster, CompareEditor.svelte:1059)`
			);
		}
	});
});

describe('AC-20: Sharing-Invariante (Wächter — GREEN von Anfang an)', () => {
	test('cm-mobile-cta-testid bleibt erhalten', () => {
		assert.match(
			editor(),
			/data-testid="cm-mobile-cta"/,
			'AC-20 FAIL: testid cm-mobile-cta ist aus CompareEditor.svelte verschwunden'
		);
	});

	test('compare-step2-mobile-library-btn-testid bleibt erhalten (in CompareEditor oder Step2Orte)', () => {
		const combined = editor() + step2();
		assert.match(
			combined,
			/data-testid="compare-step2-mobile-library-btn"/,
			'AC-20 FAIL: testid compare-step2-mobile-library-btn ist verschwunden'
		);
	});

	test('cm-mobile-tab-{id}-Pattern bleibt erhalten', () => {
		assert.match(
			editor(),
			/data-testid="cm-mobile-tab-\{t\.id\}"/,
			'AC-20 FAIL: das cm-mobile-tab-{id}-Testid-Pattern ist aus CompareEditor.svelte verschwunden'
		);
	});

	test('geteilte Organismen bleiben referenziert (Proxy für 0-Zeilen-Diff)', () => {
		const code = editor();
		for (const organism of ['CorridorEditor', 'CorridorEditorMobile', 'LayoutTab', 'VersandTab']) {
			assert.ok(
				new RegExp(`\\b${organism}\\b`).test(code),
				`AC-20 FAIL: geteilter Organism ${organism} wird nicht mehr referenziert — die neuen CTA-Füße dürfen nur als Wrapper UM die Organismen liegen, nicht in ihnen (C0-Invariante)`
			);
		}
	});
});
