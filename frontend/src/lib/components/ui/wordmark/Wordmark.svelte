<script lang="ts">
	interface Props {
		size?: 'sm' | 'md' | 'lg';
		href?: string;
	}

	let { size = 'md', href = '/' }: Props = $props();
</script>

<a {href} aria-label="Gregor Zwanzig — Home" class="wordmark wordmark--{size}">
	<div class="wordmark__row">
		<span class="wordmark__gregor">gregor</span>
		<span class="wordmark__dot">.</span>
		<span class="wordmark__zwanzig">zwanzig</span>
	</div>
	{#if size !== 'sm'}
		<div class="wordmark__subtitle">v0.20 · wetter-briefing</div>
	{/if}
</a>

<style>
	.wordmark {
		display: inline-block;
		text-decoration: none;
	}

	.wordmark__row {
		font-family: var(--g-font-data);
		font-weight: 500;
		letter-spacing: 0.04em;
		color: var(--g-ink);
		display: flex;
		align-items: baseline;
		gap: 0;
	}

	.wordmark__dot { color: var(--g-ink-faint); }
	.wordmark__zwanzig { color: var(--g-accent); }

	.wordmark__subtitle {
		font-family: var(--g-font-data);
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--g-ink-faint);
		margin-top: 3px;
	}

	.wordmark--sm .wordmark__row { font-size: 14px; }

	.wordmark--md .wordmark__row { font-size: 18px; }
	.wordmark--md .wordmark__subtitle { font-size: 9px; }

	.wordmark--lg .wordmark__row { font-size: 24px; }
	.wordmark--lg .wordmark__subtitle { font-size: 10px; }
</style>
