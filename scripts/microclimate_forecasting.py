"""Leakage-safe daily and hourly microclimate forecasting utilities."""

from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


PARAMETER_NAMES = {
    "temp": "temperature",
    "rh": "relative_humidity",
    "vpd": "vpd",
    "par": "par",
    "soil moisture": "soil_moisture",
}


def build_daily_forecast_frame(raw_data, min_daily_observations=18):
    """Create daily predictor rows at day t with targets for day t + 1."""
    data = raw_data.copy()
    data["time"] = pd.to_datetime(data["time"], format="mixed", errors="coerce")
    data = data.dropna(subset=["time", "plot", "param", "value"])
    data = data[data["param"].isin(PARAMETER_NAMES)].copy()
    data["signal"] = data["param"].map(PARAMETER_NAMES)
    data["date"] = data["time"].dt.normalize()

    group_columns = ["plot", "date", "signal"]
    if "ft" in data.columns:
        group_columns.insert(1, "ft")
    daily = (
        data.groupby(group_columns, as_index=False)
        .agg(value=("value", "mean"), observations=("value", "size"))
    )
    daily.loc[daily["observations"] < min_daily_observations, "value"] = np.nan

    index_columns = ["plot", "date"]
    if "ft" in daily.columns:
        index_columns.insert(1, "ft")
    values = daily.pivot(index=index_columns, columns="signal", values="value").reset_index()
    for signal in PARAMETER_NAMES.values():
        if signal not in values:
            values[signal] = np.nan
    values = values.sort_values(["plot", "date"]).reset_index(drop=True)

    for signal in PARAMETER_NAMES.values():
        grouped = values.groupby("plot", sort=False)[signal]
        values[f"{signal}_lag_1"] = grouped.shift(1)
        values[f"{signal}_roll3"] = grouped.transform(lambda series: series.rolling(3, min_periods=1).mean())
        values[f"{signal}_roll7"] = grouped.transform(lambda series: series.rolling(7, min_periods=1).mean())

    values["forecast_date"] = values.groupby("plot", sort=False)["date"].shift(-1)
    is_next_day = values["forecast_date"].eq(values["date"] + pd.Timedelta(days=1))
    for signal in PARAMETER_NAMES.values():
        values[f"target_{signal}"] = values.groupby("plot", sort=False)[signal].shift(-1).where(is_next_day)

    day_of_year = values["date"].dt.dayofyear
    values["day_of_year_sin"] = np.sin(2 * np.pi * day_of_year / 365.25)
    values["day_of_year_cos"] = np.cos(2 * np.pi * day_of_year / 365.25)
    return values


MODEL_ORDER = {
    "Ridge": 0,
    "Elastic net": 1,
    "Histogram gradient boosting": 2,
    "Random forest": 3,
    "Extra trees": 4,
}

MODEL_SELECTION_ORDER = {"Persistence": 0, **{name: order + 1 for name, order in MODEL_ORDER.items()}}


class PersistenceRegressor(BaseEstimator, RegressorMixin):
    """Return the current observed value as the next-step forecast."""

    def __init__(self, source_column):
        self.source_column = source_column

    def fit(self, features, target=None):
        if self.source_column not in features:
            raise ValueError(f"Persistence source column is missing: {self.source_column}")
        return self

    def predict(self, features):
        if self.source_column not in features:
            raise ValueError(f"Persistence source column is missing: {self.source_column}")
        return features[self.source_column].to_numpy(dtype=float)


