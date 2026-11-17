// Abnahme-Aufnahmen — Issue #2795 S3b, Teilschritt 1b (Neubau Reiter „Zustellung“), AC-38.
// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md
// Soll: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html (per file://, nur Deutsch).
//
// Erzeugt in docs/artifacts/feature-2795-s3b1b-bilder/ (oder $BILD_DIR):
//   - mockup-<ctx>-<geraet>.png und staging-<ctx>-<geraet>.png für ctx trip|orte × desktop 1280×900 |
//     mobil 390×844, Sprache DE (8 Bilder),
//   - texte-<ctx>-<lang>.json (Desktop, de und en): {abschnitt: [sichtbare Texte in DOM-Reihenfolge]}
//     je `[data-abschnitt]` im Reiter, dazu `_hubkopf` (Hub-Kopf) und `_rest` (Reiter-Panel außerhalb
//     jedes Abschnitts).
// Vor jeder Aufnahme werden alle `<details>` im Reiter geöffnet — auf Staging („Anpassen“) wie im Mockup
// („Anpassen“ unter den stillen Stunden), damit Soll und Ist denselben aufgeklappten Zustand zeigen.
// Das Mockup bleibt im Zustand „normal“ mit „neu markiert“ (V-Marken sichtbar, Mockup-Standard); der
// Mockup-Rahmen (.frame) und das Rückmeldeformular (.fb) werden ausgeblendet.
//
// Nur in /e2e-verify gegen Staging, nie gegen Produktion, nicht in der CI-Positivliste.
//   cd frontend && npx playwright test --config playwright.2795-s3b1b-bilder.staging.config.ts
import { test, expect, type Page } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ganzseite } from './ganzseitenaufnahme';
import { HUB_KINDS, HUB_SEL, type HubKind } from './helpers';
import { DESKTOP, MARKER, MOBIL, oeffneZustellung, seedZustellung } from './s3b2795-zustellung.helpers';

const HIER = path.dirname(fileURLToPath(import.meta.url));
const MOCKUP = 'file://' + path.resolve(HIER, '..', '..', 'docs', 'context', 'einstellungen_neu', 'seiten', 'mockup-hub-fassung4.html');
const ARTEFAKTE = path.resolve(HIER, '..', '..', 'docs', 'artifacts', 'feature-2795-s3b1b-bilder');

type Lang = 'de' | 'en';
const KTX: Record<HubKind, 'trip' | 'orte'> = { route: 'trip', vergleich: 'orte' };
const GERAETE = [
	['desktop', DESKTOP],
	['mobil', MOBIL]
] as const;
const HUBKOPF = '[data-seite="hub"][data-abschnitt="kopf"]';

test.describe.configure({ mode: 'serial' });

function bildOrdner(): string {
	const d = process.env.BILD_DIR ?? ARTEFAKTE;
	mkdirSync(d, { recursive: true });
	return d;
}

async function sprache(page: Page, lang: Lang): Promise<void> {
	const res = await page.request.put('/api/auth/profile', { data: { language: lang } });
	expect(res.ok(), `Sprache ${lang}: HTTP ${res.status()}`).toBeTruthy();
}

const panelSel = (kind: HubKind): string => `[data-testid="${HUB_SEL[kind].panel}-zustellung"]`;

/** Im Browser: alle `details` unter jedem Treffer des Selektors öffnen. */
function oeffneDetails(selektor: string): void {
	for (const w of Array.from(document.querySelectorAll(selektor))) w.querySelectorAll('details').forEach((d) => ((d as HTMLDetailsElement).open = true));
}

/**
 * Im Browser: sichtbare Texte je Abschnitt. Textregeln wie `sichtbareTexte` in
 * elementliste-abgleich.staging.spec.ts (eigene Textknoten sichtbarer Elemente, aria-label von Knöpfen
 * und role=switch/group/textbox, bei Eingaben aria-label/placeholder/Wert). Zuordnung: nächster
 * `[data-abschnitt]`-Vorfahr innerhalb des Panels, sonst `_rest`; der Hub-Kopf landet unter `_hubkopf`.
 */
