"""Refresh in a temporary directory; never silently publish a partial snapshot."""
from pathlib import Path
import shutil
import tempfile
from invest_strategy.market import download_snapshot, extend_fx_from_fred

root = Path(__file__).resolve().parents[1] / 'reports/data'
with tempfile.TemporaryDirectory() as tmp:
    for name, symbols in [('single', {'equity':'QQQ'}), ('portfolio', {'equity':'QQQ','gold':'GLD','dividend':'515100.SS'})]:
        path = Path(tmp) / name
        download_snapshot(path, symbols=symbols)
        data, _ = extend_fx_from_fred(path)
        if data.ndx.dropna().empty or data.equity.dropna().empty:
            raise ValueError(f'{name}: incomplete market snapshot')
        shutil.copytree(path, root/name, dirs_exist_ok=True)
