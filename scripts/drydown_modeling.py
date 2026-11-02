"""Leave-one-site-out drydown model comparison and feature-importance tools."""

import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def _pipeline(model_name, feature_columns):
    """Build the model-specific preprocessing pipeline."""
    if model_name == "Ridge":
        preprocessing = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]
        )
        estimator = Ridge(alpha=2.0)
        preprocessing_label = "Median imputation + standardization"
    elif model_name == "Random forest":
        preprocessing = Pipeline([("imputer", SimpleImputer(strategy="median"))])
        estimator = RandomForestRegressor(
            n_estimators=200,
            min_samples_leaf=3,
            max_features=0.8,
            random_state=42,
            n_jobs=1,
        )
        preprocessing_label = "Median imputation"
    elif model_name == "Histogram gradient boosting":
        preprocessing = Pipeline([("imputer", SimpleImputer(strategy="median"))])
        estimator = HistGradientBoostingRegressor(
            learning_rate=0.05,
            max_leaf_nodes=7,
            l2_regularization=1.0,
            random_state=42,
        )
        preprocessing_label = "Median imputation"
    else:
        raise ValueError(f"Unsupported model: {model_name}")

    return (
        Pipeline(
            [
                ("prep", ColumnTransformer([("numeric", preprocessing, feature_columns)])),
                ("model", estimator),
            ]
        ),
        preprocessing_label,
    )


def _evaluate_logo(df, target_column, feature_columns, model_name, feature_set_label):
    """Score one model with held-out-site predictions and importance values."""
    model_df = df.dropna(subset=[target_column]).copy()
    features = model_df[feature_columns]
    target = model_df[target_column]
    groups = model_df["plot"]
    logo = LeaveOneGroupOut()

    predictions = []
    observed = []
    heldout_sites = []
    importance_rows = []

    for train_index, test_index in logo.split(features, target, groups):
        pipeline, preprocessing_label = _pipeline(model_name, feature_columns)
        train_features = features.iloc[train_index]
        test_features = features.iloc[test_index]
        train_target = target.iloc[train_index]
        test_target = target.iloc[test_index]
        heldout_plot = groups.iloc[test_index].iloc[0]

        pipeline.fit(train_features, train_target)
        fold_prediction = pipeline.predict(test_features)
        predictions.extend(fold_prediction)
        observed.extend(test_target)
        heldout_sites.extend([heldout_plot] * len(test_index))

        heldout_importance = permutation_importance(
            pipeline,
            test_features,
            test_target,
            scoring="neg_mean_absolute_error",
            n_repeats=10,
            random_state=42,
            n_jobs=1,
        )
        importance_rows.extend(
            {
                "target": target_column,
                "target_label": "Drying rate" if target_column == "abs_drying_rate" else "Half-life",
                "model_name": model_name,
                "preprocessing": preprocessing_label,
                "feature_set": feature_set_label,
                "heldout_plot": heldout_plot,
                "feature": feature,
                "mae_increase_mean": importance,
            }
            for feature, importance in zip(feature_columns, heldout_importance.importances_mean)
        )

    observed = np.asarray(observed)
    predictions = np.asarray(predictions)
    metrics = {
        "mae": mean_absolute_error(observed, predictions),
        "rmse": np.sqrt(mean_squared_error(observed, predictions)),
        "r2": r2_score(observed, predictions),
    }
    prediction_frame = pd.DataFrame(
        {
            "plot": heldout_sites,
            "target": target_column,
            "target_label": "Drying rate" if target_column == "abs_drying_rate" else "Half-life",
            "model_name": model_name,
            "preprocessing": preprocessing_label,
            "feature_set": feature_set_label,
            "observed": observed,
            "predicted": predictions,
        }
    )
    return metrics, prediction_frame, pd.DataFrame(importance_rows), preprocessing_label


def _plot_model_comparison(comparison, output_directory):
    """Show held-out MAE for every model and feature-set combination."""
    targets = ["Drying rate", "Half-life"]
    colors = {
        "Ridge": "#4c78a8",
        "Random forest": "#59a14f",
        "Histogram gradient boosting": "#e15759",
    }
    figure, axes = plt.subplots(1, 2, figsize=(15, 6), sharex=False)

    for axis, target_label in zip(axes, targets):
        plot_data = comparison[comparison["target_label"] == target_label].copy()
        plot_data = plot_data.sort_values("mae", ascending=True).reset_index(drop=True)
        labels = plot_data["model_name"] + "\n" + plot_data["feature_set"]
        bars = axis.barh(
            labels,
            plot_data["mae"],
            color=plot_data["model_name"].map(colors),
            edgecolor="white",
        )
        for bar, value in zip(bars, plot_data["mae"]):
            axis.text(value, bar.get_y() + bar.get_height() / 2, f"  {value:.4f}", va="center", fontsize=8)
        axis.invert_yaxis()
        axis.set_title(f"{target_label}: held-out-site MAE")
        axis.set_xlabel("MAE (lower is better)")
        axis.grid(axis="x", alpha=0.25)

    figure.suptitle("Drydown model comparison: preprocessing, features, and model family", y=1.02)
    figure.tight_layout()
    figure.savefig(
        os.path.join(output_directory, "soil_J_plot_summary_model_comparison.png"),
        dpi=180,
        bbox_inches="tight",
    )
    plt.show()


