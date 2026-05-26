<script lang="ts" module>
	export type MIconKind =
		| 'menu' | 'back' | 'close' | 'plus' | 'search' | 'bell' | 'more'
		| 'filter' | 'edit' | 'share' | 'settings' | 'check' | 'chevron'
		| 'chevron-down' | 'chevron-up' | 'drag' | 'trash' | 'map' | 'list'
		| 'external' | 'send';
</script>

<script lang="ts">
	// Issue #373 — MIcon (kanonisch aus mobile-shell.jsx, Svelte 5).
	//
	// Inline-SVG-Iconsatz fuer die Mobile-Schicht. Token-basierte Farbe.
	// Unbekanntes kind -> leerer Platzhalter (kein Crash).
	//
	// Spec: docs/specs/modules/issue_373_mobile.md

	interface Props {
		kind: MIconKind | string;
		size?: number;
		color?: string;
	}

	let { kind, size = 22, color = 'var(--g-ink)' }: Props = $props();
</script>

{#if kind === 'menu' || kind === 'list'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M4 7h16M4 12h16M4 17h16" />
	</svg>
{:else if kind === 'back'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M15 5l-7 7 7 7" />
	</svg>
{:else if kind === 'close'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M6 6l12 12M18 6l-12 12" />
	</svg>
{:else if kind === 'plus'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M12 5v14M5 12h14" />
	</svg>
{:else if kind === 'search'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" />
	</svg>
{:else if kind === 'bell'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10 21a2 2 0 0 0 4 0" />
	</svg>
{:else if kind === 'more'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
		<circle cx="5" cy="12" r="1.7" /><circle cx="12" cy="12" r="1.7" /><circle cx="19" cy="12" r="1.7" />
	</svg>
{:else if kind === 'filter'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M4 6h16M7 12h10M10 18h4" />
	</svg>
{:else if kind === 'edit'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M14 4l6 6L9 21H3v-6z" />
	</svg>
{:else if kind === 'share'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M12 3v13M8 7l4-4 4 4M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" />
	</svg>
{:else if kind === 'settings'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.6 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 4.7 9a1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1" />
	</svg>
{:else if kind === 'check'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M5 12l5 5 9-11" />
	</svg>
{:else if kind === 'chevron'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M9 6l6 6-6 6" />
	</svg>
{:else if kind === 'chevron-down'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M6 9l6 6 6-6" />
	</svg>
{:else if kind === 'chevron-up'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M6 15l6-6 6 6" />
	</svg>
{:else if kind === 'drag'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
		<circle cx="9" cy="6" r="1.6" /><circle cx="15" cy="6" r="1.6" /><circle cx="9" cy="12" r="1.6" /><circle cx="15" cy="12" r="1.6" /><circle cx="9" cy="18" r="1.6" /><circle cx="15" cy="18" r="1.6" />
	</svg>
{:else if kind === 'trash'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M4 7h16M9 7V4h6v3M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13" />
	</svg>
{:else if kind === 'map'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M9 4l-6 2v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14" />
	</svg>
{:else if kind === 'external'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M14 4h6v6M20 4l-9 9M10 6H5a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5" />
	</svg>
{:else if kind === 'send'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M3 11l18-8-7 18-3-7-8-3z" />
	</svg>
{:else}
	<span style:width="{size}px" style:height="{size}px" style:display="inline-block"></span>
{/if}
