<script lang="ts">
	interface Props {
		kind: 'email' | 'signal' | 'telegram' | 'sms';
	}
	let { kind }: Props = $props();

	const icons: Record<string, string> = {
		email: '✉',
		signal: '▲',
		telegram: '✈',
		sms: '·'
	};
</script>

<span
	style="
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 18px;
		height: 18px;
		background: var(--g-paper-deep);
		border-radius: 3px;
		font-size: 10px;
		font-family: var(--g-font-mono, ui-monospace, monospace);
	"
	title={kind}
>
	{icons[kind] ?? '?'}
</span>
