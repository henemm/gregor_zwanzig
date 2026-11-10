<script lang="ts">
	// Issue #2881 Lieferung B (R2, ADR-0111): Uhrzeitfeld als Design-System-Baustein statt
	// <input type="time"> — bits-ui TimeField, Segmente Stunde/Minute, immer 24 h (beide Sprachen,
	// wie fmtTime). Wert nach außen unverändert als String `HH:MM`.
	// Von Trip und Vergleich nutzbar (CLAUDE.md Trip/Ortsvergleich-Teilung).
	// Spec: docs/specs/modules/rework_2881_design_system_bereinigung.md (AC-2, AC-3)
	import { tick, untrack } from 'svelte';
	import { TimeField } from 'bits-ui';
	import { SegmentFeldMeldung, TippZaehler, segmenteUnvollstaendig } from './segmentFeldMeldung.ts';
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

	// Zwischenstände beim Tippen gehen nie nach außen (wie DatumFeld, Regel in segmentFeldMeldung.ts);
	// `aufbau` baut die Segmente neu auf, wenn ein geleertes/unvollständiges Feld verlassen wird.
	// Ein fremder Wertwechsel (andere Etappe, Rücknahme) braucht keine eigene Behandlung (Fix-Loop 2,
	// per Mutation belegt, wie DatumFeld).
	let feld = $state<HTMLElement | null>(null);
	const zaehler = new TippZaehler();
	let aufbau = $state(0);
	const meldung = new SegmentFeldMeldung((hhmm) => onchange?.(hhmm));

	// Steht im Feld gerade eine vollständige Uhrzeit?
	let vollstaendig = untrack(() => !!zeit);
	// Hat der Nutzer das Feld seit dem letzten Aufbau angefasst (Taste oder Wertänderung)?
	let beruehrt = false;

	function geaendert(neu: Time | undefined): void {
		if (!neu) {
			vollstaendig = false;
			// Leer wird erst beim Verlassen gemeldet (`geleert` dort; Etappen-Startzeit fällt dann auf
			// 08:00 zurück, #675 AC-5) — bits-ui meldet das Leeren der Stunde ohnehin nicht als leeren Wert.
			meldung.verwerfen();
			return;
		}
		vollstaendig = true;
		const hhmm = `${zwei(neu.hour)}:${zwei(neu.minute)}`;
		if (hhmm === value) {
			meldung.verwerfen();
			return;
		}
		// Anders als im DatumFeld sofort: das Nachmelden nach dem Neuzeichnen ist hier wirkungslos
		// (Fix-Loop 2, Mutation ohne Befund im Etappenwechsel).
		meldung.aendern(hhmm, zaehler.unfertig(feld));
	}

	function verlassen(e: FocusEvent): void {
		if (feld?.contains(e.relatedTarget as Node | null)) return;
		const hatteOffen = meldung.offen;
		meldung.abschliessen();
		// Geleert ohne Meldung von bits-ui (Stunde „––"): zählt wie leer.
		const geleert = beruehrt && !hatteOffen && segmenteUnvollstaendig(feld);
		if (geleert && leerMelden && value !== '') meldung.aendern('', false);
		// Nur was der Nutzer angefasst hat, wird zurückgesetzt (sonst schlösse ein leeres,
		// unberührtes Feld beim Öffnen des Kalenders seine eigene Liste).
		if (beruehrt && (!vollstaendig || geleert)) {
			// Unvollständig/leer verlassen: nach der Meldung zeigt das Feld den Modellwert (Etappe:
			// gespeicherte Zeit bzw. 08:00) — nie eine leere Anzeige vor einem stillen Altwert.
			void tick().then(() => {
				vollstaendig = !!zeit;
				beruehrt = false;
				aufbau += 1;
			});
		}
	}
</script>

<div class="uhrzeit-feld" data-slot="uhrzeit-feld" data-groesse={groesse} data-testid={testid} bind:this={feld} onfocusout={verlassen} onkeydowncapture={(e) => { beruehrt = true; zaehler.taste(e); }} onfocusincapture={zaehler.fokus}>
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
