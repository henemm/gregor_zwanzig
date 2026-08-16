// E2E — #1488 Scheibe A: der Absolut-Modus ist fuer Gewitter gesperrt.
//
// Spec: docs/specs/modules/fix_1488_sa_gewitter_absolutregel.md (AC-1, AC-2)
//
// Gemessener Bug (docs/context/fix-1488-gewitterstufen.md, Befund 1+3): auf
// `/trips/new` -> Alarmregeln laesst sich fuer die Metrik „Gewitter" eine Regel
// im Modus „Absolut" mit den Schwellen „MITTEL"/„HOCH" anlegen. Der Alarm-Dienst
// wertet diese Schwelle nie aus, und beide Woerter alarmieren eine Stufe frueher
// als beschriftet. Die Bedienflaeche verspricht eine Wirkung, die es nicht gibt.
//
// Regulaerer CI-Spec (kein `.staging.spec.ts`) und auf `.github/ci_e2e_specs.txt`
// — ein von Hand gestarteter Staging-Spec belegt den Fix einmal und bewacht ihn
// danach nie wieder; genau dieser Fehlertyp ist der Gegenstand des Tickets.

import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import * as path from 'node:path';

const MOBILE = { width: 390, height: 844 };

// Locator fuer eine Modus-Karte. ModeCard.svelte:58-60 wechselt die testid je
// nach Auswahl (`mode-card-absolute` <-> `mode-card-absolute-selected`) — ein
// exakter Testid-Vergleich wuerde die ausgewaehlte Karte uebersehen und
// „nicht vorhanden" melden, obwohl sie dasteht.
function modeCard(scope: ReturnType<Page['locator']>, mode: 'absolute' | 'delta' | 'both') {
	return scope.locator(`[data-testid="mode-card-${mode}"], [data-testid="mode-card-${mode}-selected"]`);
}

// `/trips/new` bis zum Alerts-Tab durchklicken. Uebernommen aus dem bereits
// funktionierenden `issue-776-metrics-toggle.spec.ts::openNewTripZeitplan()`
// (mobiler Pfad, Progressive-Tab-Unlock) — einziger zusaetzlicher Schritt ist
// der Klick auf „Alerts". Kein Trip wird angelegt: der GPX-Upload loest nur den
// zustandslosen `POST /api/gpx/parse` aus.
async function openNewTripAlerts(page: Page) {
	await page.setViewportSize(MOBILE);
	await page.goto('/trips/new');
	await page.getByTestId('trip-new-name-input-mobile').fill('#1488 Gewitter-Alarmregel');
	await page.getByTestId('trip-new-date-input').fill(new Date().toISOString().slice(0, 10));

	const tabbar = page.getByTestId('tn-mobile-tabbar');
	await tabbar.getByRole('tab', { name: /Etappen/ }).click({ force: true });

	const gpx = path.resolve('./e2e/fixtures/test-trip.gpx');
	// IMMER den ersten verbleibenden offenen Datei-Input frisch aufloesen: eine
	// Etappe mit gesetztem GPX verliert ihren Input komplett aus dem DOM
	// (TripNewEditor.svelte `{#if s.gpx}`), ein fixierter Index zeigt danach
	// ins Leere.
	const stageCount = await page.locator('.tn-mobile input[type="file"][accept=".gpx"]').count();
	for (let i = 0; i < stageCount; i++) {
		const input = page.locator('.tn-mobile input[type="file"][accept=".gpx"]').first();
		await Promise.all([
			page.waitForResponse((r) => r.url().includes('/api/gpx/parse'), { timeout: 30_000 }).catch(() => null),
			input.setInputFiles(gpx)
		]);
		await page.waitForTimeout(600);
	}

	await tabbar.getByRole('tab', { name: /Wetter/ }).click({ force: true });
	await tabbar.getByRole('tab', { name: /Zeitplan/ }).click({ force: true });
	await tabbar.getByRole('tab', { name: /Alerts/ }).click({ force: true });

	// Harter Surface-Check: ohne den waere jedes spaetere `toHaveCount(0)`
	// bedeutungslos (leerer DOM zaehlt auch 0). AlertRulesEditor wird sowohl im
	// .tn-desktop- als auch im .tn-mobile-Baum gemountet — daher scopen.
	const editor = page.locator('.tn-mobile').getByTestId('alert-rules-editor');
	await expect(editor).toBeVisible({ timeout: 15_000 });
	return editor;
}

// Legt eine Default-Regel an (wind_gust/absolut) und oeffnet ihren Edit-Modus.
async function openFirstRuleEditor(page: Page, editor: ReturnType<Page['locator']>) {
	await editor.getByTestId('alert-rules-editor-add').click();
	await editor.getByTestId('alert-rule-kebab-trigger').first().click();
	await editor.getByTestId('alert-rule-edit-btn').first().click();
	const edit = editor.getByTestId('alert-rule-edit').first();
	await expect(edit).toBeVisible();
	return edit;
}

