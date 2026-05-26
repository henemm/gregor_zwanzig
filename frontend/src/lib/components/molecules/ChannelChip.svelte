<script lang="ts" module>
	// Einheitliches Mono-Glyph pro Kanal (interner Helper, exportiert fuer Reuse).
	export function channelGlyph(kind: string): string {
		const k = String(kind).toLowerCase();
		if (k.startsWith('email')) return '✉'; // ✉
		if (k.startsWith('signal')) return '▲'; // ▲
		if (k.startsWith('telegram')) return '✈'; // ✈
		if (k.startsWith('sms')) return '✱'; // ✱
		return '·'; // ·
	}
</script>

<script lang="ts">
	// Issue #372 — ChannelChip-Molecule (kanonisch aus molecules.jsx, Svelte 5).
	//
	// Kanal-Indikator. Zwei Layouts:
	//   default        — Pill mit Glyph + Text (Desktop, in Briefing-Listen)
	//   compact=true   — 24×24 Tile mit Glyph allein (Mobile, in Listen)
	//
	// Spec: docs/specs/modules/issue_372_molecules.md (AC-1)

	interface Props {
		kind: string; // "Email" | "Signal" | "Telegram" | "SMS"
		active?: boolean;
		compact?: boolean;
		class?: string;
	}

	let { kind, active = true, compact = false, class: className = '' }: Props = $props();

	const opacity = $derived(active ? 1 : 0.5);
	const glyph = $derived(channelGlyph(kind));
</script>

{#if compact}
	<span
		class={className}
		style:font-family="var(--g-font-mono)"
		style:width="24px"
		style:height="24px"
		style:border-radius="4px"
		style:background="var(--g-paper-deep)"
		style:display="inline-flex"
		style:align-items="center"
		style:justify-content="center"
		style:font-size="12px"
		style:color="var(--g-ink-2)"
		style:opacity={opacity}
		style:flex-shrink="0"
	>{glyph}</span>
{:else}
	<span
		class={className}
		style:font-family="var(--g-font-mono)"
		style:display="inline-flex"
		style:align-items="center"
		style:gap="4px"
		style:font-size="11px"
		style:padding="2px 6px"
		style:border="1px solid var(--g-rule)"
		style:border-radius="var(--g-r-pill)"
		style:color="var(--g-ink-3)"
		style:opacity={opacity}
	>
		<span>{glyph}</span>
		<span style:text-transform="lowercase">{String(kind).toLowerCase()}</span>
	</span>
{/if}
