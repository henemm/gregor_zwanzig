<script lang="ts">
	// Issue #2657 (i18n F8) — Test-Huelle (nicht ausgeliefert): der geteilte
	// LayoutTab braucht ein `editor`-Snippet. Eingehaengt wird der geteilte
	// Ausgabe-Layout-Editor (OutputLayoutEditor) fuer den gewaehlten Kanal —
	// so traegt ein Render Eyebrow, Kanal-Umschalter, Reihenfolge/Spalten und
	// den Kappungs-Hinweis in EINEM Durchgang.
	import LayoutTab from '../LayoutTab.svelte';
	import OutputLayoutEditor from '../../OutputLayoutEditor.svelte';
	import type { ChannelId } from '../ltChannels';

	interface Props {
		context: 'route' | 'vergleich';
		channel: ChannelId;
		colCount: number;
		subjectLabel: string;
		hasLabelColumn: boolean;
		smsCharLimit?: number;
		catalog: Record<string, unknown[]>;
		buckets: { primary: string[]; secondary: string[]; off: string[] };
		templates?: { id: string; label: string; metrics: string[] }[];
		hideDetailBucket?: boolean;
	}
	let { context, channel, colCount, subjectLabel, hasLabelColumn, smsCharLimit, catalog, buckets, templates = [], hideDetailBucket = false }: Props = $props();
</script>

<LayoutTab {context} {channel} {colCount} {subjectLabel} {hasLabelColumn} {smsCharLimit}>
	{#snippet editor({ channel: ch })}
		<OutputLayoutEditor
			catalog={catalog as never}
			{buckets}
			friendlyMap={{}}
			channel={ch}
			{templates}
			{hideDetailBucket}
		/>
	{/snippet}
</LayoutTab>
