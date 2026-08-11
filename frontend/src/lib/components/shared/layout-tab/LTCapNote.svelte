<script lang="ts">
	// LTCapNote — Issue #1232 Scheibe 3a: geteilter Kappungs-Hinweis unter der
	// Reihenfolge/dem Bucket-Editor des LayoutTab-Organism.
	//
	// Issue #1719 Scheibe S3 (AC-4/AC-5): Text-/Grenzwert-Logik nach
	// ltChannels.ts::ltCapNoteText ausgelagert (reine Funktion, testbar ohne
	// Svelte-Renderharness) — keine Wertung mehr, SMS traegt eine Zeichen-
	// statt einer Spaltengrenze.
	//
	// Spec: docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md (Abschnitt 5, AC-5)

	import { ltLimitForChannel, ltCapNoteText, SMS_TRIP_CHAR_LIMIT, type ChannelId } from './ltChannels';

	interface Props {
		channel: ChannelId;
		colCount: number;
		subject: string;
		dense?: boolean;
		/**
		 * Fresh-Eyes-Fund #1232-3b: `colCount` zählt im vergleich-Kontext Orte
		 * PLUS eine Label-Spalte (Orte-als-Spalten-Vorschau) — im route-Kontext
		 * zählt `colCount` dagegen reine Metriken (die Trip-Kappung in
		 * `WeatherV2Reihenfolge` zählt ausschließlich Metriken, keine
		 * Label-Spalte). Default `true` erhält den bisherigen vergleich-Wortlaut
		 * unverändert; route übergibt `false`.
		 */
		hasLabelColumn?: boolean;
		/** Issue #1719 S3 Abschnitt 5: der SMS-Zeichenwert kommt vom AUFRUFER
		 *  (Trip 160 / Vergleich 153) — Default ist der Trip-Wert, da diese
		 *  Komponente heute nur ueber LayoutTab im route-Kontext eingebettet ist. */
		smsCharLimit?: number;
	}
	let {
		channel,
		colCount,
		subject,
		dense = false,
		hasLabelColumn = true,
		smsCharLimit = SMS_TRIP_CHAR_LIMIT
	}: Props = $props();

	const limit = $derived(ltLimitForChannel(channel, smsCharLimit));
	const warn = $derived(limit.kind === 'columns' && colCount > limit.value);
	const text = $derived(ltCapNoteText({ channel, limit, colCount, subject, hasLabelColumn }));
</script>

<div class="lt-cap-note mono" class:warn class:dense data-testid="lt-cap-note">
	{text}
</div>

<style>
	.lt-cap-note {
		margin-top: 10px;
		font-size: 11px;
		color: var(--g-ink-4);
		letter-spacing: 0.03em;
		line-height: 1.5;
	}
	.lt-cap-note.dense {
		margin-top: 8px;
		font-size: 10.5px;
	}
	.lt-cap-note.warn {
		color: var(--g-warn);
	}
</style>
