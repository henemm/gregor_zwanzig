<script lang="ts" module>
	let meldungZaehler = 0;
</script>

<script lang="ts">
	// Issue #2881 Lieferung B (R2, ADR-0111): Datumsfeld als Design-System-Baustein statt
	// <input type="date"> — bits-ui DatePicker: Segmente Tag/Monat/Jahr, Kalender im Popover,
	// Wochenbeginn Montag. Format nach Konto-Sprache wie im übrigen UI: de `19.11.2026`,
	// en Tag zuerst `19/11/2026` (en-GB; fmtDateNumeric zeigt `19 Nov 2026`, nie Monat zuerst).
	// Wert nach außen unverändert als String `YYYY-MM-DD` (Speicherpfade bleiben, ADR-0101).
	// Von Trip und Vergleich nutzbar (CLAUDE.md Trip/Ortsvergleich-Teilung).
	// Spec: docs/specs/modules/rework_2881_design_system_bereinigung.md (AC-1, AC-2, AC-3)
	import { tick, untrack } from 'svelte';
	import { DatePicker } from 'bits-ui';
	import { SegmentFeldMeldung, TippZaehler } from './segmentFeldMeldung.ts';
	import { DatumTipp, ruecknahmeNachUngueltig, type Segment } from './datumTipp.ts';
	import { parseDate, type DateValue } from '@internationalized/date';
	import { t, locale } from '$lib/i18n';

	interface Props {
		/** `YYYY-MM-DD` oder leer. */
		value?: string;
		/** Neues Datum als `YYYY-MM-DD` (erst bei vollständigem, vierstelligem Jahr). */
		onchange?: (iso: string) => void;
		testid?: string;
		ariaLabel?: string;
		required?: boolean;
		disabled?: boolean;
		/** kompakt = Etappen-Karte, normal = Formular am Computer, gross = Formular am Handy. */
		groesse?: 'kompakt' | 'normal' | 'gross';
		/**
		 * Geleertes/unvollständiges Feld beim Verlassen als '' melden (Anlegen: „Startdatum fehlt",
		 * wie früher das native Feld). Ohne: das Feld springt beim Verlassen auf den gespeicherten
		 * Wert zurück (Etappe: kein Datenverlust, kein stiller Altwert hinter einer leeren Anzeige).
		 */
		leerMelden?: boolean;
		/**
		 * #2999: true, solange „Dieses Datum gibt es nicht." steht (bindbar) — Anlegen blendet
		 * damit „Startdatum fehlt" aus (keine Doppelmeldung).
		 */
		ungueltig?: boolean;
	}

	let { value = '', onchange, testid, ariaLabel, required = false, disabled = false, groesse = 'normal', leerMelden = false, ungueltig = $bindable(false) }: Props = $props();
	// #2999: eigener Zähler statt $props.id() — der teilt den Zähler mit bits-ui und würde alle
	// bits-Kennungen im (serverseitig gerenderten) Markup verschieben. Die Meldung gibt es nur im
	// Browser (ungueltig entsteht erst beim Tippen), daher keine Abgleichsfrage beim Hydrieren.
	const meldungId = `datum-feld-meldung-${++meldungZaehler}`;

	const intlLocale = $derived($locale === 'en' ? 'en-GB' : 'de-DE');

	function zuDatum(iso: string): DateValue | undefined {
		try {
			return iso ? parseDate(iso) : undefined;
		} catch {
			return undefined;
		}
	}
	const datum = $derived(zuDatum(value));

	// Melde-Regel (Zwischenstände beim Tippen nie nach außen): segmentFeldMeldung.ts. `aufbau`
	// baut die Segmente neu auf, wenn ein geleertes/unvollständiges Feld verlassen wird.
	// Ein fremder Wertwechsel (andere Etappe, Rücknahme nach gescheitertem Speichern) braucht keine
	// eigene Behandlung (Fix-Loop 2, per Mutation belegt): wer die Etappe wechselt, verlässt vorher
	// das Feld, und bei der Rücknahme setzt bits-ui den neuen Wert, den `iso === value` unten
	// verwirft — samt Offenem.
	let feld = $state<HTMLElement | null>(null);
	const zaehler = new TippZaehler();
	let aufbau = $state(0);
	const meldung = new SegmentFeldMeldung((iso) => onchange?.(iso));

	// Steht im Feld gerade ein vollständiges Datum? (Leeren und halbfertige Jahre 0002/0020 nicht.)
	let vollstaendig = untrack(() => !!datum);
	// Hat der Nutzer das Feld seit dem letzten Aufbau angefasst (Taste oder Wertänderung)?
	let beruehrt = false;

	function geaendert(neu: DateValue | undefined): void {
		// #2999: bits-ui meldet beim Neuaufbau nach der 8. Ziffer noch seinen (geklemmten) Stand.
		if (bautNeu) return;
		if (!neu || neu.year < 1000) {
			vollstaendig = false;
			// Leer erst beim Verlassen melden (siehe verlassen) — nie als Zwischenstand.
			if (leerMelden && value !== '') meldung.aendern('', true);
			// #2999 AC-10: ein zurückgehaltener Zwischenstand (Rücktaste „20" → „2") steht nicht mehr
			// im Feld und darf beim Verlassen nicht hinausgehen.
			else meldung.verwerfen();
			return;
		}
		vollstaendig = true;
		const iso = neu.toString().slice(0, 10);
		if (iso === value) {
			meldung.verwerfen();
			return;
		}
		// Erst nach dem Neuzeichnen melden: bits-ui räumt seine Tipp-Zwischenstände in einem Effekt
		// weg; ein synchron gemeldeter Wert liesse sie bei einem folgenden Etappenwechsel stehen.
		// #2999: solange ein Ziffernstrom läuft, bleibt der (evtl. von bits-ui geklemmte) Wert
		// zurück, wenn er dem Strom widerspricht; die 8. Ziffer verwirft ihn (`folge`).
		const nr = folge;
		void tick().then(() => {
			if (nr !== folge) return;
			// Nur ein Wert, der den fertig getippten Segmenten des Stroms widerspricht (geklemmt/
			// verrutscht), bleibt zurück; ein stimmiger geht wie bisher hinaus (DS-2).
			const zurueck = tipp.widerspricht(iso) || zaehler.unfertig(feld);
			if (!zurueck) ungueltig = false;
			meldung.aendern(iso, zurueck);
		});
	}

	// #2999 Tipp-Protokoll (datumTipp.ts): eigener Ziffernstrom vor bits-ui. Er beginnt nur im
	// ersten Segment (wer allein das Jahr ändert, tippt kein ganzes Datum).
	const tipp = new DatumTipp();
	let folge = 0;
	let bautNeu = false;
	const DATUM_TEILE = new Set(['day', 'month', 'year']);
	const MODIFIKATOREN = new Set(['Shift', 'Control', 'Alt', 'AltGraph', 'Meta', 'CapsLock']);

	function datumSegmente(): HTMLElement[] {
		if (!feld) return [];
		return Array.from(feld.querySelectorAll<HTMLElement>('[data-segment]')).filter((el) => DATUM_TEILE.has(el.getAttribute('data-segment') ?? ''));
	}

	function taste(e: KeyboardEvent): void {
		beruehrt = true;
		// Vor dem Zählen: ist das Segment schon angefangen (Rücktaste „20" → „2")? Dann ergänzt die
		// nächste Ziffer bei bits-ui das Segment und ist kein Strombeginn.
		const angefangen = zaehler.unfertig(feld);
		zaehler.taste(e);
		if (MODIFIKATOREN.has(e.key)) return;
		// Tastenkürzel (Strg+V, Strg+A …) sind keine getippten Ziffern: Strom neu, bits-ui waltet.
		if (e.ctrlKey || e.altKey || e.metaKey) {
			tipp.zuruecksetzen();
			return;
		}
		const segmente = datumSegmente();
		const ziel = e.target as HTMLElement | null;
		if (!ziel || !segmente.includes(ziel)) {
			tipp.zuruecksetzen();
			return;
		}
		if (!tipp.laeuft && /^\d$/.test(e.key) && (ziel !== segmente[0] || (angefangen && !ziel.hasAttribute('data-placeholder')))) return;
		const reihenfolge = segmente.map((el) => el.getAttribute('data-segment') as Segment);
		// Die Strom-beginnende Ziffer merkt sich den Modellwert (Rücknahme bei ungültigem Ende, F005).
		const ergebnis = tipp.taste(e.key, reihenfolge, value);
		if (!ergebnis) return;
		// Die 8. Ziffer legt die Absicht fest: bits-ui bekommt sie nicht mehr, Zurückgehaltenes verfällt.
		e.preventDefault();
		e.stopPropagation();
		folge += 1;
		meldung.verwerfen();
		if (ergebnis.ok) {
			ungueltig = false;
			if (ergebnis.iso !== value) onchange?.(ergebnis.iso);
		} else {
			ungueltig = true;
			// AC-5: ein stimmiger Zwischenstand dieses Stroms (DS-2) ging schon hinaus — zurücknehmen.
			const ruecknahme = ruecknahmeNachUngueltig(tipp.wertVorStrom, value);
			if (ruecknahme !== null) onchange?.(ruecknahme);
		}
		void neuAufbauen(ergebnis.ok ? 'letztes' : 'erstes');
	}

	/** Feld zeigt den Modellwert (nach gültiger Eingabe den gemeldeten), Fokus bleibt im Feld. */
	async function neuAufbauen(fokus: 'erstes' | 'letztes'): Promise<void> {
		bautNeu = true;
		await tick();
		vollstaendig = !!datum;
		beruehrt = false;
		aufbau += 1;
		await tick();
		const segmente = datumSegmente();
		segmente[fokus === 'erstes' ? 0 : segmente.length - 1]?.focus();
		bautNeu = false;
	}

	function fokusRein(e: FocusEvent): void {
		zaehler.fokus(e);
		// Fokus von außen ins Feld: neuer Strom (bits-ui springt beim Tippen selbst weiter).
		if (!feld?.contains(e.relatedTarget as Node | null)) tipp.zuruecksetzen();
	}

	function verlassen(e: FocusEvent): void {
		const ziel = e.relatedTarget as Element | null;
		// In das Feld selbst oder in den eigenen Kalender (Portal) ist kein Verlassen.
		if (bautNeu || feld?.contains(ziel) || ziel?.closest?.('[data-slot="datum-feld-kalender"]')) return;
		tipp.zuruecksetzen();
		if (meldung.offen) ungueltig = false;
		meldung.abschliessen();
		// Geleert oder Jahr angefangen (bits-ui meldet dann keinen bzw. einen Jahr-<1000-Wert, also
		// `vollstaendig = false`). Nur was der Nutzer angefasst hat, wird zurückgesetzt (sonst
		// schlösse ein leeres, unberührtes Feld beim Öffnen des Kalenders seine eigene Liste).
		if (beruehrt && !vollstaendig) {
			// Unvollständig/leer verlassen: nach der Meldung ('' bei leerMelden) zeigt das Feld den
			// Modellwert — Etappe: das gespeicherte Datum, Anlegen: leer mit „Startdatum fehlt".
			void tick().then(() => {
				vollstaendig = !!datum;
				beruehrt = false;
				aufbau += 1;
			});
		}
	}
