"""Sensitivity checks for the hard-cleaned and analysis-screened data tiers."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from scripts.microclimate_forecasting import (
    MODEL_ORDER,
    MODEL_SELECTION_ORDER,
    _fold_metrics,
    _regression_pipeline,
    build_daily_forecast_frame,
)
from scripts.microclimate_statistics import block_spearman_table


DAILY_COLUMNS = ["temperature", "relative_humidity", "vpd", "par", "soil_moisture"]
VPD_BINS = [-np.inf, 0.2, 0.5, 0.8, np.inf]
VPD_LABELS = ["low_demand", "moderate_demand", "high_demand", "very_high_demand"]


def build_daily_microclimate(raw_data):
    """Create the plot-day table used by the readiness analysis."""
    data = raw_data.loc[
        raw_data["param"].isin(["temp", "rh", "vpd", "par", "soil moisture"]),
        ["time", "plot", "ft", "param", "value"],
    ].copy()
    data["date"] = pd.to_datetime(data["time"], errors="coerce").dt.floor("D")
    daily = (
        data.pivot_table(index=["date", "plot", "ft"], columns="param", values="value", aggfunc="mean")
        .rename(columns={"temp": "temperature", "rh": "relative_humidity", "soil moisture": "soil_moisture"})
        .reset_index()
        .sort_values(["plot", "date"])
        .reset_index(drop=True)
    )
    for column in DAILY_COLUMNS:
        if column not in daily:
            daily[column] = np.nan
    if daily["vpd"].quantile(0.99) > 10:
        daily["vpd"] = daily["vpd"] / 1000
    return daily


def _add_vpd_state(frame):
    result = frame.copy()
    result["vpd_state"] = pd.cut(result["vpd"], VPD_BINS, labels=VPD_LABELS)
    return result


def compare_vpd_labels(hard_clean_daily, screened_daily):
    """Report how often VPD labels change after screening."""
    hard = _add_vpd_state(hard_clean_daily)[["plot", "date", "vpd_state"]].rename(
        columns={"vpd_state": "hard_clean_state"}
    )
    screened = _add_vpd_state(screened_daily)[["plot", "date", "vpd_state"]].rename(
        columns={"vpd_state": "screened_state"}
    )
    paired = hard.merge(screened, on=["plot", "date"], how="inner").dropna()
    agreement = paired["hard_clean_state"].astype(str).eq(paired["screened_state"].astype(str))
    summary = pd.DataFrame(
        [
            {
                "paired_plot_days": len(paired),
                "matching_labels": int(agreement.sum()),
                "changed_labels": int((~agreement).sum()),
                "agreement_rate": float(agreement.mean()),
            }
        ]
    )
    transitions = (
        paired.assign(
            hard_clean_state=paired["hard_clean_state"].astype(str),
            screened_state=paired["screened_state"].astype(str),
        )
        .groupby(["hard_clean_state", "screened_state"], as_index=False, observed=True)
        .size()
        .rename(columns={"size": "plot_days"})
    )
    return summary, transitions


def evaluate_temporal_regression(daily_frame, targets, feature_columns):
    """Run the chronological 60/20/20 regression check for one data tier."""
    validation_rows = []
    final_rows = []
    split_rows = []
    for target in targets:
        target_column = f"target_{target}"
        target_frame = daily_frame.dropna(subset=[target, target_column]).sort_values("date").copy()
        dates = np.sort(target_frame["date"].unique())
        if len(dates) < 15:
            raise ValueError(f"Not enough dates for a chronological split of {target}.")
        train_cutoff = dates[int(len(dates) * 0.60)]
        validation_cutoff = dates[int(len(dates) * 0.80)]
        train = target_frame[target_frame["date"] <= train_cutoff]
        validation = target_frame[(target_frame["date"] > train_cutoff) & (target_frame["date"] <= validation_cutoff)]
        test = target_frame[target_frame["date"] > validation_cutoff]
        for split_name, split_frame in {"train": train, "validation": validation, "final_test": test}.items():
            split_rows.append(
                {
                    "target": target,
                    "split": split_name,
                    "rows": len(split_frame),
                    "start_date": split_frame["date"].min(),
                    "end_date": split_frame["date"].max(),
                    "plots": split_frame["plot"].nunique(),
                }
            )

        candidates = [{"target": target, "model_name": "Persistence", **_fold_metrics(validation[target_column], validation[target])}]
        for model_name in MODEL_ORDER:
            model = _regression_pipeline(model_name, feature_columns, train)
            model.fit(train[feature_columns], train[target_column])
            candidates.append(
                {"target": target, "model_name": model_name, **_fold_metrics(validation[target_column], model.predict(validation[feature_columns]))}
            )
        candidate_frame = pd.DataFrame(candidates)
        validation_rows.extend(candidate_frame.to_dict("records"))
        best_mae = candidate_frame["mae"].min()
        finalists = candidate_frame[candidate_frame["mae"] <= best_mae * 1.01].copy()
        finalists["complexity_order"] = finalists["model_name"].map(MODEL_SELECTION_ORDER)
        selected = finalists.sort_values(["complexity_order", "mae"]).iloc[0]["model_name"]

        persistence_metrics = _fold_metrics(test[target_column], test[target])
        if selected == "Persistence":
            prediction = test[target].to_numpy()
        else:
            train_validation = pd.concat([train, validation], ignore_index=True)
            model = _regression_pipeline(selected, feature_columns, train_validation)
            model.fit(train_validation[feature_columns], train_validation[target_column])
            prediction = model.predict(test[feature_columns])
        selected_metrics = _fold_metrics(test[target_column], prediction)
        final_rows.append(
            {
                "target": target,
                "selected_model": selected,
                "persistence_mae": persistence_metrics["mae"],
                **selected_metrics,
                "mae_improvement_vs_persistence_pct": (
                    100 * (persistence_metrics["mae"] - selected_metrics["mae"]) / persistence_metrics["mae"]
                    if persistence_metrics["mae"]
                    else np.nan
                ),
                "final_test_rows": len(test),
            }
        )
    return pd.DataFrame(final_rows), pd.DataFrame(validation_rows), pd.DataFrame(split_rows)


def evaluate_vpd_classifier(daily_frame):
    """Repeat the leakage-safe VPD-state 60/20/20 comparison for one tier."""
    forecast = _add_vpd_state(daily_frame).sort_values(["plot", "date"]).reset_index(drop=True)
    for column in DAILY_COLUMNS:
        grouped = forecast.groupby("plot")[column]
        forecast[f"{column}_lag1"] = grouped.shift(1)
        forecast[f"{column}_roll3"] = grouped.transform(lambda values: values.shift(1).rolling(3, min_periods=2).mean())
        forecast[f"{column}_roll7"] = grouped.transform(lambda values: values.shift(1).rolling(7, min_periods=4).mean())
    forecast["day_of_year_sin"] = np.sin(2 * np.pi * forecast["date"].dt.dayofyear / 365.25)
    forecast["day_of_year_cos"] = np.cos(2 * np.pi * forecast["date"].dt.dayofyear / 365.25)
    groups = forecast.groupby("plot")
    forecast["target_vpd_state"] = groups["vpd_state"].shift(-1)
    next_date = groups["date"].shift(-1)
    forecast.loc[(next_date - forecast["date"]) != pd.Timedelta(days=1), "target_vpd_state"] = np.nan
    features = [column for column in forecast if column.endswith(("_lag1", "_roll3", "_roll7"))]
    features += ["day_of_year_sin", "day_of_year_cos"]
    model_data = forecast.dropna(subset=["target_vpd_state"])
    dates = np.sort(model_data["date"].unique())
    train_cutoff = dates[int(len(dates) * 0.60)]
    validation_cutoff = dates[int(len(dates) * 0.80)]
    train = model_data[model_data["date"] <= train_cutoff]
    validation = model_data[(model_data["date"] > train_cutoff) & (model_data["date"] <= validation_cutoff)]
    test = model_data[model_data["date"] > validation_cutoff]
    factories = {
        "logistic_regression": lambda: Pipeline(
            [("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()), ("model", LogisticRegression(max_iter=2000, class_weight="balanced", C=0.2, random_state=42))]
        ),
        "hist_gradient_boosting": lambda: Pipeline(
            [("impute", SimpleImputer(strategy="median")), ("model", HistGradientBoostingClassifier(max_iter=150, max_leaf_nodes=15, l2_regularization=1, class_weight="balanced", random_state=42))]
        ),
    }

    def scores(model_name, observed, predicted):
        return {
            "model_name": model_name,
            "rows": len(observed),
            "accuracy": accuracy_score(observed, predicted),
            "balanced_accuracy": balanced_accuracy_score(observed, predicted),
            "macro_f1": f1_score(observed, predicted, average="macro", zero_division=0),
        }

    validation_rows = [scores("persistence", validation["target_vpd_state"].astype(str), validation["vpd_state"].astype(str))]
    for name, factory in factories.items():
        model = factory()
        model.fit(train[features], train["target_vpd_state"].astype(str))
        validation_rows.append(scores(name, validation["target_vpd_state"].astype(str), model.predict(validation[features])))
    validation_metrics = pd.DataFrame(validation_rows).sort_values("macro_f1", ascending=False)
    selected = validation_metrics.iloc[0]["model_name"]
    if selected == "persistence":
        prediction = test["vpd_state"].astype(str)
    else:
        model = factories[selected]()
        train_validation = pd.concat([train, validation], ignore_index=True)
        model.fit(train_validation[features], train_validation["target_vpd_state"].astype(str))
        prediction = model.predict(test[features])
    final = pd.DataFrame([scores(selected, test["target_vpd_state"].astype(str), prediction)])
    final["selected_model"] = selected
    return final, validation_metrics


def run_screening_robustness(hard_clean, screened, output_directory, n_bootstrap=300):
    """Repeat principal labels, correlations, and temporal forecasts across both tiers."""
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    daily = {
        "hard_cleaned": build_daily_microclimate(hard_clean),
        "analysis_screened": build_daily_microclimate(screened),
    }
    label_summary, label_transitions = compare_vpd_labels(daily["hard_cleaned"], daily["analysis_screened"])

    correlation_frames = []
    for tier, frame in daily.items():
        result = block_spearman_table(frame, DAILY_COLUMNS, block_days=14, n_bootstrap=n_bootstrap, random_state=42)
        correlation_frames.append(result.assign(data_tier=tier))
    correlations = pd.concat(correlation_frames, ignore_index=True)
    correlation_comparison = correlations.pivot(
        index=["variable_1", "variable_2"], columns="data_tier", values="within_plot_median_rho"
    ).reset_index()
    correlation_comparison["screened_minus_hard_cleaned"] = (
        correlation_comparison["analysis_screened"] - correlation_comparison["hard_cleaned"]
    )

    classifier_rows = []
    regression_rows = []
    for tier, frame in daily.items():
        final_classifier, _ = evaluate_vpd_classifier(frame)
        classifier_rows.append(final_classifier.assign(data_tier=tier))
        forecast_frame = build_daily_forecast_frame(hard_clean if tier == "hard_cleaned" else screened)
        targets = list(DAILY_COLUMNS)
        features = [
            column for column in forecast_frame
            if column not in {"plot", "date", "forecast_date"} and not column.startswith("target_")
        ]
        final_regression, _, _ = evaluate_temporal_regression(forecast_frame, targets, features)
        regression_rows.append(final_regression.assign(data_tier=tier))
    classifier_metrics = pd.concat(classifier_rows, ignore_index=True)
    regression_metrics = pd.concat(regression_rows, ignore_index=True)

    label_summary.to_csv(output_directory / "tier_vpd_label_agreement.csv", index=False)
    label_transitions.to_csv(output_directory / "tier_vpd_label_transitions.csv", index=False)
    correlations.to_csv(output_directory / "tier_block_spearman_correlations.csv", index=False)
    correlation_comparison.to_csv(output_directory / "tier_correlation_comparison.csv", index=False)
    classifier_metrics.to_csv(output_directory / "tier_vpd_classifier_metrics.csv", index=False)
    regression_metrics.to_csv(output_directory / "tier_temporal_regression_metrics.csv", index=False)

    figure, axes = plt.subplots(2, 2, figsize=(13, 9))
    axes[0, 0].bar(["Matching", "Changed"], [label_summary.loc[0, "matching_labels"], label_summary.loc[0, "changed_labels"]], color=["#4c78a8", "#f58518"])
    axes[0, 0].set_title("VPD-state labels after screening")
    axes[0, 0].set_ylabel("Paired plot-days")
    axes[0, 1].scatter(correlation_comparison["hard_cleaned"], correlation_comparison["analysis_screened"], color="#4c78a8")
    axes[0, 1].plot([-1, 1], [-1, 1], "--", color="#555555")
    axes[0, 1].set(xlim=(-1, 1), ylim=(-1, 1), xlabel="Hard-cleaned rho", ylabel="Screened rho", title="Within-plot correlation sensitivity")
    for tier, group in classifier_metrics.groupby("data_tier"):
        axes[1, 0].bar(tier.replace("_", " "), group.iloc[0]["macro_f1"])
    axes[1, 0].set_ylim(0, 1)
    axes[1, 0].set_title("Final-period VPD-state macro-F1")
    pivot_mae = regression_metrics.pivot(index="target", columns="data_tier", values="mae")
    pivot_mae.plot(kind="bar", ax=axes[1, 1], color=["#4c78a8", "#f58518"])
    axes[1, 1].set_yscale("log")
    axes[1, 1].set_title("Final-period regression MAE by data tier")
    axes[1, 1].set_ylabel("MAE (log scale)")
    axes[1, 1].set_xlabel("")
    axes[1, 1].tick_params(axis="x", rotation=25)
    figure.tight_layout()
    figure.savefig(output_directory / "screening_robustness_summary.png", dpi=180, bbox_inches="tight")
    plt.close(figure)
    return {
        "label_summary": label_summary,
        "label_transitions": label_transitions,
        "correlations": correlations,
        "correlation_comparison": correlation_comparison,
        "classifier_metrics": classifier_metrics,
        "regression_metrics": regression_metrics,
        "figure_path": output_directory / "screening_robustness_summary.png",
    }
