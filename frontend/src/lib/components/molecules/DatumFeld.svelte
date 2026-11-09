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
	import { SegmentFeldMeldung, tipptIn } from './segmentFeldMeldung.ts';
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
	}

	let { value = '', onchange, testid, ariaLabel, required = false, disabled = false, groesse = 'normal' }: Props = $props();

	const intlLocale = $derived($locale === 'en' ? 'en-GB' : 'de-DE');

	function zuDatum(iso: string): DateValue | undefined {
		try {
			return iso ? parseDate(iso) : undefined;
		} catch {
			return undefined;
		}
	}
	const datum = $derived(zuDatum(value));

	// Ein FREMDER Wertwechsel (z. B. andere Etappe gewählt) baut die Segmente neu auf: bits-ui hält
	// sonst die zuletzt getippten Segmente fest und schreibt sie in den neuen Wert zurück. Die eigene
	// Meldung lässt das Feld stehen — sonst ginge der Fokus mitten im Tippen verloren.
	// Melde-Regel (Zwischenstände beim Tippen nie nach außen): segmentFeldMeldung.ts.
	let feld = $state<HTMLElement | null>(null);
	let eigen: string | null = null;
	let letzter = untrack(() => value);
	let aufbau = $state(0);
	const meldung = new SegmentFeldMeldung((iso) => {
		eigen = iso;
		onchange?.(iso);
	});
	$effect.pre(() => {
		const v = value;
		untrack(() => {
			if (v !== letzter && v !== eigen) {
				meldung.sperren();
				aufbau += 1;
				void tick().then(() => meldung.freigeben());
			}
			if (v === eigen) eigen = null;
			letzter = v;
		});
	});
	$effect(() => () => meldung.verwerfen());

	function geaendert(neu: DateValue | undefined): void {
		// Leeren und halbfertige Jahre (beim Tippen 0002, 0020 …) werden nicht nach außen gegeben.
		if (!neu || neu.year < 1000) return;
		const iso = neu.toString().slice(0, 10);
		if (iso === value) {
			meldung.verwerfen();
			return;
		}
		meldung.aendern(iso, tipptIn(feld));
	}

	function verlassen(e: FocusEvent): void {
		if (!feld?.contains(e.relatedTarget as Node | null)) meldung.abschliessen();
	}
</script>

<div class="datum-feld" data-slot="datum-feld" data-groesse={groesse} data-testid={testid} bind:this={feld} onfocusout={verlassen}>
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
			<DatePicker.Input data-slot="datum-feld-eingabe" aria-label={ariaLabel}>
				{#snippet children({ segments })}
					{#each segments as { part, value: teil }, i (i)}
						<DatePicker.Segment {part}>{teil}</DatePicker.Segment>
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
	{/key}
</div>

<style>
	.datum-feld {
		display: inline-flex;
		min-width: 0;
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
	}

	/* Kalender im Portal (außerhalb des Bausteins im DOM) — daher global über data-slot. */
	:global([data-slot='datum-feld-kalender']) {
		z-index: 1000;
		padding: 12px;
		border: 1px solid var(--g-rule);
		border-radius: 8px;
		background: var(--g-card);
		color: var(--g-ink);
		box-shadow: 0 6px 20px rgba(26, 26, 24, 0.14);
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