</script>

<div class="datum-feld" data-slot="datum-feld" data-groesse={groesse} data-testid={testid} bind:this={feld} onfocusout={verlassen} onkeydowncapture={taste} onfocusincapture={fokusRein} onpointerdowncapture={() => tipp.zuruecksetzen()}>
	{#key aufbau}
	<DatePicker.Root
		value={datum}
		onValueChange={geaendert}
		locale={intlLocale}
		weekStartsOn={1}
		weekdayFormat="short"
		granularity="day"
		fixedWeeks
		{required}
		{disabled}
	>
		<div class="rahmen">
			<DatePicker.Input data-slot="datum-feld-eingabe" aria-label={ariaLabel} aria-describedby={ungueltig ? meldungId : undefined}>
				{#snippet children({ segments })}
					{#each segments as { part, value: teil }, i (i)}
						<DatePicker.Segment {part} aria-describedby={ungueltig ? meldungId : undefined}>{teil}</DatePicker.Segment>
					{/each}
				{/snippet}
			</DatePicker.Input>
			<DatePicker.Trigger data-slot="datum-feld-kalender-knopf" aria-label={$t('bausteine.datum.kalender_oeffnen')}>
				<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></svg>
			</DatePicker.Trigger>
		</div>
		<DatePicker.Portal>
			<DatePicker.Content data-slot="datum-feld-kalender" sideOffset={6} align="start">
				<DatePicker.Calendar>
					{#snippet children({ months, weekdays })}
						<DatePicker.Header data-slot="datum-feld-kopf">
							<DatePicker.PrevButton data-slot="datum-feld-zurueck" aria-label={$t('bausteine.datum.voriger_monat')}>‹</DatePicker.PrevButton>
							<DatePicker.Heading data-slot="datum-feld-titel" />
							<DatePicker.NextButton data-slot="datum-feld-weiter" aria-label={$t('bausteine.datum.naechster_monat')}>›</DatePicker.NextButton>
						</DatePicker.Header>
						{#each months as monat (monat.value.toString())}
							<DatePicker.Grid data-slot="datum-feld-raster">
								<DatePicker.GridHead>
									<DatePicker.GridRow>
										{#each weekdays as wtag, i (i)}
											<DatePicker.HeadCell data-slot="datum-feld-wochentag">{wtag}</DatePicker.HeadCell>
										{/each}
									</DatePicker.GridRow>
								</DatePicker.GridHead>
								<DatePicker.GridBody>
									{#each monat.weeks as woche, w (w)}
										<DatePicker.GridRow>
											{#each woche as tag (tag.toString())}
												<DatePicker.Cell date={tag} month={monat.value} data-slot="datum-feld-zelle">
													<DatePicker.Day data-slot="datum-feld-tag" />
												</DatePicker.Cell>
											{/each}
										</DatePicker.GridRow>
									{/each}
								</DatePicker.GridBody>
							</DatePicker.Grid>
						{/each}
					{/snippet}
				</DatePicker.Calendar>
			</DatePicker.Content>
		</DatePicker.Portal>
	</DatePicker.Root>
	{/key}{#if ungueltig}<div class="datum-meldung" data-slot="datum-feld-meldung" id={meldungId} role="alert">{$t('bausteine.datum.ungueltig')}</div>{/if}
</div>

<style>
	.datum-feld {
		display: inline-flex;
		min-width: 0;
		/* #2999: Bezugsrahmen für die Meldung darunter. */
		position: relative;
	}
	/* #2999: Meldung direkt unter dem Feld, ohne Zusatzhülle und ohne Zeilen-Layouts (Etappe)
	   zu verschieben — sie liegt über dem Folgeinhalt, solange sie steht. */
	.datum-meldung {
		position: absolute;
		top: 100%;
		left: 0;
		z-index: 1;
		margin-top: var(--g-s-1);
		padding: 0 var(--g-s-1);
		background: var(--g-card);
		font-size: var(--g-text-xs);
		line-height: 1.4;
		white-space: nowrap;
		color: var(--g-danger-fg);
	}
	.datum-feld[data-groesse='normal'],
	.datum-feld[data-groesse='gross'] {
		display: flex;
		width: 100%;
	}
	.rahmen {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		width: 100%;
		box-sizing: border-box;
		padding: 0 4px 0 12px;
		border: 1.5px solid var(--g-rule);
		border-radius: var(--g-r-2);
		background: var(--g-card);
		color: var(--g-ink);
		font-family: var(--g-font-mono);
		font-feature-settings: 'tnum', 'zero';
		font-size: 14px;
		min-height: 40px;
	}
	[data-groesse='kompakt'] .rahmen {
		padding: 0 0 0 4px;
		border: none;
		background: transparent;
		font-size: 13px;
		min-height: 28px;
	}
	[data-groesse='gross'] .rahmen {
		border-width: 1px;
		border-radius: var(--g-r-3);
		min-height: 48px;
		font-size: 16px;
	}
	.rahmen:focus-within {
		border-color: var(--g-ink);
	}
	.datum-feld :global([data-slot='datum-feld-eingabe']) {
		display: inline-flex;
		align-items: center;
		flex: 1;
		min-width: 0;
		white-space: nowrap;
	}
	.datum-feld :global([data-segment]) {
		padding: 1px 1px;
		border-radius: 3px;
		outline: none;
	}
	.datum-feld :global([data-segment]:focus) {
		background: var(--g-ink);
		color: var(--g-paper);
	}
	.datum-feld :global([data-segment][data-placeholder]) {
		color: var(--g-ink-3);
	}
	.datum-feld :global([data-slot='datum-feld-kalender-knopf']) {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		width: 32px;
		height: 32px;
		border: none;
		border-radius: var(--g-r-2);
		background: transparent;
		color: var(--g-ink-2);
		cursor: pointer;
	}
	.datum-feld :global([data-slot='datum-feld-kalender-knopf']:hover) {
		background: var(--g-paper-deep);
	}
	.datum-feld :global([data-slot='datum-feld-kalender-knopf']:focus-visible) {
		outline: 2px solid var(--g-accent);
		outline-offset: 1px;
	}
	/* #2601/R5: am Handy kein iOS-Auto-Zoom (16 px) und Kalender-Knopf als 44er-Tippfläche. */
	@media (max-width: 899px), (pointer: coarse) {
		.datum-feld[data-groesse] .rahmen {
			font-size: 16px;
		}
		.datum-feld :global([data-slot='datum-feld-kalender-knopf']) {
			width: 44px;
			height: 44px;
		}
		/* #2601 Runde 2 (AC-7/AC-8): Tag/Monat als ≥ 24×24-px-Tippziel — echte Breite statt
		   ::after-Fläche (Nachbarsegmente würden sich sonst überlappen). Jahr bleibt unverändert. */
		.datum-feld :global(:is([data-segment='day'], [data-segment='month'])) {
			display: inline-block;
			box-sizing: border-box;
			min-width: var(--g-s-6);
			min-height: var(--g-s-6);
			text-align: center;
		}
	}

	/* Kalender im Portal (außerhalb des Bausteins im DOM) — daher global über data-slot. */
	:global([data-slot='datum-feld-kalender']) {
		z-index: 1000;
		padding: 12px;
		border: 1px solid var(--g-rule);
		border-radius: 8px;
		background: var(--g-card);
		color: var(--g-ink);
		box-shadow: var(--g-shadow-3);
		font-family: var(--g-font-sans);
		font-size: 13px;
	}
	:global([data-slot='datum-feld-kopf']) {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		margin-bottom: 8px;
	}
	:global([data-slot='datum-feld-titel']) {
		font-weight: 600;
	}
	:global([data-slot='datum-feld-zurueck']),
	:global([data-slot='datum-feld-weiter']) {
		width: 36px;
		height: 36px;
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-2);
		background: transparent;
		color: var(--g-ink);
		font-size: 18px;
		line-height: 1;
		cursor: pointer;
	}
	:global([data-slot='datum-feld-raster']) {
		border-collapse: collapse;
	}
	:global([data-slot='datum-feld-wochentag']) {
		width: 36px;
		padding-bottom: 4px;
		font-family: var(--g-font-mono);
		font-size: 11px;
		font-weight: 500;
		color: var(--g-ink-3);
		text-align: center;
	}
	:global([data-slot='datum-feld-zelle']) {
		padding: 1px;
		text-align: center;
	}
	:global([data-slot='datum-feld-tag']) {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 34px;
		height: 34px;
		border-radius: var(--g-r-2);
		font-family: var(--g-font-mono);
		font-feature-settings: 'tnum', 'zero';
		cursor: pointer;
	}
	:global([data-slot='datum-feld-tag']:hover) {
		background: var(--g-paper-deep);
	}
	:global([data-slot='datum-feld-tag'][data-today]) {
		box-shadow: inset 0 0 0 1px var(--g-accent);
	}
	:global([data-slot='datum-feld-tag'][data-selected]) {
		background: var(--g-ink);
		color: var(--g-paper);
	}
	:global([data-slot='datum-feld-tag'][data-outside-month]) {
		color: var(--g-ink-3);
	}
	:global([data-slot='datum-feld-tag']:focus-visible) {
		outline: 2px solid var(--g-accent);
		outline-offset: 1px;
	}
	@media (max-width: 899px), (pointer: coarse) {
		:global([data-slot='datum-feld-zurueck']),
		:global([data-slot='datum-feld-weiter']) {
			width: 44px;
			height: 44px;
		}
		:global([data-slot='datum-feld-wochentag']) {
			width: 44px;
		}
		:global([data-slot='datum-feld-tag']) {
			width: 42px;
			height: 42px;
		}
	}
</style>
