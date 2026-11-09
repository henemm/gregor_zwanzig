<script lang="ts">
	// Issue #2881 Lieferung B (R2, ADR-0111): Uhrzeitfeld als Design-System-Baustein statt
	// <input type="time"> — bits-ui TimeField, Segmente Stunde/Minute, immer 24 h (beide Sprachen,
	// wie fmtTime). Wert nach außen unverändert als String `HH:MM`.
	// Von Trip und Vergleich nutzbar (CLAUDE.md Trip/Ortsvergleich-Teilung).
	// Spec: docs/specs/modules/rework_2881_design_system_bereinigung.md (AC-2, AC-3)
	import { tick, untrack } from 'svelte';
	import { TimeField } from 'bits-ui';
	import { SegmentFeldMeldung, tipptIn } from './segmentFeldMeldung.ts';
	import { Time } from '@internationalized/date';
	import { locale } from '$lib/i18n';

	interface Props {
		/** `HH:MM` (Sekunden werden ignoriert) oder leer. */
		value?: string;
		onchange?: (hhmm: string) => void;
		testid?: string;
		ariaLabel?: string;
		disabled?: boolean;
		/** kompakt = Etappen-Karte, normal = Formular. */
		groesse?: 'kompakt' | 'normal';
		/** Geleertes Feld als '' melden (Etappen-Startzeit: zurück auf den Standard, #675 AC-5). */
		leerMelden?: boolean;
	}

	let { value = '', onchange, testid, ariaLabel, disabled = false, groesse = 'normal', leerMelden = false }: Props = $props();

	const intlLocale = $derived($locale === 'en' ? 'en-GB' : 'de-DE');
	const zwei = (n: number) => String(n).padStart(2, '0');

	const zeit = $derived.by(() => {
		const m = /^(\d{1,2}):(\d{2})/.exec(value ?? '');
		return m ? new Time(Number(m[1]), Number(m[2])) : undefined;
	});

	// Fremder Wertwechsel baut die Segmente neu auf, die eigene Meldung nicht; Zwischenstände beim
	// Tippen gehen nie nach außen (wie DatumFeld, Regel in segmentFeldMeldung.ts).
	let feld = $state<HTMLElement | null>(null);
	let eigen: string | null = null;
	let letzter = untrack(() => value);
	let aufbau = $state(0);
	const meldung = new SegmentFeldMeldung((hhmm) => {
		eigen = hhmm;
		onchange?.(hhmm);
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

	function geaendert(neu: Time | undefined): void {
		if (!neu) {
			if (leerMelden) meldung.aendern('', tipptIn(feld));
			return;
		}
		const hhmm = `${zwei(neu.hour)}:${zwei(neu.minute)}`;
		if (hhmm === value) {
			meldung.verwerfen();
			return;
		}
		meldung.aendern(hhmm, tipptIn(feld));
	}

	function verlassen(e: FocusEvent): void {
		if (!feld?.contains(e.relatedTarget as Node | null)) meldung.abschliessen();
	}
</script>

<div class="uhrzeit-feld" data-slot="uhrzeit-feld" data-groesse={groesse} data-testid={testid} bind:this={feld} onfocusout={verlassen}>
	{#key aufbau}
	<TimeField.Root value={zeit} onValueChange={(v) => geaendert(v as Time | undefined)} hourCycle={24} granularity="minute" locale={intlLocale} {disabled}>
		<TimeField.Input data-slot="uhrzeit-feld-eingabe" aria-label={ariaLabel}>
			{#snippet children({ segments })}
				{#each segments as { part, value: teil }, i (i)}
					<TimeField.Segment {part}>{teil}</TimeField.Segment>
				{/each}
			{/snippet}
		</TimeField.Input>
	</TimeField.Root>
	{/key}
</div>

<style>
	.uhrzeit-feld {
		display: inline-flex;
		align-items: center;
		box-sizing: border-box;
		padding: 0 12px;
		border: 1.5px solid var(--g-rule);
		border-radius: var(--g-r-2);
		background: var(--g-card);
		color: var(--g-ink);
		font-family: var(--g-font-mono);
		font-feature-settings: 'tnum', 'zero';
		font-size: 14px;
		min-height: 40px;
	}
	.uhrzeit-feld[data-groesse='kompakt'] {
		padding: 0 4px;
		border: none;
		background: transparent;
		font-size: 13px;
		min-height: 28px;
	}
	.uhrzeit-feld:focus-within {
		border-color: var(--g-ink);
	}
	.uhrzeit-feld :global([data-slot='uhrzeit-feld-eingabe']) {
		display: inline-flex;
		align-items: center;
		white-space: nowrap;
	}
	.uhrzeit-feld :global([data-segment]) {
		padding: 1px 1px;
		border-radius: 3px;
		outline: none;
	}
	.uhrzeit-feld :global([data-segment]:focus) {
		background: var(--g-ink);
		color: var(--g-paper);
	}
	.uhrzeit-feld :global([data-segment][data-placeholder]) {
		color: var(--g-ink-3);
	}
	/* #2601: am Handy kein iOS-Auto-Zoom (16 px). */
	@media (max-width: 899px), (pointer: coarse) {
		.uhrzeit-feld[data-groesse] {
			font-size: 16px;
		}
	}
</style>
