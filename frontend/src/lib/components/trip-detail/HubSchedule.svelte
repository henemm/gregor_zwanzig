<script lang="ts">
	import { Eyebrow, Card, Switch, Btn } from '$lib/components/atoms';
	import ChannelDot from './ChannelDot.svelte';
	import type { Trip } from '$lib/types';

	interface Props {
		trip: Trip;
	}
	let { trip }: Props = $props();

	interface ScheduleCard {
		title: string;
		time: string;
		sub: string;
		channels: string[];
		on?: boolean;
		alert?: boolean;
	}

	const cards: ScheduleCard[] = [
		{
			title: 'Morgen-Briefing',
			time: '06:00',
			sub: 'Vor Etappenstart — alles für den Tag',
			channels: ['email', 'signal'],
			on: true
		},
		{
			title: 'Abend-Briefing',
			time: '18:00',
			sub: 'Nach Tagesende — Ausblick auf morgen',
			channels: ['email'],
			on: true
		},
		{
			title: 'Alert-Trigger',
			time: 'bei Δ / Schwellwert',
			sub: 'Sofort bei kritischer Änderung',
			channels: ['signal'],
			on: true,
			alert: true
		},
		{
			title: 'Mehrtages-Trend',
			time: 'So 18:00',
			sub: '3–7-Tage-Ausblick (optional)',
			channels: ['email']
		}
	];

	let switchStates = $state(cards.map((c) => c.on ?? false));

	function makeSwitchHandler(i: number) {
		return function doToggle(checked: boolean) {
			switchStates[i] = checked;
		};
	}
</script>

<div
	data-testid="hub-schedule"
	style="
		position: relative;
		padding: 32px 40px 60px;
		max-width: 1480px;
	"
>
	<Eyebrow style="margin-bottom: 6px;">Briefing-Zeitplan</Eyebrow>
	<h2
		style="
			font-size: 28px;
			font-weight: 600;
			letter-spacing: -0.02em;
			margin: 0 0 12px;
			color: var(--g-ink);
		"
	>
		Wann geht was an welchen Kanal?
	</h2>
	<p
		style="
			font-size: 14px;
			color: var(--g-ink-2);
			max-width: 720px;
			line-height: 1.55;
			margin-bottom: 24px;
		"
	>
		Drei Briefing-Typen, je eigener Zeitpunkt und eigene Kanäle. Gelesen werden sie im Kanal — die
		App schickt sie automatisch.
	</p>

	<div
		style="
			display: grid;
			grid-template-columns: 1fr 1fr;
			gap: 20px;
			max-width: 980px;
		"
	>
		{#each cards as card, i}
			<Card padding={18}>
				<div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px;">
					<div>
						<div style="font-size: 14px; font-weight: 600; color: var(--g-ink); margin-bottom: 4px;">
							{card.title}
						</div>
						<div style="font-size: 12px; color: var(--g-ink-3);">{card.sub}</div>
					</div>
					<Switch checked={switchStates[i]} onchange={makeSwitchHandler(i)} />
				</div>
				<div
					style="
						display: flex;
						align-items: center;
						justify-content: space-between;
						border-top: 1px solid var(--g-rule-soft);
						padding-top: 10px;
					"
				>
					<span
						style="
							font-family: var(--g-font-mono, ui-monospace, monospace);
							font-size: 11px;
							color: var(--g-ink-3);
						"
					>{card.time}</span>
					<div style="display: flex; gap: 4px;">
						{#each card.channels as ch}
							<ChannelDot kind={ch as 'email' | 'signal' | 'telegram' | 'sms'} />
						{/each}
					</div>
				</div>
			</Card>
		{/each}
	</div>
</div>
