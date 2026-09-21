// E2E — #1895 Schritt 2: die Alarmregel-Karte zeigt nur noch Metrik, Kanaele
// und den Aktiv-Haken. Δ-Schwelle, Zeitfenster, der Wert-Text („> 20 km/h") und
// die „Δ"-Pille sind aus BEIDEN Ansichten der Karte zurueckgebaut.
//
// Spec: docs/specs/modules/fix_1895_s2_alarmkarte_rueckbau.md (AC-1, AC-2, AC-5, AC-6, AC-7)
// Vorgaenger: docs/specs/modules/fix_1895_alarm_modus_rueckbau.md (#1895 Schritt 1)
//
// Diese Datei war bis #1895 der Sperr-Waechter aus #1488 Scheibe A („fuer Gewitter
// ist der Absolut-Modus gesperrt"). Sie wurde in Schritt 1 IN PLACE zum
// Abwesenheits-Waechter der Modus-Auswahl umgeschrieben und wird hier — wieder
// IN PLACE, wieder unter demselben Dateinamen — auf den Rueckbau von Δ-Schwelle
// und Zeitfenster nachgezogen. Der Name bleibt, weil die Datei in der E2E-Ratsche
// `.github/ci_e2e_specs.txt` (Zeile 246) steht und im `e2e`-Check der CI-Ampel
// laeuft. Ein neuer Dateiname haette den Ratschen-Eintrag entwertet — „Ratsche
// leeren macht den abhaengigen Test vakuum-gruen".
//
// Die Zusicherungen aus Schritt 1 (keine `mode-card-*`, keine Gruppe
// „Alarm-Modus", kein `alert-rule-threshold-abs`) BLEIBEN hier bestehen; sie
// werden nicht durch die neuen ersetzt, sondern um sie ergaenzt.
//
// Gemessener Befund (docs/context/fix-1895-s2-alarmkarte-rueckbau.md): die Karte
// bietet eine Δ-Schwelle und ein Zeitfenster an, die keinen Alarm ausloesen. Der
// Alarm-Ausloeser speist sich ausschliesslich aus den Empfindlichkeitsstufen
// (ADR-0043); `trip.alert_rules` wird dort nie gelesen. Die Bedienflaeche
// verspricht einen Regler, den es nicht gibt.
//
// BEWUSST GESTRICHEN (Schritt 2, Spec AC-6): die beiden Zeilen
// `toHaveValue('20')` / `toHaveValue('6h')` aus dem AC-7-Fall der Vorfassung
// (:199-200). Sie verlieren ihr Subjekt, weil die Felder verschwinden — der
// Wert 20/'6h' ist im Browser nicht mehr messbar. Die Zusicherung „eine neue
// Regel startet mit 20/6h" gilt unveraendert weiter und wird auf Bausteinebene
// bewacht (`__tests__/alertRegelNurAenderung.test.ts`, AC-7). Das ist keine
// stillschweigend fallengelassene Zusicherung, sondern ein Ebenenwechsel — und
// der Grund, warum er hier ausdruecklich steht.
//
// Gemessen wird hier die `.svelte`-Verdrahtung im echten Browser. Der SSR-Harness
// (node --test) erreicht den Bearbeiten-Zustand nicht und kann darum weder das
// Verschwinden der Felder noch das Ueberleben der Kanal-Chips belegen.

import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import * as path from 'node:path';

const MOBILE = { width: 390, height: 844 };

// Modus-Karten-Locator. ModeCard.svelte:58-60 wechselte die testid je nach Auswahl
// (`mode-card-absolute` <-> `mode-card-absolute-selected`) — ein exakter Vergleich
// wuerde die ausgewaehlte Karte uebersehen und faelschlich „nicht vorhanden"
// melden. Nach dem Rueckbau darf KEINE der beiden Varianten mehr auftauchen.
function modeCard(scope: ReturnType<Page['locator']>, mode: 'absolute' | 'delta' | 'both') {
	return scope.locator(`[data-testid="mode-card-${mode}"], [data-testid="mode-card-${mode}-selected"]`);
}

// Alle Modus-Karten zusammen — faengt auch eine vierte, neu erfundene Karte.
function alleModusKarten(scope: ReturnType<Page['locator']>) {
	return scope.locator('[data-testid^="mode-card-"]');
}

