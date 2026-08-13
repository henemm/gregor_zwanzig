<script lang="ts">
	// LayoutTab — Issue #1232 Scheibe 3a/3b: der geteilte Layout-Organism
	// (Epic #1230, Phase 4 Editor-Konsolidierung). EIN Organism für Trip-Editor
	// (context="route") und Compare-Editor (context="vergleich").
	//
	// Reine Hülle: Kanal-Umschalter (LTChannelPicker) + Kappungs-Hinweis
	// (LTCapNote) — die eigentliche Editor-Logik kommt vollständig aus dem
	// Snippet-Prop des Aufrufers. Zustandsarm und save-frei (kein $effect,
	// keine Persistenz, kein API-Call).
	//
	// Issue #1719 Scheibe S3 (PO-Entscheid): die Live-Vorschau "So kommt es
	// an" (zweite Spalte, `preview`-Snippet) ist ERSATZLOS entfernt — einzige
	// Einbettung war WeatherMetricsTab.svelte (context="route"), die eigene
	// Vorschau-Komponente (WeatherV2MailPreview.svelte) ist gelöscht. Der
	// Organism ist damit eine EIN-Spalten-Hülle, keine Zwei-Spalten-Shell mehr.
	//
	// Design-Quelle (1:1, vor S3): claude-code-handoff/current/jsx/layout-tab.jsx
	// Spec: docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md (Abschnitt 7, 10.5)

	import type { Snippet } from 'svelte';
	import LTChannelPicker from './LTChannelPicker.svelte';
	import LTCapNote from './LTCapNote.svelte';
	import {
		ltChannelsFor, ltOverflowAcrossChannels, SMS_TRIP_CHAR_LIMIT, type ChannelId
	} from './ltChannels';

	interface Props {
		context: 'route' | 'vergleich';
		channel?: ChannelId;
		dense?: boolean;
		/** Aufrufer liefert die kontextspezifische Zählung (z. B. Orte+Label). */
		colCount: number;
		/** z. B. "4 Orte" (vergleich) — Metriken (route, Scheibe 3b). */
		subjectLabel: string;
		/**
		 * Issue #1703 Scheibe 8 (Fix A, AC-S8-13): PFLICHT-Prop ohne Vorgabewert.
		 * Bis dahin wurde sie aus `context` abgeleitet (`context === 'vergleich'`)
		 * — ein Default, der fuer den damals einzigen Vergleichsfall (Orte als
		 * Spalten, Hub-Reiter „Layout") gebaut und seit dessen Aufloesung (#1360)
		 * ohne Konsumenten war. Die Uebersichts-Einbettung dieser Scheibe zaehlt
		 * Metriken als ZEILEN und braeuchte `false`; ein aus dem Kontext
		 * abgeleiteter Wert haette dort vom ersten Tag an eine falsche
		 * Kappungslinie behauptet. Die Zaehl-Einheit ist eine Eigenschaft des
		 * AUFRUFERS, nicht des Kontext-Strings.
		 */
		hasLabelColumn: boolean;
		/** Issue #1703 Scheibe 8 (Fix B, AC-S8-12): Zeichengrenze des SMS-Wegs
		 *  dieser Flaeche (Trip 160 / Vergleich 153). Speist Kanal-Badge,
		 *  Ueberlauf-Chip UND Kappungs-Hinweis aus EINER Zahl — vorher stand die
		 *  Trip-Konstante an allen drei Stellen fest verdrahtet. */
		smsCharLimit?: number;
		editor: Snippet<[{ channel: ChannelId }]>;
	}
	let {
		context,
		channel = $bindable('email'),
		dense = false,
		colCount,
		subjectLabel,
		hasLabelColumn,
		smsCharLimit = SMS_TRIP_CHAR_LIMIT,
		editor
	}: Props = $props();

	// Issue #1719 S3 Abschnitt 5: der SMS-Zeichenwert kommt vom AUFRUFER, nicht
	// aus einer geteilten Konstante (Trip 160 / Vergleich 153 / Alarm 140).
	const overflow = $derived(ltOverflowAcrossChannels(colCount, smsCharLimit));
	const channels = $derived(ltChannelsFor(smsCharLimit));
</script>

<div class="layout-tab" class:dense data-testid="layout-tab" data-context={context}>
	<div class="lt-eyebrow mono">Kanal · Auswahl &amp; Kappung</div>
	<LTChannelPicker bind:channel {overflow} {dense} {channels} />
	{@render editor({ channel })}
	<!-- Issue #1703 S8 (Fix A/B): Zaehl-Einheit UND SMS-Zeichengrenze kommen vom
	     Aufrufer — dieselbe Zahl, die oben schon Badge und Ueberlauf-Chip speist.
	     Vorher: hasLabelColumn aus `context` abgeleitet, smsCharLimit gar nicht
	     durchgereicht (LTCapNote fiel still auf den Trip-Default 160 zurueck). -->
	<LTCapNote {channel} {colCount} subject={subjectLabel} {dense} {hasLabelColumn} {smsCharLimit} />
</div>

<style>
	.layout-tab {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.lt-eyebrow {
		font-size: 10px;
		color: var(--g-ink-4);
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}
</style>
