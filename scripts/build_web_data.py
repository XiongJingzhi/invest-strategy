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
package = root / 'web/public/python/invest_strategy'
package.mkdir(parents=True, exist_ok=True)
for name in ('__init__.py', 'account.py', 'models.py', 'performance.py', 'valuation.py', 'decision.py', 'compare.py', 'research.py'):
    shutil.copy(root / 'src/invest_strategy' / name, package / name)
# compare imports legacy backtest and profile modules at import time.
for name in ('backtest.py', 'strategies.py', 'profiles.py'):
    shutil.copy(root / 'src/invest_strategy' / name, package / name)