// AC-1: Abwesenheit von Δ-Schwelle und Zeitfenster in der Bearbeiten-Karte —
// dreifach gemessen, damit nicht eine blosse Umbenennung der testid das Feld
// unbemerkt am Leben haelt:
//   1. ueber die testids selbst,
//   2. testid-UNABHAENGIG ueber die Rolle (`spinbutton` = <input type="number">;
//      das war bis Schritt 2 das EINZIGE Zahlenfeld der Karte),
//   3. testid-UNABHAENGIG ueber die Beschriftung („Δ-Schwelle" / „Zeitfenster",
//      heute als aria-label an beiden Feldern). Nicht-exaktes Matching mit
//      Absicht: es faengt auch eine Umbeschriftung wie „Zeitfenster (h)".
async function erwarteKeineSchwelleUndKeinZeitfenster(edit: ReturnType<Page['locator']>) {
	await expect.soft(edit.getByTestId('alert-rule-threshold')).toHaveCount(0);
	await expect.soft(edit.getByTestId('alert-rule-delta-window')).toHaveCount(0);

	await expect.soft(edit.getByRole('spinbutton')).toHaveCount(0);
	await expect.soft(edit.locator('input[type="number"]')).toHaveCount(0);
	await expect.soft(edit.getByLabel('Δ-Schwelle')).toHaveCount(0);
	await expect.soft(edit.getByLabel('Zeitfenster')).toHaveCount(0);
}

// AC-1 Anti-Vakuum: die Bearbeiten-Karte steht wirklich und traegt die drei
// Bedienelemente, die BLEIBEN sollen. Ohne diese drei Zusicherungen hiesse
// „kein Schwellenfeld" bloss „kein DOM" — und der ganze Fall waere vakuum-gruen.
// Ersetzt die frueheren Positivkontrollen, die auf `alert-rule-threshold`
// zeigten (:141, :174 der Vorfassung) — genau das Element, das jetzt fehlen muss.
async function erwarteKarteStehtNoch(edit: ReturnType<Page['locator']>, metric: string) {
	await expect(edit.getByTestId('alert-rule-metric')).toHaveValue(metric);
	await expect(edit.getByTestId('alert-rule-channel-email')).toBeVisible();
	await expect(edit.getByTestId('alert-rule-save')).toBeVisible();
}

// AC-2: die Ansichtszeile zeigt keinen Wert und keine Pille mehr.
// Anti-Vakuum zuerst (Metrik-Name + mindestens ein Kanal-Chip): eine leere oder
// gar nicht gerenderte Zeile wuerde „keine Ziffer" sonst muehelos erfuellen.
async function erwarteZeileOhneWertUndOhnePille(
	row: ReturnType<Page['locator']>,
	metrikText: string
) {
	await expect(row).toBeVisible();
	await expect(row).toContainText(metrikText);
	expect(
		await row.locator('.channel-chip').count(),
		'Anti-Vakuum: die Zeile muss mindestens einen Kanal-Chip zeigen'
	).toBeGreaterThanOrEqual(1);

	await expect.soft(row.locator('.threshold')).toHaveCount(0);
	await expect.soft(row.locator('[data-slot="pill"]')).toHaveCount(0);

	const text = (await row.innerText()).replace(/\s+/g, ' ').trim();
	expect.soft(text, `Zeile darf kein „Δ" mehr zeigen: "${text}"`).not.toMatch(/Δ/);
	expect.soft(text, `Zeile darf kein „Abs" mehr zeigen: "${text}"`).not.toMatch(/Abs/);
	expect.soft(text, `Zeile darf keinen Zahlenwert mehr zeigen: "${text}"`).not.toMatch(/\d/);
	expect.soft(text, `Zeile darf kein Vergleichszeichen mehr zeigen: "${text}"`).not.toMatch(/[><≥]/);
	expect.soft(text, `Zeile darf keine Einheit „km/h" mehr zeigen: "${text}"`).not.toMatch(/km\/h/);
}