test.describe('#1488 Scheibe A: Absolut-Modus fuer Gewitter gesperrt', () => {
	test('Böen: Absolut-Karte bleibt vorhanden und waehlbar (AC-2 Positivkontrolle)', async ({ page }) => {
		const editor = await openNewTripAlerts(page);
		const edit = await openFirstRuleEditor(page, editor);

		// Default-Regel ist wind_gust (newDefaultRule) — keine Delta-only-Metrik.
		await expect(edit.getByTestId('alert-rule-metric')).toHaveValue('wind_gust');
		await expect(modeCard(edit, 'absolute')).toHaveCount(1);
		await expect(modeCard(edit, 'absolute')).toBeEnabled();
		await modeCard(edit, 'absolute').click();
		await expect(edit.locator('[data-testid="mode-card-absolute-selected"]')).toHaveCount(1);
	});

	test('Gewitter: keine Absolut-Karte, kein MITTEL/HOCH-Select (AC-1)', async ({ page }) => {
		const editor = await openNewTripAlerts(page);
		const edit = await openFirstRuleEditor(page, editor);

		// Positivkontrolle im selben Testfall: bei Böen steht die Absolut-Karte da.
		await expect(modeCard(edit, 'absolute')).toHaveCount(1);

		await edit.getByTestId('alert-rule-metric').selectOption('thunder_level');
		// Gegenprobe, dass die Modus-Auswahl nach dem Metrik-Wechsel ueberhaupt
		// noch gerendert wird — sonst waere die Abwesenheit der Absolut-Karte nur
		// die Abwesenheit der ganzen Zeile.
		await expect(modeCard(edit, 'delta')).toHaveCount(1);

		// AC-1a: keine „Absolut"-Karte mehr fuer Gewitter.
		// AC-1b: der Schwellwert-Select mit MITTEL/HOCH existiert nicht mehr im DOM.
		// Beide als SOFT-Assertion: eine harte wuerde den Testfall an der ersten
		// Stelle abbrechen, und die zweite Zusicherung bliebe im RED-Lauf
		// ungemessen — „nicht ausgefuehrt" saehe dann aus wie „erfuellt".
		await expect.soft(modeCard(edit, 'absolute')).toHaveCount(0);
		await expect.soft(edit.locator('option', { hasText: /^MITTEL$/ })).toHaveCount(0);
		await expect.soft(edit.locator('option', { hasText: /^HOCH$/ })).toHaveCount(0);

		// AC-1c: der Modus darf nach dem Wechsel nicht auf der verschwundenen
		// „Absolut"-Auswahl haengenbleiben. Ohne diese Zusicherung faengt KEIN
		// Test die Entfernung des editMode-Guards (in der GREEN-Phase per
		// Mutation gemessen, s. gegenprobe_mutation_editmode_guard.log) — der
		// Nutzer saehe dann eine Schwelle, die beim Speichern still durch die
		// Δ-Vorgabe ersetzt wird.
		await expect.soft(edit.locator('[data-testid="mode-card-delta-selected"]')).toHaveCount(1);

		// AC-1d: die Sperre haengt an DELTA_ONLY_METRICS, nicht am Namen
		// 'thunder_level'. Ohne eine ZWEITE Delta-only-Metrik bliebe eine
		// Verengung des Guards auf `draft.metric !== 'thunder_level'` unbemerkt
		// (Adversary-Fund F001) — dann saehe der Nutzer bei
		// „Temperatur (Änderung)" weiterhin eine anklickbare Absolut-Karte,
		// deren Schwelle expandRules() beim Speichern still zu kind='delta'
		// umschreibt. Genau dieses „sichtbar, aber wirkungslos" ist der Gegen-
		// stand des Tickets. `temperature_change` gewaehlt, weil im selben
		// Select erreichbar: kein zweiter Seitenaufbau, kein weiterer
		// GPX-Durchlauf, damit der billigste der drei verbleibenden Faelle.
		await edit.getByTestId('alert-rule-metric').selectOption('temperature_change');
		await expect.soft(modeCard(edit, 'delta')).toHaveCount(1);
		await expect.soft(modeCard(edit, 'absolute')).toHaveCount(0);
	});
});

// AC-4 („Bestandsregel ueberlebt PUT→GET unveraendert") ist per PO-Entscheid
// vom 2026-08-16 gestrichen und der zugehoerige Testfall hier entfernt: der
// Go-Store normalisiert `alert_rules` bei jedem Laden und Speichern
// (internal/store/trip.go:206/:238 -> model.SyncAlertRules), die Given-Bedingung
// ist also gar nicht herstellbar. Der Befund ist in #1895 nachgetragen; die
// Zusicherung „Scheibe A fuegt keinen Umschreibe-Code hinzu" bleibt eine
// Unterlassung, kein Testfall.
