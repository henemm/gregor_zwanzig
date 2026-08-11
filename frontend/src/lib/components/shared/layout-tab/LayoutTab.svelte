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
	import { ltOverflowAcrossChannels, SMS_TRIP_CHAR_LIMIT, type ChannelId } from './ltChannels';

	interface Props {
		context: 'route' | 'vergleich';
		channel?: ChannelId;
		dense?: boolean;
		/** Aufrufer liefert die kontextspezifische Zählung (z. B. Orte+Label). */
		colCount: number;
		/** z. B. "4 Orte" (vergleich) — Metriken (route, Scheibe 3b). */
		subjectLabel: string;
		editor: Snippet<[{ channel: ChannelId }]>;
	}
	let {
		context,
		channel = $bindable('email'),
		dense = false,
		colCount,
		subjectLabel,
		editor
	}: Props = $props();

	// Issue #1719 S3 Abschnitt 5: der SMS-Zeichenwert kommt vom AUFRUFER, nicht
	// aus einer geteilten Konstante — LayoutTab kennt nur den Trip-Pfad (160),
	// der Vergleichspfad (153) hat heute keine Einbettung ueber diesen
	// Organism (Kontext-Dokument Abschnitt 10.2: der Vergleichs-Layout-Reiter
	// ist seit #1360 aufgeloest).
	const overflow = $derived(ltOverflowAcrossChannels(colCount, SMS_TRIP_CHAR_LIMIT));
</script>

<div class="layout-tab" class:dense data-testid="layout-tab" data-context={context}>
	<div class="lt-eyebrow mono">Kanal · Auswahl &amp; Kappung</div>
	<LTChannelPicker bind:channel {overflow} {dense} />
	{@render editor({ channel })}
	<!-- Fresh-Eyes-Fund #1232-3b: hasLabelColumn=true nur im vergleich-Kontext
	     (Orte-als-Spalten-Vorschau zählt eine Label-Spalte mit); route zählt
	     reine Metriken (siehe LTCapNote-Prop-Kommentar). -->
	<LTCapNote {channel} {colCount} subject={subjectLabel} {dense} hasLabelColumn={context === 'vergleich'} />
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