// `/trips/new` bis zum Alerts-Tab durchklicken. Uebernommen aus dem bereits
// funktionierenden `issue-776-metrics-toggle.spec.ts::openNewTripZeitplan()`
// (mobiler Pfad, Progressive-Tab-Unlock) — einziger zusaetzlicher Schritt ist der
// Klick auf „Alerts". Kein Trip wird angelegt: der GPX-Upload loest nur den
// zustandslosen `POST /api/gpx/parse` aus.
async function openNewTripAlerts(page: Page) {
	await page.setViewportSize(MOBILE);
	await page.goto('/trips/new');
	await page.getByTestId('trip-new-name-input-mobile').fill('#1895 Alarmregel-Karte');
	await page.getByTestId('trip-new-date-input').fill(new Date().toISOString().slice(0, 10));

	const tabbar = page.getByTestId('tn-mobile-tabbar');
	await tabbar.getByRole('tab', { name: /Etappen/ }).click({ force: true });

	const gpx = path.resolve('./e2e/fixtures/test-trip.gpx');
	// IMMER den ersten verbleibenden offenen Datei-Input frisch aufloesen: eine
	// Etappe mit gesetztem GPX verliert ihren Input komplett aus dem DOM
	// (TripNewEditor.svelte `{#if s.gpx}`), ein fixierter Index zeigt danach ins Leere.
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

	// Harter Surface-Check: ohne ihn waere jedes spaetere `toHaveCount(0)`
	// bedeutungslos (leerer DOM zaehlt auch 0). AlertRulesEditor wird sowohl im
	// .tn-desktop- als auch im .tn-mobile-Baum gemountet — daher scopen.
	const editor = page.locator('.tn-mobile').getByTestId('alert-rules-editor');
	await expect(editor).toBeVisible({ timeout: 15_000 });
	return editor;
}

// Legt eine Default-Regel an und oeffnet ihren Edit-Modus.
async function openFirstRuleEditor(page: Page, editor: ReturnType<Page['locator']>) {
	await editor.getByTestId('alert-rules-editor-add').click();
	await editor.getByTestId('alert-rule-kebab-trigger').first().click();
	await editor.getByTestId('alert-rule-edit-btn').first().click();
	const edit = editor.getByTestId('alert-rule-edit').first();
	await expect(edit).toBeVisible();
	return edit;
}

// Oeffnet den Edit-Modus einer bereits sichtbaren Regel (ohne eine neue anzulegen).
async function reopenRuleEditor(editor: ReturnType<Page['locator']>) {
	await editor.getByTestId('alert-rule-kebab-trigger').first().click();
	await editor.getByTestId('alert-rule-edit-btn').first().click();
	const edit = editor.getByTestId('alert-rule-edit').first();
	await expect(edit).toBeVisible();
	return edit;
}