def _regression_pipeline(model_name, feature_columns, frame):
    categorical_features = [
        column
        for column in feature_columns
        if pd.api.types.is_object_dtype(frame[column])
        or pd.api.types.is_string_dtype(frame[column])
        or isinstance(frame[column].dtype, pd.CategoricalDtype)
    ]
    numeric_features = [column for column in feature_columns if column not in categorical_features]
    if model_name in {"Ridge", "Elastic net"}:
        numeric_steps = [("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]
    else:
        numeric_steps = [("imputer", SimpleImputer(strategy="median"))]
    transformers = [("numeric", Pipeline(numeric_steps), numeric_features)]
    if categorical_features:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_features,
            )
        )
    estimators = {
        "Ridge": Ridge(alpha=2.0),
        "Elastic net": ElasticNet(alpha=0.01, l1_ratio=0.3, max_iter=10_000, random_state=42),
        "Random forest": RandomForestRegressor(
            n_estimators=100, min_samples_leaf=3, max_features=0.8, random_state=42, n_jobs=1
        ),
        "Extra trees": ExtraTreesRegressor(
            n_estimators=100, min_samples_leaf=3, max_features=0.8, random_state=42, n_jobs=1
        ),
        "Histogram gradient boosting": HistGradientBoostingRegressor(
            learning_rate=0.05, max_leaf_nodes=15, l2_regularization=1.0, random_state=42
        ),
    }
    return Pipeline([("prep", ColumnTransformer(transformers)), ("model", estimators[model_name])])


def _fold_metrics(observed, predicted):
    return {
        "mae": mean_absolute_error(observed, predicted),
        "rmse": np.sqrt(mean_squared_error(observed, predicted)),
        "r2": r2_score(observed, predicted) if len(observed) > 1 else np.nan,
    }


def _heldout_site_metrics(predictions):
    """Summarise each target/model/site fold and its across-site variation."""
    rows = []
    for (target, model_name, heldout_plot), group in predictions.groupby(
        ["target", "model_name", "heldout_plot"], sort=False
    ):
        rows.append(
            {
                "target": target,
                "model_name": model_name,
                "heldout_plot": heldout_plot,
                "forecast_days": len(group),
                **_fold_metrics(group["observed"], group["predicted"]),
            }
        )
    site_metrics = pd.DataFrame(rows)
    site_variation = (
        site_metrics.groupby(["target", "model_name"], as_index=False)
        .agg(
            sites=("heldout_plot", "nunique"),
            mae_mean=("mae", "mean"),
            mae_std=("mae", "std"),
            mae_min=("mae", "min"),
            mae_max=("mae", "max"),
            rmse_mean=("rmse", "mean"),
            r2_mean=("r2", "mean"),
        )
    )
    return site_metrics, site_variation


def run_daily_model_suite(frame, targets=None, feature_columns=None):
    """Evaluate daily regressors by leave-one-site-out validation and select winners."""
    targets = list(targets or PARAMETER_NAMES.values())
    if feature_columns is None:
        excluded = {"plot", "date", "forecast_date"}
        feature_columns = [
            column for column in frame.columns if column not in excluded and not column.startswith("target_")
        ]
    model_names = ["Persistence", *MODEL_ORDER]
    comparison_rows = []
    prediction_frames = []

    for target in targets:
        target_column = f"target_{target}"
        model_frame = frame.dropna(subset=[target_column, target]).copy()
        groups = model_frame["plot"]
        splitter = LeaveOneGroupOut()
        for model_name in model_names:
            fold_rows = []
            for train_index, test_index in splitter.split(model_frame, groups=groups):
                train = model_frame.iloc[train_index]
                test = model_frame.iloc[test_index]
                if model_name == "Persistence":
                    predicted = test[target].to_numpy()
                else:
                    pipeline = _regression_pipeline(model_name, feature_columns, train)
                    pipeline.fit(train[feature_columns], train[target_column])
                    predicted = pipeline.predict(test[feature_columns])
                observed = test[target_column].to_numpy()
                metrics = _fold_metrics(observed, predicted)
                heldout_plot = test["plot"].iloc[0]
                fold_rows.append({"heldout_plot": heldout_plot, **metrics})
                prediction_frames.append(
                    pd.DataFrame(
                        {
                            "date": test["date"].to_numpy(),
                            "forecast_date": test["forecast_date"].to_numpy(),
                            "plot": test["plot"].to_numpy(),
                            "heldout_plot": heldout_plot,
                            "target": target,
                            "model_name": model_name,
                            "observed": observed,
                            "predicted": predicted,
                            "source_value": test[target].to_numpy(),
                        }
                    )
                )
            fold_metrics = pd.DataFrame(fold_rows)
            comparison_rows.append(
                {
                    "target": target,
                    "model_name": model_name,
                    "mae": fold_metrics["mae"].mean(),
                    "rmse": fold_metrics["rmse"].mean(),
                    "r2": fold_metrics["r2"].mean(),
                    "heldout_sites": fold_metrics["heldout_plot"].nunique(),
                    "evaluation": "Macro-average leave-one-site-out",
                }
            )

    comparison = pd.DataFrame(comparison_rows)
    selections = []
    for target in targets:
        candidates = comparison[comparison["target"] == target].copy()
        best_mae = candidates["mae"].min()
        tied = candidates[candidates["mae"] <= best_mae * 1.01].copy()
        tied["complexity_order"] = tied["model_name"].map(MODEL_SELECTION_ORDER)
        selections.append(tied.sort_values(["complexity_order", "mae"]).iloc[0].drop(labels="complexity_order"))
    selected = pd.DataFrame(selections).reset_index(drop=True)
    predictions = pd.concat(prediction_frames, ignore_index=True)
    return comparison, predictions, selected


