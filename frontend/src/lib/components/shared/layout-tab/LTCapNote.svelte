<script lang="ts">
	// LTCapNote — Issue #1232 Scheibe 3a: geteilter Kappungs-Hinweis unter der
	// Reihenfolge/dem Bucket-Editor des LayoutTab-Organism. 1:1-Text-Logik aus
	// claude-code-handoff/current/jsx/layout-tab.jsx (LT_CapNote).
	//
	// Spec: docs/specs/modules/layout_tab_vergleich.md (Implementation Details §1)

	import { LT_CH_BY_ID, type ChannelId } from './ltChannels';

	interface Props {
		channel: ChannelId;
		colCount: number;
		subject: string;
		dense?: boolean;
	}
	let { channel, colCount, subject, dense = false }: Props = $props();

	const ch = $derived(LT_CH_BY_ID[channel]);
	const warn = $derived(ch.max !== Infinity && ch.max !== 0 && colCount > ch.max);
	const text = $derived.by(() => {
		if (ch.max === Infinity) return 'Email zeigt alles · keine Begrenzung';
		if (ch.max === 0) return 'SMS hat keine Tabelle — nur Fließtext, entscheidungskritische Werte';
		const fits = colCount <= ch.max;
		const fitText = fits ? `passt (max ${ch.max})` : `zu breit — max ${ch.max}, weiter vorne = sicherer`;
		return `${ch.label}: ${colCount} Spalten (Label + ${subject}) · ${fitText}`;
	});
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