def _plot_feature_importance(importance_summary, comparison, output_directory):
    """Plot the top held-out features from the best full-feature model per target."""
    full_feature_set = "Engineered event-onset + plot traits"
    selected_models = (
        comparison[comparison["feature_set"] == full_feature_set]
        .sort_values("mae")
        .groupby("target_label", as_index=False)
        .first()[["target_label", "model_name", "preprocessing", "feature_set"]]
    )
    focus = importance_summary.merge(
        selected_models,
        on=["target_label", "model_name", "preprocessing", "feature_set"],
        how="inner",
    )

    figure, axes = plt.subplots(1, 2, figsize=(15, 6), sharex=False)
    for axis, target_label in zip(axes, ["Drying rate", "Half-life"]):
        target_data = (
            focus[focus["target_label"] == target_label]
            .nlargest(8, "mae_increase_mean")
            .sort_values("mae_increase_mean")
        )
        axis.barh(
            target_data["feature"].str.replace("_", " "),
            target_data["mae_increase_mean"],
            color="#4c78a8",
        )
        axis.set_title(f"{target_label}: top held-out features")
        axis.set_xlabel("Mean MAE increase after permutation")
        axis.grid(axis="x", alpha=0.25)

    figure.suptitle("Permutation importance from the best full-feature model", y=1.02)
    figure.tight_layout()
    figure.savefig(
        os.path.join(output_directory, "soil_L_logo_permutation_importance.png"),
        dpi=180,
        bbox_inches="tight",
    )
    plt.show()
    return focus


def run_drydown_model_suite(model_df, site_trait_columns, output_directory):
    """Compare model/preprocessing options and export held-out feature importance."""
    model_df = model_df.copy()
    model_df["antecedent_moisture_anomaly"] = model_df["start_daily_mean"] - model_df["mean_roll7"]
    model_df["recent_variability_ratio"] = model_df["start_daily_range"] / (model_df["range_roll7"] + 1e-6)

    event_features = [
        "start_signal",
        "start_daily_range",
        "mean_roll7",
        "max_roll3",
        "month_sin",
        "month_cos",
        "antecedent_moisture_anomaly",
        "recent_variability_ratio",
    ]
    feature_sets = {
        "Engineered event-onset": event_features,
        "Engineered event-onset + plot traits": event_features + site_trait_columns,
    }
    model_names = ["Ridge", "Random forest", "Histogram gradient boosting"]
    targets = [
        ("abs_drying_rate", "Drying rate"),
        ("empirical_half_life_days", "Half-life"),
    ]

    comparison_rows = []
    prediction_frames = []
    importance_frames = []
    for target_column, target_label in targets:
        for feature_set_label, feature_columns in feature_sets.items():
            for model_name in model_names:
                metrics, predictions, importance, preprocessing_label = _evaluate_logo(
                    model_df,
                    target_column,
                    feature_columns,
                    model_name,
                    feature_set_label,
                )
                comparison_rows.append(
                    {
                        "target": target_column,
                        "target_label": target_label,
                        "model_name": model_name,
                        "preprocessing": preprocessing_label,
                        "feature_set": feature_set_label,
                        **metrics,
                    }
                )
                prediction_frames.append(predictions)
                importance_frames.append(importance)

    comparison = pd.DataFrame(comparison_rows)
    baseline = comparison[
        (comparison["model_name"] == "Ridge")
        & (comparison["feature_set"] == "Engineered event-onset")
    ][["target", "mae", "rmse"]].rename(columns={"mae": "baseline_mae", "rmse": "baseline_rmse"})
    comparison = comparison.merge(baseline, on="target", how="left")
    comparison["mae_change_vs_baseline_pct"] = 100 * (
        comparison["baseline_mae"] - comparison["mae"]
    ) / comparison["baseline_mae"]
    comparison["rmse_change_vs_baseline_pct"] = 100 * (
        comparison["baseline_rmse"] - comparison["rmse"]
    ) / comparison["baseline_rmse"]
    comparison = comparison.drop(columns=["baseline_mae", "baseline_rmse"])

    predictions = pd.concat(prediction_frames, ignore_index=True)
    importance_detail = pd.concat(importance_frames, ignore_index=True)
    importance_summary = (
        importance_detail.groupby(
            ["target", "target_label", "model_name", "preprocessing", "feature_set", "feature"],
            as_index=False,
        )
        .agg(
            mae_increase_mean=("mae_increase_mean", "mean"),
            mae_increase_std=("mae_increase_mean", "std"),
            heldout_sites=("heldout_plot", "nunique"),
        )
        .sort_values(["target_label", "model_name", "feature_set", "mae_increase_mean"], ascending=[True, True, True, False])
    )

    os.makedirs(output_directory, exist_ok=True)
    model_df.to_csv(os.path.join(output_directory, "soil_drydown_events_with_plot_summary.csv"), index=False)
    comparison.to_csv(os.path.join(output_directory, "soil_plot_summary_model_comparison.csv"), index=False)
    predictions.to_csv(os.path.join(output_directory, "soil_plot_summary_predictions.csv"), index=False)
    importance_detail.to_csv(os.path.join(output_directory, "soil_logo_permutation_importance.csv"), index=False)
    importance_summary.to_csv(
        os.path.join(output_directory, "soil_logo_feature_importance_summary.csv"),
        index=False,
    )
    _plot_model_comparison(comparison, output_directory)
    importance_focus = _plot_feature_importance(importance_summary, comparison, output_directory)
    return model_df, comparison, predictions, importance_detail, importance_summary, importance_focus
