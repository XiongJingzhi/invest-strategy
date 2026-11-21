"""Auditable V2.1 data snapshots, separate signal price from investable total return."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import yfinance as yf


def download_snapshot(directory, start="1985-01-01", end=None, symbols=None):
    """Default single asset: QQQ adjusted USD close converted with observed USD/CNY.

    Archive raw observations. No forward fill of executable prices or FX. The optional
    three-asset set must be supplied explicitly (e.g. GLD / 515100.SS), and is restricted
    to their real existence. NDX high starts with source history, not a trailing window.
    """
    symbols = symbols or {"equity": "QQQ"}
    end = end or datetime.now(UTC).date().isoformat()
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    series, metadata = {}, []
    for name, symbol in {"ndx": "^NDX", "fx": "CNY=X", **symbols}.items():
        raw = yf.download(
            symbol, start=start, end=end, auto_adjust=False, progress=False
        )
        if raw.empty:
            raise ValueError(f"Real history download unavailable: {symbol}")
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        # Official close is distinct from adjusted close and cannot be substituted.
        col = "Close" if name in ("ndx", "fx") else "Adj Close"
        values = raw[col].copy()
        values.index = pd.to_datetime(values.index).tz_localize(None).normalize()
        raw_path = directory / f"{name}-raw.csv"
        raw.to_csv(raw_path)
        series[name] = values
        metadata.append(
            dict(
                name=name,
                symbol=symbol,
                source="Yahoo Finance via yfinance",
                downloaded_at=datetime.now(UTC).isoformat(),
                field=col,
                currency="CNY"
                if symbol.endswith((".SS", ".SZ"))
                else "USD"
                if name != "fx"
                else "CNY per USD",
                first=str(values.index.min()),
                last=str(values.index.max()),
                missing=int(values.isna().sum()),
                sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest(),
            )
        )
    data = pd.concat(series, axis=1).sort_index()
    # Exclude incomplete current US session, including after-hours partial refreshes.
    now = pd.Timestamp.now(tz="America/New_York")
    completed = (
        now.normalize() if now.hour >= 17 else now.normalize() - pd.Timedelta(days=1)
    )
    data = data.loc[data.index <= completed.tz_localize(None)]
    for asset, symbol in symbols.items():
        if not symbol.endswith((".SS", ".SZ")):
            data[asset] = data[asset] * data.fx
    data.to_csv(directory / "market.csv", index_label="date")
    manifest = {
        "kind": "REAL_VENDOR_HISTORY",
        "download_end_exclusive": end,
        "currency": "CNY",
        "signal": "NDX unadjusted daily Close, US 16:00 vendor observation",
        "execution": "next eligible observed adjusted close; not guaranteed real fills",
        "fx": "same-date observed Yahoo USD/CNY; no missing-date fill",
        "warning": "Vendor revisions/adjustments possible; verify official closes before live execution. Current snapshot is not vintage fundamentals.",
        "rows": len(data),
        "missing_by_column": data.isna().sum().to_dict(),
        "sources": metadata,
        "market_sha256": hashlib.sha256(
            (directory / "market.csv").read_bytes()
        ).hexdigest(),
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return data, manifest


def load_snapshot(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    if (
        hashlib.sha256((directory / "market.csv").read_bytes()).hexdigest()
        != manifest["market_sha256"]
    ):
        raise ValueError("Snapshot hash mismatch")
    for source in manifest.get("sources", []):
        raw_name = (
            "fred-DEXCHUS-raw.csv"
            if source["name"] == "fx_extension"
            else f"{source['name']}-raw.csv"
        )
        if (
            hashlib.sha256((directory / raw_name).read_bytes()).hexdigest()
            != source["sha256"]
        ):
            raise ValueError(f"Raw source hash mismatch: {raw_name}")
    return pd.read_csv(
        directory / "market.csv", index_col="date", parse_dates=True
    ), manifest


def extend_fx_from_fred(directory, start="1985-01-01", end=None):
    """Merge Federal Reserve DEXCHUS observations, retaining Yahoo only where FRED absent.

    Exchange rate is an execution/valuation conversion, never a predictive signal.
    DEXCHUS is a noon reference rate, not a guaranteed executable FX quote.
    """
    import io
    from urllib.request import urlopen

    directory = Path(directory)
    data, manifest = load_snapshot(directory)
    end = end or datetime.now(UTC).date().isoformat()
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXCHUS&cosd={start}&coed={end}"
    with urlopen(url, timeout=30) as response:
        payload = response.read()
    raw_path = directory / "fred-DEXCHUS-raw.csv"
    raw_path.write_bytes(payload)
    raw = pd.read_csv(io.BytesIO(payload), index_col=0, parse_dates=True)
    fx = (
        pd.to_numeric(raw.DEXCHUS, errors="coerce")
        .reindex(data.index)
        .combine_first(data.fx)
    )
    for source in manifest["sources"]:
        name = source["name"]
        if name not in ("ndx", "fx") and source["currency"] == "USD":
            prices = pd.read_csv(
                directory / f"{name}-raw.csv", index_col=0, parse_dates=True
            )["Adj Close"]
            data[name] = prices.reindex(data.index) * fx
    data["fx"] = fx
    data.to_csv(directory / "market.csv", index_label="date")
    manifest["sources"] = [
        source for source in manifest["sources"] if source["name"] != "fx_extension"
    ]
    manifest["sources"].append(
        dict(
            name="fx_extension",
            source="Federal Reserve H.10 / FRED DEXCHUS",
            url=url,
            downloaded_at=datetime.now(UTC).isoformat(),
            currency="CNY per USD",
            field="DEXCHUS",
            sha256=hashlib.sha256(payload).hexdigest(),
            first=str(raw.index.min()),
            last=str(raw.index.max()),
            missing=int(pd.to_numeric(raw.DEXCHUS, errors="coerce").isna().sum()),
        )
    )
    manifest["fx"] = (
        "FRED DEXCHUS noon reference rate; Yahoo same-date fallback; no temporal fill; not guaranteed executable FX"
    )
    manifest["missing_by_column"] = data.isna().sum().to_dict()
    manifest["market_sha256"] = hashlib.sha256(
        (directory / "market.csv").read_bytes()
    ).hexdigest()
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return data, manifest
