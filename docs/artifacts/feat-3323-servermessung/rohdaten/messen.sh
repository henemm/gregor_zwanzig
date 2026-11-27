#!/usr/bin/env bash
# Messung #3323: serieller, dann paralleler sicherer Offline-Volllauf im eigenen Worktree.
# Aufruf: messen.sh <worktree> <ausgabeordner>
set -u
export PATH="$HOME/.local/bin:$PATH"
WT="$1"; OUT="$2"; PROD="$HOME/gregor_zwanzig"
mkdir -p "$OUT"; cd "$WT" || exit 2
log(){ echo "$(date -Is) $*" >> "$OUT/ablauf.log"; }

# Abtastung: Summen-RSS aller Prozesse der Gruppe, Gesamt-CPU-%, MemAvailable; Abbruch bei < 1 GB.
sampler(){ # $1=pgid $2=name
  local pg="$1" name="$2" f="$OUT/$2-abtastung.tsv"
  echo -e "zeit\trss_summe_kb\tcpu_summe_pct\tnproc\tmemavail_kb\tload1" > "$f"
  while kill -0 -- "-$pg" 2>/dev/null; do
    read -r rss cpu n < <(ps -o rss=,pcpu= -g "$pg" | awk '{r+=$1;c+=$2;n++} END{print r+0, c+0, n+0}')
    ma=$(awk '/MemAvailable/{print $2}' /proc/meminfo); l1=$(cut -d' ' -f1 /proc/loadavg)
    echo -e "$(date +%T)\t$rss\t$cpu\t$n\t$ma\t$l1" >> "$f"
    if [ "$ma" -lt 1048576 ]; then log "ABBRUCH $name: MemAvailable ${ma} kB < 1 GB"; echo "ABBRUCH_SPEICHER" > "$OUT/$name-abbruch"; kill -TERM -- "-$pg"; fi
    sleep 10
  done
}

selftest(){ # $1=label
  local t0; t0=$(date -Is)
  (cd "$PROD" && timeout 300 python3 .claude/hooks/prod_selftest.py) > "$OUT/selftest-$1.txt" 2>&1
  local rc=$?; echo "$1 start=$t0 ende=$(date -Is) exit=$rc" >> "$OUT/selftest.log"; log "selftest $1 exit=$rc"
}

lauf(){ # $1=name $2=befehl (woertliche Gate-Form)
  log "START $1: $2"
  setsid bash -c "/usr/bin/time -v -o '$OUT/$1-time.txt' $2 > '$OUT/$1.txt' 2>&1" &
  local pid=$!; sleep 1
  sampler "$pid" "$1" & local sp=$!
  if [ "$1" = parallel ]; then
    ( sleep 600; kill -0 "$pid" 2>/dev/null && selftest parallel-10min
      sleep 900; kill -0 "$pid" 2>/dev/null && selftest parallel-25min ) &
  fi
  wait "$pid"; local rc=$?; wait "$sp" 2>/dev/null
  log "ENDE $1 rc=$rc"
}

log "COMMIT $(git rev-parse HEAD)"
selftest kontrolle-vorher
lauf seriell "uv run pytest --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports --ignore=tests/red/"
lauf parallel "nice -n 10 uv run pytest -n 2 --dist loadgroup --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports --ignore=tests/red/"
selftest kontrolle-nachher
log "FERTIG"; touch "$OUT/FERTIG"
