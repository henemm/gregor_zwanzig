// Pruefstand fuer #3047 Runde 7, Paket p10 (Matrixzellen orte.ortsfolge / orte.orte_auswahl /
// orte.ortsnamen): die Orte-MAIL einer gespeicherten Konfiguration ueber die ECHTE Python-Kette,
// ohne Netz. Keine .test.ts-Datei.
//
// Kette wie im Betrieb (tests/helpers/einstellung_gleich_mail_orte.py `sende_orte_mail`):
// Profil + Orte je Nutzer in einer frischen Datenwurzel -> Preset als rohes JSON ->
// `load_compare_presets` -> `send_one_compare_preset` -> Renderer -> `mail_sink`. Das Wetter kommt
// aus der offline-Engine-Naht des Helfers (`wetter_naht`, Werte aus `build_result`). Abgelesen
// wird nur die fertige Mail: Folge der Ort-Bloecke (Klartext-Uebersicht, Stundenverlauf-Koepfe)
// und Folge der Ortsnamen im HTML.
// Muster wie ausgabeOrakel.ts: `uv run python3 -c …` im Repo-Wurzelverzeichnis, Eingabe per stdin.

import { execFileSync } from 'node:child_process';
import { REPO } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';

const PY = `
import sys, json, re, tempfile, html as H
sys.path.insert(0, 'src'); sys.path.insert(0, '.')
import app.loader as L
L._DATA_ROOT = tempfile.mkdtemp(prefix='gz-p10-')
import tests.helpers.einstellung_gleich_mail_orte as O
from services.send_outcomes import InvalidPresetError

def ort_bloecke(plain):
    zeilen = plain.splitlines()
    start = next(i for i, z in enumerate(zeilen) if z.startswith('-----')) + 1
    namen = []
    for z in zeilen[start:]:
        if z.strip() in ('STUNDENVERLAUF',) or z.startswith('Einheiten:'):
            break
        if z and not z.startswith(' '):
            namen.append(z)
    return namen

def stunden_koepfe(plain, namen):
    return [z[:-len(' (CET)')] for z in plain.splitlines() if z.endswith(' (CET)') and z[:-len(' (CET)')] in namen]

def html_folge(body, namen):
    text = H.unescape(re.sub(r'<[^>]+>', ' ', body))
    pos = {n: text.find(n) for n in namen}
    return [n for n in sorted(pos, key=pos.get) if pos[n] >= 0]

K = json.loads(sys.stdin.read())
aus = {}
for uid, n in K.items():
    O.ORTE = {o['id']: (o['name'], 46.5, 11.5, i % 3) for i, o in enumerate(n['orte'])}
    preset = O.preset_dict('basis')
    preset['id'] = 'p10-' + uid
    preset['location_ids'] = n['location_ids']
    namen = [o['name'] for o in n['orte']]
    try:
        m = O.sende_orte_mail(preset, uid=uid)
    except InvalidPresetError as e:
        aus[uid] = {'fehler': e.reason_key}
        continue
    aus[uid] = {
        'bloecke': ort_bloecke(m.plain),
        'stunden': stunden_koepfe(m.plain, namen),
        'html': html_folge(m.html, namen),
        'gespeichert': m.roh['location_ids'],
    }
print(json.dumps(aus, ensure_ascii=False))
`;

export type Ort = { id: string; name: string };
export type NutzerEingabe = { orte: Ort[]; location_ids: string[] };
export type OrteMailFolge =
	| { bloecke: string[]; stunden: string[]; html: string[]; gespeichert: string[]; fehler?: undefined }
	| { fehler: string };

/** Je Nutzer: Orte (eigene Datenablage) + gespeicherte `location_ids` -> Folge der Orte in der Mail. */
export function orteMailFolge(nutzer: Record<string, NutzerEingabe>): Record<string, OrteMailFolge> {
	const stdout = execFileSync('uv', ['run', 'python3', '-c', PY], {
		cwd: REPO,
		input: JSON.stringify(nutzer),
		encoding: 'utf-8',
		maxBuffer: 32 * 1024 * 1024,
		stdio: ['pipe', 'pipe', 'inherit']
	});
	return JSON.parse(stdout.trim().split('\n').pop()!);
}
