from types import SimpleNamespace
import inspect

import pandas as pd

import app
from app import (
    _compact_layout_css,
    _comparison_selected_profile_name,
    _current_valuation_from_history,
    _default_profile_index,
)


def test_comparison_selection_returns_clicked_strategy_name():
    display = pd.DataFrame(
        {
            "策略组合": ["纯固定定投", "成长进攻"],
            "总收益率": [10.0, 20.0],
        }
    )
    event = SimpleNamespace(selection=SimpleNamespace(rows=[1]))

    selected = _comparison_selected_profile_name(
        event,
        display,
        valid_profile_names={"纯固定定投", "成长进攻"},
        current_name="纯固定定投",
    )

    assert selected == "成长进攻"


def test_comparison_selection_ignores_current_or_invalid_rows():
    display = pd.DataFrame({"策略组合": ["纯固定定投", "临时结果"]})

    assert (
        _comparison_selected_profile_name(
            {"selection": {"rows": [0]}},
            display,
            valid_profile_names={"纯固定定投"},
            current_name="纯固定定投",
        )
        is None
    )
    assert (
        _comparison_selected_profile_name(
            {"selection": {"rows": [1]}},
            display,
            valid_profile_names={"纯固定定投"},
            current_name="纯固定定投",
        )
        is None
    )


def test_main_only_renders_one_monthly_detail_table():
    source = inspect.getsource(app.main)

    assert "target_monthly_display_frame" not in source
    assert source.count("monthly_display_frame(result.monthly)") == 1


def test_default_profile_index_uses_simple_fixed_dca():
    assert _default_profile_index(["纯固定定投", "稳健定投"]) == 0
    assert _default_profile_index(["稳健定投", "纯固定定投"]) == 1
    assert _default_profile_index(["稳健定投"]) == 0


def test_current_valuation_preserves_pe_percentile():
    valuation_history = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-12-31"]),
            "dividend_yield": [5.9],
            "dividend_percentile": [80.0],
            "pe": [8.86],
            "pe_percentile": [15.0],
        }
    )

    valuation = _current_valuation_from_history(valuation_history)

    assert valuation.dividend_percentile == 80.0
    assert valuation.dividend_yield == 5.9
    assert valuation.pe == 8.86
    assert valuation.pe_percentile == 15.0


def test_compact_layout_css_reduces_top_and_sidebar_spacing():
    css = _compact_layout_css()

    assert ".block-container" in css
    assert "padding-top: 1rem" in css
    assert "section[data-testid=\"stSidebar\"]" in css
    assert "gap: 0.35rem" in css