def _selected_permutation_importance(frame, selected_models, feature_columns, repeats):
    """Compute permutation importance only on the held-out portion of each fold."""
    rows = []
    splitter = LeaveOneGroupOut()
    for selection in selected_models.to_dict("records"):
        if selection["model_name"] == "Persistence":
            continue
        target = selection["target"]
        target_column = f"target_{target}"
        model_frame = frame.dropna(subset=[target_column, target]).copy()
        groups = model_frame["plot"]
        for train_index, test_index in splitter.split(model_frame, groups=groups):
            train = model_frame.iloc[train_index]
            test = model_frame.iloc[test_index]
            pipeline = _regression_pipeline(selection["model_name"], feature_columns, train)
            pipeline.fit(train[feature_columns], train[target_column])
            result = permutation_importance(
                pipeline,
                test[feature_columns],
                test[target_column],
                scoring="neg_mean_absolute_error",
                n_repeats=repeats,
                random_state=42,
                n_jobs=1,
            )
            rows.extend(
                {
                    "target": target,
                    "model_name": selection["model_name"],
                    "heldout_plot": test["plot"].iloc[0],
                    "feature": feature,
                    "mae_increase_mean": value,
                }
                for feature, value in zip(feature_columns, result.importances_mean)
            )
    detail_columns = ["target", "model_name", "heldout_plot", "feature", "mae_increase_mean"]
    detail = pd.DataFrame(rows, columns=detail_columns)
    if detail.empty:
        summary = pd.DataFrame(
            columns=["target", "model_name", "feature", "mae_increase_mean", "mae_increase_std", "heldout_sites"]
        )
        return detail, summary
    summary = (
        detail.groupby(["target", "model_name", "feature"], as_index=False)
        .agg(
            mae_increase_mean=("mae_increase_mean", "mean"),
            mae_increase_std=("mae_increase_mean", "std"),
            heldout_sites=("heldout_plot", "nunique"),
        )
        .sort_values(["target", "mae_increase_mean"], ascending=[True, False])
    )
    return detail, summary


