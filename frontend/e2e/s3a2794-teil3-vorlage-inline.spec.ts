// E2E (Staging) — Issue #3190 (Epic #2913): „Als eigene Vorlage speichern“ als Inline-Karte nach Mockup.
// Spec: docs/specs/modules/feat_3190_vorlage_dialog_inline.md (AC-1 bis AC-8).
// Derselbe Test-Code für Trip (route) und Orts-Vergleich (vergleich).
//
// Dateiname bewusst ohne Ziffern im Namensteil: die Staging-Konfiguration sammelt nur
// /s3a2794-teil3-[a-z-]+\.spec\.ts/ (playwright.2794-s3a3.staging.config.ts).
//
//   AC-1  Karte direkt unter der Vorlage-Karte und vor der Metrik-Karte, ohne Scrim/×/aria-modal;
//         der Auslöser schaltet um (aria-expanded, aria-controls).
//   AC-2  Ankreuzfeld-Text je Kontext („… neue Trips“ / „… neue Orte“).
//   AC-3  Lesereihenfolge Titel, Name, Beschreibung, Ankreuzfeld, Hinweis, Speichern vor Abbrechen.
//   AC-4  Pflichtfehler direkt unter Name, nichts gespeichert.
//   AC-5  Speichern mit Beschreibung und angekreuztem Standard (Klick auf den TEXT): Karte zu, Meldung,
//         Vorlage per API mit is_default und #3189-Herkunft; Aufräumen im finally.
//   AC-6  Abbrechen und Escape (Fokus in der Karte) schließen, Fokus zurück auf den Auslöser.
//   AC-7  Picker offen + Karte offen, Escape mit Fokus im Picker: nur der Picker schließt.
//   AC-8  Fokus nach dem Öffnen im Namensfeld, Gruppe mit Titel benannt, Bedienziele ≥ 44 px.
//
//   cd frontend && npx playwright test --config playwright.2794-s3a3.staging.config.ts s3a2794-teil3-vorlage-inline

import { test, expect, type Locator } from '@playwright/test';
import { HUB_KINDS } from './helpers';
import { DESKTOP, WT, oeffneWetter, seedWetter, stand, type Json } from './s3a2794-teil3.helpers';

const STANDARD_TEXT = { route: 'Als Standard für neue Trips', vergleich: 'Als Standard für neue Orte' } as const;
const TITEL = 'Als eigene Vorlage speichern';

async function box(l: Locator) {
	const b = await l.boundingBox();
	expect(b, 'Element ohne Box (nicht sichtbar?)').toBeTruthy();
	return b!;
}