function texteJeAbschnitt(arg: { panel: string; kopf: string }): Record<string, string[]> {
	const MIT_LABEL = new Set(['switch', 'group', 'textbox']);
	const n = (s: string | null) => String(s ?? '').replace(/\s+/g, ' ').trim();
	const texteVon = (el: Element): string[] => {
		if (el.closest('script,style,[aria-hidden="true"]') || !el.checkVisibility()) return [];
		if (el instanceof HTMLInputElement) {
			const t = n(el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.value);
			return t ? [t] : [];
		}
		const aus: string[] = [];
		const label = el.getAttribute('aria-label');
		if (label && (el.tagName === 'BUTTON' || MIT_LABEL.has(el.getAttribute('role') ?? ''))) aus.push(n(label));
		let eigen = '';
		for (const k of Array.from(el.childNodes)) if (k.nodeType === 3) eigen += k.nodeValue;
		if (n(eigen)) aus.push(n(eigen));
		return aus;
	};
	const ergebnis: Record<string, string[]> = { _hubkopf: [], _rest: [] };
	for (const kopf of Array.from(document.querySelectorAll(arg.kopf))) {
		for (const el of [kopf, ...Array.from(kopf.querySelectorAll('*'))]) ergebnis._hubkopf.push(...texteVon(el));
	}
	for (const panel of Array.from(document.querySelectorAll(arg.panel))) {
		if (!panel.checkVisibility()) continue;
		for (const el of [panel, ...Array.from(panel.querySelectorAll('*'))]) {
			const t = texteVon(el);
			if (t.length === 0) continue;
			const ab = el.closest('[data-abschnitt]');
			const schluessel = ab && panel.contains(ab) && ab !== panel ? (ab.getAttribute('data-abschnitt') ?? '_rest') : '_rest';
			(ergebnis[schluessel] ??= []).push(...t);
		}
	}
	return ergebnis;
}

test.afterAll(async ({ request }) => {
	await request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
});

test('#2795 AC-38: Aufnahmen Mockup (Soll) — Reiter Zustellung, Trip/Orte × 1280/390', async ({ browser }) => {
	const ordner = bildOrdner();
	for (const [geraet, vp] of GERAETE) {
		const m = await browser.newPage({ viewport: vp });
		try {
			await m.goto(MOCKUP);
			for (const ctx of ['trip', 'orte'] as const) {
				await m.locator(`[data-ctx="${ctx}"]`).click();
				await m.locator('#tabs [data-tab="zustellung"]').click();
				await expect(m.locator('#tabs [data-tab="zustellung"]')).toHaveAttribute('aria-current', 'page');
				await m.evaluate(oeffneDetails, '#content');
				const stil = await m.addStyleTag({ content: '.frame,.fb{display:none!important}' });
				const masse = await ganzseite(m, path.join(ordner, `mockup-${ctx}-${geraet}.png`));
				expect(masse.breite).toBe(vp.width);
				await stil.evaluate((s) => s.remove());
			}
		} finally {
			await m.close();
		}
	}
});

test('#2795 AC-38: Aufnahmen Staging (Ist) — Reiter Zustellung, Trip/Orte × 1280/390, DE', async ({ page }) => {
	const ordner = bildOrdner();
	await sprache(page, 'de');
	for (const [geraet, vp] of GERAETE) {
		await page.setViewportSize(vp);
		for (const kind of HUB_KINDS) {
			const hub = await seedZustellung(page.request, kind);
			try {
				await oeffneZustellung(page, kind, hub.id);
				await page.evaluate(oeffneDetails, panelSel(kind));
				await page.waitForTimeout(200);
				const masse = await ganzseite(page, path.join(ordner, `staging-${KTX[kind]}-${geraet}.png`));
				expect(masse.breite).toBe(vp.width);
			} finally {
				await hub.aufraeumen();
			}
		}
	}
});

test('#2795 AC-38: sichtbare Texte je Abschnitt — Trip/Orte × DE/EN, Desktop', async ({ page }) => {
	const ordner = bildOrdner();
	await page.setViewportSize(DESKTOP);
	for (const lang of ['de', 'en'] as const) {
		await sprache(page, lang);
		for (const kind of HUB_KINDS) {
			const hub = await seedZustellung(page.request, kind);
			try {
				await oeffneZustellung(page, kind, hub.id);
				await page.evaluate(oeffneDetails, panelSel(kind));
				await page.waitForTimeout(200);
				const texte = await page.evaluate(texteJeAbschnitt, { panel: panelSel(kind), kopf: HUBKOPF });
				for (const mk of MARKER) expect(texte[mk]?.length ?? 0, `${kind} ${lang}: Abschnitt ${mk} ohne sichtbaren Text`).toBeGreaterThan(0);
				writeFileSync(path.join(ordner, `texte-${KTX[kind]}-${lang}.json`), JSON.stringify(texte, null, 2) + '\n');
			} finally {
				await hub.aufraeumen();
			}
		}
	}
});