def run_forecasting_workflow(
    raw_data,
    output_directory,
    targets=None,
    min_daily_observations=18,
    importance_repeats=5,
):
    """Run the daily suite, export reproducible artifacts, and fit final models."""
    output_directory = Path(output_directory)
    model_directory = output_directory / "models"
    output_directory.mkdir(parents=True, exist_ok=True)
    model_directory.mkdir(parents=True, exist_ok=True)
    daily_frame = build_daily_forecast_frame(raw_data, min_daily_observations=min_daily_observations)
    targets = list(targets or PARAMETER_NAMES.values())
    feature_columns = [
        column
        for column in daily_frame.columns
        if column not in {"plot", "date", "forecast_date"} and not column.startswith("target_")
    ]
    comparison, predictions, selected_models = run_daily_model_suite(
        daily_frame, targets=targets, feature_columns=feature_columns
    )
    site_metrics, site_variation = _heldout_site_metrics(predictions)
    importance_detail, importance_summary = _selected_permutation_importance(
        daily_frame, selected_models, feature_columns, importance_repeats
    )

    final_models = {}
    manifest_rows = []
    for selection in selected_models.to_dict("records"):
        target = selection["target"]
        model_frame = daily_frame.dropna(subset=[f"target_{target}", target]).copy()
        if selection["model_name"] == "Persistence":
            pipeline = PersistenceRegressor(target)
        else:
            pipeline = _regression_pipeline(selection["model_name"], feature_columns, model_frame)
        pipeline.fit(model_frame[feature_columns], model_frame[f"target_{target}"])
        model_path = model_directory / f"{target}.joblib"
        joblib.dump(pipeline, model_path)
        final_models[target] = pipeline
        manifest_rows.append(
            {
                **selection,
                "training_rows": len(model_frame),
                "training_start": model_frame["date"].min().date().isoformat(),
                "training_end": model_frame["date"].max().date().isoformat(),
                "feature_columns": ";".join(feature_columns),
                "model_path": str(model_path),
            }
        )
    manifest = pd.DataFrame(manifest_rows)

    selected_predictions = predictions.merge(
        selected_models[["target", "model_name"]], on=["target", "model_name"], how="inner"
    )
    soil_predictions = selected_predictions[selected_predictions["target"] == "soil_moisture"].copy()
    if soil_predictions.empty:
        soil_drydown_metrics = pd.DataFrame(columns=["condition", "mae", "rmse", "r2", "forecast_days"])
    else:
        soil_predictions["is_drying_next_day"] = soil_predictions["observed"] < soil_predictions["source_value"]
        soil_drydown_metrics = (
            soil_predictions.groupby("is_drying_next_day", as_index=False)
            .apply(
                lambda group: pd.Series(
                    {
                        "mae": mean_absolute_error(group["observed"], group["predicted"]),
                        "rmse": np.sqrt(mean_squared_error(group["observed"], group["predicted"])),
                        "r2": r2_score(group["observed"], group["predicted"]),
                        "forecast_days": len(group),
                    }
                )
            )
            .rename(columns={"is_drying_next_day": "condition"})
        )
        soil_drydown_metrics["condition"] = soil_drydown_metrics["condition"].map(
            {True: "Next-day drying", False: "Next-day recharge or stable"}
        )

    comparison.to_csv(output_directory / "daily_model_comparison.csv", index=False)
    predictions.to_csv(output_directory / "daily_heldout_predictions.csv", index=False)
    site_metrics.to_csv(output_directory / "daily_heldout_site_metrics.csv", index=False)
    site_variation.to_csv(output_directory / "daily_model_site_variation.csv", index=False)
    selected_models.to_csv(output_directory / "daily_selected_models.csv", index=False)
    manifest.to_csv(output_directory / "final_model_manifest.csv", index=False)
    importance_detail.to_csv(output_directory / "daily_heldout_permutation_importance.csv", index=False)
    importance_summary.to_csv(output_directory / "daily_feature_importance_summary.csv", index=False)
    soil_drydown_metrics.to_csv(output_directory / "daily_soil_moisture_drydown_metrics.csv", index=False)
    return {
        "daily_frame": daily_frame,
        "comparison": comparison,
        "predictions": predictions,
        "site_metrics": site_metrics,
        "site_variation": site_variation,
        "selected_models": selected_models,
        "importance": importance_summary,
        "manifest": manifest,
        "final_models": final_models,
        "feature_columns": feature_columns,
        "soil_drydown_metrics": soil_drydown_metrics,
        "output_directory": output_directory,
        "model_directory": model_directory,
    }


