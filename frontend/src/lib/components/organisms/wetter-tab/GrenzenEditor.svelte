<script lang="ts">
	// Issue #2794 S3a, Teil-PR 3: „Grenzen ändern" einer Zeile (AC-16, AC-17, AC-18).
	// Felder nur fuer die erlaubten Seiten (beidseitig, nur oben, nur unten); Gewitter waehlt
	// statt Zahlen die Farbe je Stufe (mittel: gelb · orange · rot, hoch: orange · rot).
	// Die Eingaben gehen als Entwurf an den Reiter; gespeichert wird erst bei „Fertig".
	import type { Ampel, AmpelMetrik } from '$lib/types';
	// #2913 Teil 2 (K-6): Eingaben als Atom Input mit Ampel-Unterkante der Feldfarbe; Gewitter-Farben
	// als Segmented mit Farbpunkt.
	import { Input, Segmented } from '$lib/components/atoms';
	import { t } from '$lib/i18n';
	import { gewitterFarben, type Farbe } from '../../shared/wetter-tab/ampelModell.ts';

	type Seite = 'lower' | 'upper';
	interface Props {
		id: string;
		erlaubt: string | null;
		eintrag: AmpelMetrik | undefined;
		gewitter?: Ampel['thunder'] | null;
		abweichend: boolean;
		vorlageLabel: string;
		fehler: string[];
		onWert: (seite: Seite, farbe: Farbe, wert: number | null) => void;
		onGewitter: (stufe: 'mittel' | 'hoch', farbe: Farbe) => void;
	}
	let { id, erlaubt, eintrag, gewitter = null, abweichend, vorlageLabel, fehler, onWert, onGewitter }: Props = $props();

	const SEITEN: Record<string, Seite[]> = { both: ['lower', 'upper'], upper: ['upper'], lower: ['lower'] };
	const FOLGE: Record<Seite, Farbe[]> = { lower: ['red', 'orange', 'yellow'], upper: ['yellow', 'orange', 'red'] };
	const ZEICHEN: Record<Seite, string> = { lower: '<', upper: '>' };
	const seiten = $derived(SEITEN[erlaubt ?? ''] ?? []);
	const STUFEN: ('mittel' | 'hoch')[] = ['mittel', 'hoch'];

	// Eingabetexte lokal (ein halb getippter Wert wie „-" bleibt stehen); Startwert beim Oeffnen.
	const start = (s: Seite, f: Farbe) => {
		const v = eintrag?.[s]?.[f];
		return typeof v === 'number' ? String(v) : '';
	};
	let texte = $state<Record<string, string>>({});

	function lies(s: Seite, f: Farbe): string {
		return texte[`${s}.${f}`] ?? start(s, f);
	}
	function eingabe(s: Seite, f: Farbe, roh: string): void {
		texte = { ...texte, [`${s}.${f}`]: roh };
		const w = roh.trim().replace(',', '.');
		onWert(s, f, w === '' ? null : Number(w));
	}
	// i18n-dynamic: wetter.farbe.
	const farbwort = (f: Farbe) => $t(`wetter.farbe.${f}` as 'wetter.farbe.red');
	const farbOptionen = (stufe: 'mittel' | 'hoch') =>
		gewitterFarben(stufe).map((f) => ({ value: f, label: farbwort(f), testid: `wetter-gewitter-${stufe}-${f}`, farbe: f }));
</script>

<div class="wt-edit">
	{#if gewitter}
		{#each STUFEN as stufe (stufe)}
			<div class="wt-grp" data-testid="wetter-gewitter-{stufe}">
				<span class="wt-grp-name">{$t(`wetter.gewitter.${stufe}`)}</span>
				<div class="wt-seg">
					<Segmented rolle="radio" ariaLabel={$t(`wetter.gewitter.${stufe}`)} options={farbOptionen(stufe)} value={gewitter[stufe] ?? ''} onChange={(f: string) => onGewitter(stufe, f as Farbe)} />
				</div>
			</div>
		{/each}
		<p class="wt-hint" data-testid="wetter-gewitter-keins-hinweis">{$t('wetter.gewitter.keins_gruen')}</p>
	{:else}
		{#each seiten as s (s)}
			<div class="wt-grp">
				<span class="wt-grp-name">{$t(s === 'lower' ? 'wetter.grenzen.unten' : 'wetter.grenzen.oben')}</span>
				{#each FOLGE[s] as f (f)}
					<label class="wt-feld">
						<span>{farbwort(f)} {ZEICHEN[s]}</span>
						<Input
							type="text"
							inputmode="decimal"
							ampel={f}
							data-testid="wetter-grenze-{id}-{s}-{f}"
							value={lies(s, f)}
							oninput={(e: Event) => eingabe(s, f, (e.currentTarget as HTMLInputElement).value)}
						/>
					</label>
				{/each}
			</div>
		{/each}
		<p class="wt-hint" data-testid="wetter-grenzen-hinweis-{id}">{$t('wetter.grenzen.hinweis')}</p>
	{/if}
	{#if abweichend}
		<p class="wt-hint" data-testid="wetter-grenzen-abweichend-{id}">{$t('wetter.grenzen.abweichend', { vorlage: vorlageLabel })}</p>
	{/if}
	{#if fehler.length > 0}
		<p class="wt-fehler" role="alert" data-testid="wetter-grenzen-fehler-{id}">
			{fehler.map((k) => $t(k as 'wetter.grenzen.fehler_oben')).join(' ')}
		</p>
	{/if}
</div>

<style>
	.wt-edit {
		grid-column: 1 / -1;
		display: flex;
		flex-wrap: wrap;
		gap: var(--g-s-3) var(--g-s-5);
		align-items: flex-end;
		padding: var(--g-s-3) 0 var(--g-s-1);
	}
	.wt-grp {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		gap: var(--g-s-2);
	}
	.wt-grp-name {
		font-size: var(--g-s-3);
		color: var(--g-ink-2);
		max-width: 9ch;
		align-self: center;
	}
	.wt-feld {
		display: flex;
		flex-direction: column;
		gap: var(--g-size-2px);
		font-size: var(--g-s-3);
		color: var(--g-ink-2);
	}
	/* Unterkante (Ampelfarbe, --g-size-3px) setzt app.css über data-ampel; hier nur die übrigen Kanten. */
	.wt-feld :global([data-slot='input']) {
		width: var(--g-size-72px);
		min-height: var(--g-tap-min);
		box-sizing: border-box;
		padding: var(--g-size-6px) var(--g-s-2);
		font: inherit;
		font-family: var(--g-font-mono);
		font-size: var(--g-size-14px);
		color: var(--g-ink);
		background: var(--g-card);
		border-top-color: var(--g-rule);
		border-inline-color: var(--g-rule);
		border-radius: var(--g-r-2);
	}
	.wt-seg :global([data-slot='segmented-item']) {
		min-height: var(--g-tap-min);
		min-width: var(--g-tap-min);
		color: var(--g-ink-2);
	}
	.wt-seg :global([data-slot='segmented-item'][data-active='true']) {
		color: var(--g-paper);
	}
	.wt-hint {
		flex-basis: 100%;
		margin: 0;
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-3);
	}
	.wt-fehler {
		flex-basis: 100%;
		margin: 0;
		font-size: var(--g-text-sm);
		color: var(--g-danger);
	}
	@media (max-width: 899px) {
		.wt-feld :global([data-slot='input']) {
			font-size: var(--g-s-4);
		}
	}
</style>
