<script lang="ts">
	// LayoutTab — Issue #1232 Scheibe 3a/3b: der geteilte Layout-Organism
	// (Epic #1230, Phase 4 Editor-Konsolidierung). EIN Organism für Trip-Editor
	// (context="route", folgt Scheibe 3b) und Compare-Editor (context="vergleich").
	//
	// Reine Hülle: Kanal-Umschalter (LTChannelPicker) + Kappungs-Hinweis
	// (LTCapNote) + Zwei-Spalten-Shell — die eigentliche Editor-/Preview-Logik
	// kommt vollständig aus den Snippet-Props des Aufrufers. Zustandsarm und
	// save-frei (kein $effect, keine Persistenz, kein API-Call).
	//
	// Design-Quelle (1:1): claude-code-handoff/current/jsx/layout-tab.jsx
	// Spec: docs/specs/modules/layout_tab_vergleich.md (Implementation Details §2)

	import type { Snippet } from 'svelte';
	import LTChannelPicker from './LTChannelPicker.svelte';
	import LTCapNote from './LTCapNote.svelte';
	import { ltOverflow, LT_CH_BY_ID, type ChannelId } from './ltChannels';

	interface Props {
		context: 'route' | 'vergleich';
		channel?: ChannelId;
		dense?: boolean;
		/** Aufrufer liefert die kontextspezifische Zählung (z. B. Orte+Label). */
		colCount: number;
		/** z. B. "4 Orte" (vergleich) — Metriken (route, Scheibe 3b). */
		subjectLabel: string;
		editor: Snippet<[{ channel: ChannelId }]>;
		preview: Snippet<[{ channel: ChannelId }]>;
	}
	let {
		context,
		channel = $bindable('email'),
		dense = false,
		colCount,
		subjectLabel,
		editor,
		preview
	}: Props = $props();

	const overflow = $derived(ltOverflow(colCount));
</script>

<div class="layout-tab" class:dense data-testid="layout-tab" data-context={context}>
	<div class="lt-col lt-col-editor">
		<div class="lt-eyebrow mono">Kanal · Vorschau &amp; Kappung</div>
		<LTChannelPicker bind:channel {overflow} {dense} />
		{@render editor({ channel })}
		<!-- Fresh-Eyes-Fund #1232-3b: hasLabelColumn=true nur im vergleich-Kontext
		     (Orte-als-Spalten-Vorschau zählt eine Label-Spalte mit); route zählt
		     reine Metriken (siehe LTCapNote-Prop-Kommentar). -->
		<LTCapNote {channel} {colCount} subject={subjectLabel} {dense} hasLabelColumn={context === 'vergleich'} />
	</div>
	<div class="lt-col lt-col-preview">
		<div class="lt-eyebrow mono">So kommt es an · {LT_CH_BY_ID[channel].label}</div>
		{@render preview({ channel })}
	</div>
</div>

<style>
	.layout-tab {
		display: grid;
		grid-template-columns: minmax(380px, 1fr) minmax(380px, 1.1fr);
		gap: 32px;
		align-items: start;
	}
	.layout-tab.dense {
		display: flex;
		flex-direction: column;
		gap: 20px;
	}
	.lt-col {
		display: flex;
		flex-direction: column;
		gap: 10px;
		min-width: 0;
	}
	.lt-eyebrow {
		font-size: 10px;
		color: var(--g-ink-4);
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}
	@media (max-width: 899px) {
		.layout-tab {
			display: flex;
			flex-direction: column;
			gap: 20px;
		}
	}
</style>