for (const kind of HUB_KINDS) {
	test(`#3190 (${kind}): Inline-Karte öffnen, umschalten, Escape/Abbrechen mit Fokus-Rückgabe, Picker-Escape unabhängig`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'alpen-trekking' });
		try {
			const reiter = await oeffneWetter(page, kind, hub.id);
			const ausloeser = reiter.getByTestId(WT.alsEigene);
			const dialog = page.getByTestId(WT.dialog);
			await expect(ausloeser).toHaveAttribute('aria-expanded', 'false');

			// AC-1: öffnen, Platz und Optik
			await ausloeser.click();
			await expect(dialog).toBeVisible();
			await expect(ausloeser).toHaveAttribute('aria-expanded', 'true');
			const id = await dialog.getAttribute('id');
			expect(id, 'Karte ohne id').toBeTruthy();
			await expect(ausloeser).toHaveAttribute('aria-controls', id!);
			await expect(dialog).toHaveAttribute('role', 'group');
			await expect(page.locator('[aria-modal="true"]'), 'AC-1: kein modales Overlay').toHaveCount(0);
			await expect(page.getByRole('dialog'), 'AC-1: kein role=dialog').toHaveCount(0);
			await expect(dialog.getByRole('button', { name: /schließen|×/i }), 'AC-1: kein Schließen-Kreuz').toHaveCount(0);
			const vorlage = await box(reiter.locator('[data-abschnitt="vorlage"]').first());
			const karte = await box(dialog);
			const metriken = await box(reiter.locator('[data-abschnitt="metriken"]').first());
			expect(karte.y, 'AC-1: Karte unter der Vorlage-Karte').toBeGreaterThanOrEqual(vorlage.y + vorlage.height - 1);
			expect(metriken.y, 'AC-1: Metrik-Karte unter der Speichern-Karte').toBeGreaterThanOrEqual(karte.y + karte.height - 1);

			// AC-8: Gruppe mit Titel benannt, Fokus im Namensfeld
			await expect(page.getByRole('group', { name: TITEL })).toBeVisible();
			await expect(dialog.getByTestId(WT.dialogName)).toBeFocused();

			// AC-2: Ankreuzfeld mit Text je Kontext, zugänglicher Name
			await expect(dialog.getByTestId(WT.dialogStandard)).toContainText(STANDARD_TEXT[kind]);
			await expect(dialog.getByRole('checkbox', { name: STANDARD_TEXT[kind] })).toHaveCount(1);
			await expect(dialog.locator('textarea'), 'Beschreibung einzeilig').toHaveCount(0);
			await expect(dialog.locator('[role="switch"]'), 'kein Schalter mehr').toHaveCount(0);

			// AC-3: Lesereihenfolge
			const folge = [
				dialog.getByText(TITEL, { exact: true }),
				dialog.getByTestId(WT.dialogName),
				dialog.getByTestId(WT.dialogBeschreibung),
				dialog.getByTestId(WT.dialogStandard),
				dialog.getByTestId(WT.dialogHinweis)
			];
			let vorher = -1;
			for (const l of folge) {
				const b = await box(l);
				expect(b.y, 'AC-3: Reihenfolge von oben nach unten').toBeGreaterThan(vorher);
				vorher = b.y;
			}
			const speichern = await box(dialog.getByTestId(WT.dialogSpeichern));
			const abbrechen = await box(dialog.getByRole('button', { name: 'Abbrechen', exact: true }));
			expect(speichern.y, 'Knöpfe unter dem Hinweis').toBeGreaterThan(vorher);
			expect(speichern.x < abbrechen.x || speichern.y < abbrechen.y, 'AC-3: Speichern vor Abbrechen').toBe(true);

			// AC-8: Bedienziele ≥ 44 px
			for (const l of [dialog.getByTestId(WT.dialogName), dialog.getByTestId(WT.dialogBeschreibung), dialog.getByTestId(WT.dialogSpeichern), dialog.getByRole('button', { name: 'Abbrechen', exact: true }), dialog.getByTestId(WT.dialogStandard)]) {
				expect((await box(l)).height, 'AC-8: Touch-Ziel').toBeGreaterThanOrEqual(44);
			}

			// AC-4: Pflichtfehler direkt unter Name
			await dialog.getByTestId(WT.dialogSpeichern).click();
			const fehler = dialog.getByTestId(WT.dialogFehler);
			await expect(fehler).toHaveText('Gib der Vorlage einen Namen.');
			const f = await box(fehler);
			expect(f.y, 'AC-4: Fehler unter dem Namensfeld').toBeGreaterThan((await box(dialog.getByTestId(WT.dialogName))).y);
			expect(f.y, 'AC-4: Fehler vor der Beschreibung').toBeLessThan((await box(dialog.getByTestId(WT.dialogBeschreibung))).y);
			await expect(dialog.getByTestId(WT.dialogName)).toHaveAttribute('aria-invalid', 'true');

			// AC-1: zweiter Klick schließt
			await ausloeser.click();
			await expect(dialog).toHaveCount(0);
			await expect(ausloeser).toHaveAttribute('aria-expanded', 'false');

			// AC-6: Escape bei Fokus in der Karte schließt, Fokus zurück auf den Auslöser
			await ausloeser.click();
			await expect(dialog.getByTestId(WT.dialogName)).toBeFocused();
			await expect(dialog.getByTestId(WT.dialogFehler), 'Umschalten setzt den Fehler zurück').toHaveCount(0);
			await page.keyboard.press('Escape');
			await expect(dialog).toHaveCount(0);
			await expect(ausloeser).toBeFocused();

			// AC-6: Abbrechen schließt, Fokus zurück auf den Auslöser
			await ausloeser.click();
			await dialog.getByRole('button', { name: 'Abbrechen', exact: true }).click();
			await expect(dialog).toHaveCount(0);
			await expect(ausloeser).toBeFocused();

			// AC-7: Picker-Escape schließt nur den Picker, die offene Karte bleibt
			await ausloeser.click();
			await expect(dialog).toBeVisible();
			await reiter.getByTestId(WT.picker).click();
			const menue = reiter.locator('[data-abschnitt="vorlage-auswahl"]');
			await expect(menue).toBeVisible();
			await reiter.getByTestId(WT.picker).focus();
			await page.keyboard.press('Escape');
			await expect(menue).toHaveCount(0);
			await expect(dialog, 'AC-7: Karte bleibt beim Picker-Escape offen').toBeVisible();
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`#3190 AC-5 (${kind}): Speichern mit Beschreibung und angekreuztem Standard (Klick auf den Text)`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'alpen-trekking' });
		const name = `E2E-GZ-3190-${kind}-${Date.now()}`;
		let presetId: string | null = null;
		try {
			const aboName = String((await stand(page.request, kind, hub.id)).name ?? '');
			const reiter = await oeffneWetter(page, kind, hub.id);
			const ausloeser = reiter.getByTestId(WT.alsEigene);
			await ausloeser.click();
			const dialog = page.getByTestId(WT.dialog);
			await dialog.getByTestId(WT.dialogName).fill(name);
			await dialog.getByTestId(WT.dialogBeschreibung).fill('E2E einzeilig');
			const haken = dialog.getByRole('checkbox', { name: STANDARD_TEXT[kind] });
			await expect(haken).not.toBeChecked();
			// ganzer Text klickbar (label.chk im Mockup): das unsichtbare Kontrollkästchen des Haken-Atoms liegt bewusst
			// über dem ganzen <label> (Tippfläche ≥ 44 px), es fängt den Klick. Wie ein Nutzer klicken wir daher auf die
			// sichtbare Fläche über dem Text — Mittelpunkt des Text-Spans, gezielt per Maus, ohne force (Actionability bleibt).
			const text = dialog.getByTestId(WT.dialogStandard).getByText(STANDARD_TEXT[kind], { exact: true });
			const tb = await box(text);
			const labelBox = await box(dialog.getByTestId(WT.dialogStandard));
			await dialog.getByTestId(WT.dialogStandard).click({ position: { x: tb.x - labelBox.x + tb.width / 2, y: tb.y - labelBox.y + tb.height / 2 } });
			await expect(haken).toBeChecked();

			const post = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/metric-presets');
			await dialog.getByTestId(WT.dialogSpeichern).click();
			const antwort = await post;
			expect(antwort.ok(), `POST /api/metric-presets: ${antwort.status()}`).toBeTruthy();
			const body = (await antwort.json()) as Json;
			presetId = String(body.id);
			const gesendet = antwort.request().postDataJSON() as Json;
			expect(gesendet.is_default, 'Ankreuzfeld nicht übernommen').toBe(true);
			expect(gesendet.description).toBe('E2E einzeilig');

			await expect(dialog).toHaveCount(0);
			await expect(ausloeser).toBeFocused();
			await expect(page.getByTestId(WT.dialogErfolg)).toHaveText(`Vorlage ‚${name}‘ gespeichert. Du findest sie unter ‚Eigene‘.`);

			const liste = (await (await page.request.get('/api/metric-presets')).json()) as Json[];
			const gespeichert = liste.find((p) => p.id === presetId);
			expect(gespeichert, 'Vorlage nicht gespeichert').toBeTruthy();
			expect(gespeichert.is_default, 'Standard nicht gespeichert').toBe(true);
			expect(gespeichert.kind).toBe(kind);
			if (aboName) expect(gespeichert.herkunft, '#3189-Herkunft fehlt').toEqual({ id: hub.id, name: aboName });
		} finally {
			if (presetId) await page.request.delete(`/api/metric-presets/${presetId}`).catch(() => {});
			else
				for (const p of (await (await page.request.get('/api/metric-presets')).json().catch(() => [])) as Json[])
					if (p.name === name) await page.request.delete(`/api/metric-presets/${p.id}`).catch(() => {});
			await hub.aufraeumen();
		}
	});
}
