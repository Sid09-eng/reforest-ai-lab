"""Time-aware descriptive statistics for daily microclimate data."""

from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats


def non_circular_block_positions(series_length, block_days, starts):
    """Expand moving-block starts without joining the end of a series to its start."""
    return np.concatenate(
        [np.arange(start, min(start + block_days, series_length)) for start in starts]
    )


def moving_block_spearman(
    frame,
    left,
    right,
    *,
    plot_column="plot",
    date_column="date",
    block_days=14,
    n_bootstrap=500,
    random_state=42,
):
    """Estimate within-plot Spearman association with a moving-block interval."""
    required = {plot_column, date_column, left, right}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Dataframe is missing required columns: {sorted(missing)}")
    if block_days < 2 or n_bootstrap < 20:
        raise ValueError("block_days must be at least 2 and n_bootstrap at least 20")

    paired = frame[[plot_column, date_column, left, right]].dropna().copy()
    paired[date_column] = pd.to_datetime(paired[date_column], errors="coerce")
    paired = paired.dropna(subset=[date_column]).sort_values([plot_column, date_column])
    groups = [group.reset_index(drop=True) for _, group in paired.groupby(plot_column) if len(group) >= 4]
    if not groups:
        raise ValueError(f"No plot has enough paired observations for {left} and {right}")

    plot_rhos = [stats.spearmanr(group[left], group[right]).statistic for group in groups]
    rng = np.random.default_rng(random_state)
    bootstrap_medians = []
    for _ in range(n_bootstrap):
        replicate_rhos = []
        for group in groups:
            effective_block_days = min(block_days, len(group))
            starts = rng.integers(
                0,
                len(group) - effective_block_days + 1,
                size=int(np.ceil(len(group) / effective_block_days)),
            )
            positions = non_circular_block_positions(
                len(group), effective_block_days, starts
            )[: len(group)]
            sample = group.iloc[positions]
            rho = stats.spearmanr(sample[left], sample[right]).statistic
            if np.isfinite(rho):
                replicate_rhos.append(rho)
        if replicate_rhos:
            bootstrap_medians.append(float(np.median(replicate_rhos)))

    if not bootstrap_medians:
        raise ValueError(f"Block bootstrap failed for {left} and {right}")
    ci_low, ci_high = np.quantile(bootstrap_medians, [0.025, 0.975])
    pooled_rho = stats.spearmanr(paired[left], paired[right]).statistic
    return {
        "variable_1": left,
        "variable_2": right,
        "paired_plot_days": int(len(paired)),
        "plots": int(len(groups)),
        "pooled_rho": float(pooled_rho),
        "within_plot_median_rho": float(np.nanmedian(plot_rhos)),
        "within_plot_min_rho": float(np.nanmin(plot_rhos)),
        "within_plot_max_rho": float(np.nanmax(plot_rhos)),
        "ci_low": float(ci_low),
        "ci_high": float(ci_high),
        "block_days": int(block_days),
        "bootstrap_repeats": int(n_bootstrap),
    }


def block_spearman_table(frame, variables, **kwargs):
    """Return moving-block Spearman summaries for every variable pair."""
    rows = [moving_block_spearman(frame, left, right, **kwargs) for left, right in combinations(variables, 2)]
    return pd.DataFrame(rows).sort_values("within_plot_median_rho", key=lambda values: values.abs(), ascending=False)