def build_hourly_forecast_frame(raw_data, targets=None):
    """Create one-hour-ahead rows for the supplementary hourly demonstration."""
    targets = list(targets or ["temperature", "relative_humidity", "vpd"])
    allowed_parameters = {parameter: signal for parameter, signal in PARAMETER_NAMES.items() if signal in targets}
    data = raw_data.copy()
    data["time"] = pd.to_datetime(data["time"], format="mixed", errors="coerce")
    data = data.dropna(subset=["time", "plot", "param", "value"])
    data = data[data["param"].isin(allowed_parameters)].copy()
    data["signal"] = data["param"].map(allowed_parameters)
    data["time"] = data["time"].dt.floor("h")
    group_columns = ["plot", "time", "signal"]
    if "ft" in data.columns:
        group_columns.insert(1, "ft")
    hourly = data.groupby(group_columns, as_index=False).agg(value=("value", "mean"))
    index_columns = ["plot", "time"]
    if "ft" in hourly.columns:
        index_columns.insert(1, "ft")
    values = hourly.pivot(index=index_columns, columns="signal", values="value").reset_index()
    for target in targets:
        if target not in values:
            values[target] = np.nan
    values = values.sort_values(["plot", "time"]).reset_index(drop=True)
    for target in targets:
        grouped = values.groupby("plot", sort=False)[target]
        values[f"{target}_lag_1h"] = grouped.shift(1)
        values[f"{target}_roll3h"] = grouped.transform(lambda series: series.rolling(3, min_periods=1).mean())
        values[f"{target}_roll24h"] = grouped.transform(lambda series: series.rolling(24, min_periods=1).mean())
        values[f"target_{target}"] = grouped.shift(-1)
    values["forecast_time"] = values.groupby("plot", sort=False)["time"].shift(-1)
    is_next_hour = values["forecast_time"].eq(values["time"] + pd.Timedelta(hours=1))
    for target in targets:
        values[f"target_{target}"] = values[f"target_{target}"].where(is_next_hour)
    values["hour_sin"] = np.sin(2 * np.pi * values["time"].dt.hour / 24)
    values["hour_cos"] = np.cos(2 * np.pi * values["time"].dt.hour / 24)
    values["day_of_year_sin"] = np.sin(2 * np.pi * values["time"].dt.dayofyear / 365.25)
    values["day_of_year_cos"] = np.cos(2 * np.pi * values["time"].dt.dayofyear / 365.25)
    return values


def run_hourly_demonstration(raw_data, selected_models, max_training_rows=10_000):
    """Return a fixed held-out-site, 24-hour visual forecast demonstration."""
    targets = ["temperature", "relative_humidity", "vpd"]
    hourly_frame = build_hourly_forecast_frame(raw_data, targets=targets)
    valid_counts = hourly_frame.dropna(subset=[f"target_{target}" for target in targets]).groupby("plot").size()
    demo_plot = valid_counts.idxmax()
    feature_columns = [
        column
        for column in hourly_frame.columns
        if column not in {"plot", "time", "forecast_time"} and not column.startswith("target_")
    ]
    prediction_frames = []
    for target in targets:
        selection = selected_models[selected_models["target"] == target]
        if selection.empty:
            continue
        model_name = selection.iloc[0]["model_name"]
        target_column = f"target_{target}"
        training = hourly_frame[(hourly_frame["plot"] != demo_plot) & hourly_frame[target_column].notna()].copy()
        training = training.sort_values("time")
        if len(training) > max_training_rows:
            per_plot = max_training_rows // training["plot"].nunique()
            training = training.groupby("plot", group_keys=False).tail(per_plot)
        testing = hourly_frame[(hourly_frame["plot"] == demo_plot) & hourly_frame[target_column].notna()].copy()
        if model_name == "Persistence":
            pipeline = PersistenceRegressor(target)
        else:
            pipeline = _regression_pipeline(model_name, feature_columns, training)
        pipeline.fit(training[feature_columns], training[target_column])
        testing["predicted"] = pipeline.predict(testing[feature_columns])
        testing["target"] = target
        testing["model_name"] = model_name
        prediction_frames.append(
            testing[["time", "forecast_time", "plot", "target", "model_name", target_column, "predicted"]]
            .rename(columns={target_column: "observed"})
            .tail(24)
        )
    predictions = pd.concat(prediction_frames, ignore_index=True)
    return hourly_frame, predictions, demo_plot


