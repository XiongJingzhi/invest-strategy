"""Copy hash-verified market snapshots and existing strategy engine into the site."""
from pathlib import Path
import json
import shutil
from invest_strategy.market import load_snapshot

root = Path(__file__).resolve().parents[1]
out = root / 'web/public/data'
out.mkdir(parents=True, exist_ok=True)
for name in ('single', 'portfolio'):
    market, manifest = load_snapshot(root / 'reports/data' / name)
    market.to_csv(out / f'{name}.csv', index_label='date')
    (out / f'{name}-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False))
for name in ('single', 'portfolio'):
    for suffix in ('rolling-summary.csv', 'event-summary.csv'):
        shutil.copy(root / 'reports' / f'{name}-{suffix}', out / f'{name}-{suffix}')
# Precompute the exchange calendar for fixed trading-day schedules.
import exchange_calendars as xcals
calendar = xcals.get_calendar("XNYS", start="1980-01-01", end="2100-12-31")
(out / "xnys.json").write_text(json.dumps([str(d.date()) for d in calendar.sessions]))