test.describe('#1895 Schritt 2: Δ-Schwelle, Zeitfenster und Wert-Anzeige sind zurueckgebaut', () => {
	test('Boeen: weder Δ-Schwelle noch Zeitfenster, weiterhin keine Modus-Karten (AC-1)', async ({ page }) => {
		const editor = await openNewTripAlerts(page);
		const edit = await openFirstRuleEditor(page, editor);

		// Positivkontrolle: die Card ist wirklich die Bearbeiten-Card der Boeen-Regel
		// und traegt die Bedienelemente, die bleiben sollen.
		await erwarteKarteStehtNoch(edit, 'wind_gust');

		// Soft, damit ein frueher Bruch die spaeteren Zusicherungen nicht ungemessen
		// laesst — „nicht ausgefuehrt" saehe im RED-Lauf aus wie „erfuellt".

		// — Bestand aus Schritt 1: die Modus-Auswahl bleibt fort.
		await expect.soft(alleModusKarten(edit)).toHaveCount(0);
		await expect.soft(modeCard(edit, 'absolute')).toHaveCount(0);
		await expect.soft(modeCard(edit, 'delta')).toHaveCount(0);
		await expect.soft(modeCard(edit, 'both')).toHaveCount(0);
		await expect.soft(edit.locator('[role="radiogroup"][aria-label="Alarm-Modus"]')).toHaveCount(0);
		await expect.soft(edit.getByTestId('alert-rule-delta-only-hint')).toHaveCount(0);
		await expect.soft(edit.getByTestId('alert-rule-threshold-abs')).toHaveCount(0);
		await expect.soft(edit.getByTestId('alert-rule-threshold-delta')).toHaveCount(0);

		// — NEU in Schritt 2 (UMGEDREHT gegenueber :122-126 der Vorfassung, die
		//   `toHaveCount(1)`/`toBeVisible()` verlangte): der Δ-Zweig faellt mit.
		await erwarteKeineSchwelleUndKeinZeitfenster(edit);

		// Speichern-Knopf traegt fest „Speichern", nie mehr „Beide Regeln speichern".
		await expect.soft(edit.getByTestId('alert-rule-save')).toHaveText('Speichern');
	});

	test('Metrik-Wechsel: auch Gewitter und Temperatur (Änderung) ohne Schwelle und Zeitfenster (AC-1)', async ({ page }) => {
		const editor = await openNewTripAlerts(page);
		const edit = await openFirstRuleEditor(page, editor);

		for (const metric of ['thunder_level', 'temperature_change']) {
			await edit.getByTestId('alert-rule-metric').selectOption(metric);
			// Anti-Vakuum je Durchlauf: die Card steht nach dem Wechsel noch und
			// traegt Kanal-Chips und Speichern. Sonst waere „kein Feld" nur „nichts da".
			await erwarteKarteStehtNoch(edit, metric);

			await expect.soft(alleModusKarten(edit)).toHaveCount(0);
			await expect.soft(edit.locator('[role="radiogroup"][aria-label="Alarm-Modus"]')).toHaveCount(0);
			await expect.soft(edit.getByTestId('alert-rule-threshold-abs')).toHaveCount(0);
			await expect.soft(edit.getByTestId('alert-rule-delta-only-hint')).toHaveCount(0);
			// UMGEDREHT gegenueber :141/:147 der Vorfassung (dort `toHaveCount(1)`).
			await erwarteKeineSchwelleUndKeinZeitfenster(edit);
		}

		// Die Stufenwoerter aus dem alten Gewitter-Absolut-Select (#1488) bleiben weg.
		await edit.getByTestId('alert-rule-metric').selectOption('thunder_level');
		await expect.soft(edit.locator('option', { hasText: /^MITTEL$/ })).toHaveCount(0);
		await expect.soft(edit.locator('option', { hasText: /^HOCH$/ })).toHaveCount(0);
	});

	test('Weder Δ-Schwelle noch Zeitfenster noch Absolut-Feld — fuer KEINE Metrik (AC-1)', async ({ page }) => {
		const editor = await openNewTripAlerts(page);
		const edit = await openFirstRuleEditor(page, editor);

		// Metrik-Werte aus dem DOM lesen, nicht abschreiben: eine abgeschriebene
		// Liste wuerde beim naechsten neuen Select-Eintrag still veralten.
		const werte = await edit
			.getByTestId('alert-rule-metric')
			.locator('option')
			.evaluateAll((opts) => opts.map((o) => (o as HTMLOptionElement).value));
		// Anti-Vakuum: eine leere Optionsliste wuerde die Schleife ueberspringen und
		// den Test gruen lassen, ohne eine einzige Metrik gemessen zu haben.
		expect(werte.length).toBeGreaterThanOrEqual(9);

		for (const wert of werte) {
			await edit.getByTestId('alert-rule-metric').selectOption(wert);
			// Positivkontrolle je Metrik: die Card ist gerendert und bedienbar.
			// (Bis Schritt 1 stand hier `alert-rule-threshold` toHaveCount(1) — genau
			// das Element, das jetzt fehlen MUSS. Es taugt darum nicht mehr als
			// Positivkontrolle und ist durch Metrik/Kanal/Speichern ersetzt.)
			await erwarteKarteStehtNoch(edit, wert);

			// … und traegt weder Absolut-Feld noch Δ-Schwelle noch Zeitfenster.
			await expect.soft(edit.getByTestId('alert-rule-threshold-abs')).toHaveCount(0);
			await erwarteKeineSchwelleUndKeinZeitfenster(edit);

			// Die Modus-Auswahl ist die EINZIGE Tuer zum Absolut-Feld: bis #1895 war
			// `alert-rule-threshold-abs` nur im Modus „Beides" im DOM, im Modus
			// „Absolut" dagegen nie. Ohne diese Zeile waere der Absolut-Teil des
			// Testfalls vakuum-gruen — er lief am 2026-09-21 gegen den unveraenderten
			// Stand gruen durch, obwohl jede Metrik noch drei Modus-Karten anbot.
			await expect.soft(alleModusKarten(edit)).toHaveCount(0);
		}
	});

	test('Neue Regel erscheint ohne Wert und ohne Pille (AC-7, AC-2)', async ({ page }) => {
		const editor = await openNewTripAlerts(page);
		await editor.getByTestId('alert-rules-editor-add').click();

		// Anti-Vakuum: genau eine Zeile — nicht null (dann waere „kein Wert"
		// bedeutungslos) und nicht zwei (das alte „Beides" erzeugte ein Paar).
		await expect(editor.getByTestId('alert-rule-row')).toHaveCount(1);
		const row = editor.getByTestId('alert-rule-row').first();

		// UMGEDREHT gegenueber :195 der Vorfassung (dort `toContainText('Δ')`).
		await erwarteZeileOhneWertUndOhnePille(row, 'Böen');

		// GESTRICHEN (s. Kopfkommentar): hier standen bis Schritt 1
		//   await expect.soft(edit.getByTestId('alert-rule-threshold')).toHaveValue('20');
		//   await expect.soft(edit.getByTestId('alert-rule-delta-window')).toHaveValue('6h');
		// Beide Felder existieren nicht mehr; 20/'6h' ist im Browser nicht messbar.
		// Die Zusicherung lebt weiter in
		// `src/lib/components/alert-rules-editor/__tests__/alertRegelNurAenderung.test.ts`
		// (newDefaultRule() -> 20/'6h' UND expandRules(newDefaultRule()) -> 20/'6h').
		// Statt des Werts wird hier geprueft, dass die Bearbeiten-Karte sich weiter
		// oeffnen laesst und leer von beidem ist — sonst waere der Fall nach dem
		// Streichen der zwei Zeilen ohne Gegenstand.
		const edit = await reopenRuleEditor(editor);
		await erwarteKarteStehtNoch(edit, 'wind_gust');
		await erwarteKeineSchwelleUndKeinZeitfenster(edit);
	});

	test('Speichern erhaelt genau eine Regel — ohne Wert, ohne Pille (AC-2, AC-5)', async ({ page }) => {
		const editor = await openNewTripAlerts(page);
		const edit = await openFirstRuleEditor(page, editor);

		await edit.getByTestId('alert-rule-metric').selectOption('precipitation_sum');

		// `enabled` wird hier bewusst UMGESCHALTET, nicht nur mitgelesen. An der
		// reinen Funktion expandRules() ist das Durchreichen zwar geprueft, die
		// Zusicherung WIRKT aber in saveEdit() der `.svelte`-Komponente: wer dort
		// `enabled: true` erzwaenge, wuerde von keinem Funktionstest gefangen
		// (Adversary-Mutation M17). Darum laeuft der Nachweis ueber die Bedien-
		// flaeche: abwaehlen -> speichern -> die Ansichtszeile muss inaktiv sein.
		const editAktiv = edit.getByRole('checkbox');
		await expect(editAktiv).toBeChecked();
		await editAktiv.click();
		await expect(editAktiv).not.toBeChecked();

		// F001 — die Regel-`id` wird hier MITGEMESSEN, ohne sie je zu lesen:
		// AlertRulesEditor.svelte:50 schluesselt die Liste mit
		// `{#each rules as rule, i (rule.id)}`. Ein keyed each zerstoert den
		// `<li>`-Block, sobald sich sein Key aendert, und baut einen neuen auf.
		// Der hier VOR dem Speichern gegriffene Knoten bleibt also nur dann mit
		// dem Dokument verbunden, wenn die `id` das Speichern unveraendert
		// ueberlebt. Die Zusicherung steht am Ende dieses Falls.
		const liVorSpeichern = await editor.locator('.rules-list > li').first().elementHandle();

		await edit.getByTestId('alert-rule-save').click();

		// Genau eine Zeile: nicht null (Regel verloren -> das Pruef-Gate
		// has_active_rules koennte kippen) und nicht zwei (das alte „Beides"
		// erzeugte ein Regel-Paar).
		await expect(editor.getByTestId('alert-rule-row')).toHaveCount(1);
		const row = editor.getByTestId('alert-rule-row').first();

		// UMGEDREHT gegenueber :237 der Vorfassung (dort `toContainText('Δ')`):
		// nach dem Speichern zeigt die Zeile den Metrik-Namen und die Kanal-Chips,
		// aber keinen Wert („> 50 mm") und keine Pille.
		await erwarteZeileOhneWertUndOhnePille(row, 'Niederschlag');

		// HART, nicht soft: das ist die einzige Messung von `enabled` am
		// Speicherweg. Ein erzwungenes `enabled: true` in saveEdit() muss hier
		// unmissverstaendlich rot werden.
		await expect(row.getByRole('checkbox')).not.toBeChecked();
		// Keine Paar-Markierung mehr, weil expandRules() nie mehr zwei Regeln liefert.
		await expect.soft(editor.getByTestId('pair-indicator')).toHaveCount(0);

		// HART und bewusst als LETZTE Zusicherung (alle vorherigen Awaits haben
		// den Re-Render abgewartet): `isConnected === false` heisst, dass der
		// keyed-each-Block neu aufgebaut wurde — und das passiert genau dann,
		// wenn saveEdit() eine NEUE `id` vergibt (Adversary-Mutation M16).
		// `?.` statt `!`: ein fehlender Handle liefert `undefined` und faellt
		// ebenfalls durch, statt still gruen zu bleiben.
		expect(await liVorSpeichern?.evaluate((n) => n.isConnected)).toBe(true);
	});

	// Dieser Fall ist ABSICHTLICH schon vor dem Umbau gruen und muss es danach
	// bleiben: AC-5 sichert nicht eine neue Faehigkeit zu, sondern das Ueberleben
	// einer vorhandenen. Sein Biss wird darum nicht ueber RED gemessen, sondern in
	// der Mutations-Gegenprobe: faellt der Chip-Block aus der Edit-Card oder aus
	// der Ansichtszeile, muss dieser Fall rot werden — und `alertChannels.test.ts`
	// muss dabei gruen bleiben (genau das ist im Pruefbericht festzuhalten).
	// Gemessen am 2026-09-21: gruen gegen den unveraenderten Stand.
	test('Kanal-Chips ueberleben den Rueckbau und schalten weiterhin um (AC-5)', async ({ page }) => {
		const editor = await openNewTripAlerts(page);
		const edit = await openFirstRuleEditor(page, editor);

		// Standardkanaele in `/trips/new` sind E-Mail und Telegram (SMS ist aus).
		const email = edit.getByTestId('alert-rule-channel-email');
		const telegram = edit.getByTestId('alert-rule-channel-telegram');
		await expect(email).toBeVisible();
		await expect(telegram).toBeVisible();
		await expect(edit.getByTestId('alert-rule-channel-sms')).toHaveCount(0);
		await expect(email).toHaveAttribute('aria-pressed', 'true');
		await expect(telegram).toHaveAttribute('aria-pressed', 'true');

		// Umschalten erreicht toggleAlertChannel(): Telegram ab, E-Mail bleibt.
		await telegram.click();
		await expect(telegram).toHaveAttribute('aria-pressed', 'false');
		await expect(email).toHaveAttribute('aria-pressed', 'true');

		await edit.getByTestId('alert-rule-save').click();

		// Roundtrip IM EDITOR (kein API-Aufruf): die Ansichtszeile zeigt nur E-Mail.
		const row = editor.getByTestId('alert-rule-row').first();
		await expect(row).toBeVisible();

		// F005 — Gegenrichtung zur `enabled`-Messung des AC-2-Falls: dort wird der
		// Haken ABGEWAEHLT und danach „nicht gesetzt" erwartet, was nur ein
		// erzwungenes `enabled: true` faengt. Hier bleibt der Haken UNBERUEHRT
		// (geklickt werden nur Kanal-Chips), also muss er das Speichern gesetzt
		// ueberleben. Ein in saveEdit() erzwungenes `enabled: false` wuerde jede
		// Regel still deaktivieren und nur an dieser Stelle rot.
		await expect(row.getByRole('checkbox')).toBeChecked();

		await expect.soft(row.locator('.channel-chip')).toHaveText(['E-Mail']);

		// Und erneut geoeffnet steht Telegram weiter auf „aus".
		const wieder = await reopenRuleEditor(editor);
		await expect.soft(wieder.getByTestId('alert-rule-channel-email')).toHaveAttribute('aria-pressed', 'true');
		await expect.soft(wieder.getByTestId('alert-rule-channel-telegram')).toHaveAttribute('aria-pressed', 'false');
	});
});