def save_forecasting_figures(result, hourly_predictions):
    """Save concise comparison, importance, soil-drying, and hourly demonstration figures."""
    output_directory = result["output_directory"]
    comparison = result["comparison"]
    targets = result["selected_models"]["target"].tolist()
    figure, axes = plt.subplots(len(targets), 1, figsize=(11, 3.2 * len(targets)))
    axes = np.atleast_1d(axes)
    for axis, target in zip(axes, targets):
        plot_data = comparison[comparison["target"] == target].sort_values("mae")
        colors = np.where(plot_data["model_name"].eq("Persistence"), "#bab0ac", "#4c78a8")
        axis.barh(plot_data["model_name"], plot_data["mae"], color=colors)
        axis.invert_yaxis()
        axis.set_title(f"{target.replace('_', ' ').title()}: held-out-site MAE")
        axis.set_xlabel("Macro-average MAE (lower is better)")
        axis.grid(axis="x", alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_directory / "daily_model_comparison.png", dpi=180, bbox_inches="tight")
    plt.close(figure)

    importance = result["importance"]
    figure, axes = plt.subplots(len(targets), 1, figsize=(11, 3.0 * len(targets)))
    axes = np.atleast_1d(axes)
    for axis, target in zip(axes, targets):
        plot_data = importance[importance["target"] == target].nlargest(8, "mae_increase_mean")
        if plot_data.empty:
            axis.text(0.5, 0.5, "Persistence selected; feature importance does not apply", ha="center", va="center")
            axis.set_axis_off()
            continue
        axis.barh(plot_data["feature"].str.replace("_", " "), plot_data["mae_increase_mean"], color="#59a14f")
        axis.invert_yaxis()
        axis.set_title(f"{target.replace('_', ' ').title()}: held-out permutation importance")
        axis.set_xlabel("Mean MAE increase after permutation")
        axis.grid(axis="x", alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_directory / "daily_feature_importance.png", dpi=180, bbox_inches="tight")
    plt.close(figure)

    selected_predictions = result["predictions"].merge(
        result["selected_models"][["target", "model_name"]], on=["target", "model_name"], how="inner"
    )
    soil = selected_predictions[selected_predictions["target"] == "soil_moisture"].copy()
    if not soil.empty:
        figure, axis = plt.subplots(figsize=(8, 6))
        drying = soil["observed"] < soil["source_value"]
        axis.scatter(soil.loc[~drying, "observed"], soil.loc[~drying, "predicted"], alpha=0.45, label="Recharge or stable")
        axis.scatter(soil.loc[drying, "observed"], soil.loc[drying, "predicted"], alpha=0.6, label="Next-day drying")
        limits = [min(soil["observed"].min(), soil["predicted"].min()), max(soil["observed"].max(), soil["predicted"].max())]
        axis.plot(limits, limits, "--", color="#333333", label="Perfect forecast")
        axis.set_xlabel("Observed next-day soil moisture")
        axis.set_ylabel("Predicted next-day soil moisture")
        axis.set_title("Soil-moisture forecast performance during drying periods")
        axis.legend()
        axis.grid(alpha=0.25)
        figure.tight_layout()
        figure.savefig(output_directory / "daily_soil_moisture_drydown_forecast.png", dpi=180, bbox_inches="tight")
        plt.close(figure)

    if not hourly_predictions.empty:
        hourly_targets = hourly_predictions["target"].unique()
        figure, axes = plt.subplots(len(hourly_targets), 1, figsize=(12, 3.2 * len(hourly_targets)), sharex=True)
        axes = np.atleast_1d(axes)
        for axis, target in zip(axes, hourly_targets):
            plot_data = hourly_predictions[hourly_predictions["target"] == target].sort_values("forecast_time")
            axis.plot(plot_data["forecast_time"], plot_data["observed"], marker="o", label="Observed")
            axis.plot(plot_data["forecast_time"], plot_data["predicted"], marker="o", label="Forecast")
            axis.set_title(f"Illustrative hourly forecast: {target.replace('_', ' ').title()}")
            axis.set_ylabel(target.replace("_", " "))
            axis.grid(alpha=0.25)
            axis.legend()
        figure.tight_layout()
        figure.savefig(output_directory / "hourly_forecast_demonstration.png", dpi=180, bbox_inches="tight")
        plt.close(figure)
