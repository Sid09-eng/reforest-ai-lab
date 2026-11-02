import unittest
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd


class DailyForecastFrameTests(unittest.TestCase):
    def test_builds_next_day_targets_from_mixed_timestamps_without_future_features(self):
        from scripts.microclimate_forecasting import build_daily_forecast_frame

        raw = pd.DataFrame(
            {
                "time": [
                    "2025-01-01",
                    "2025-01-01 12:00:00",
                    "2025-01-02 00:00:00",
                    "2025-01-02 12:00:00",
                    "2025-01-03 00:00:00",
                    "2025-01-03 12:00:00",
                ],
                "plot": ["A"] * 6,
                "ft": ["FT1"] * 6,
                "param": ["temp"] * 6,
                "value": [20.0, 22.0, 24.0, 26.0, 28.0, 30.0],
            }
        )

        frame = build_daily_forecast_frame(raw, min_daily_observations=2)
        first_day = frame.loc[frame["date"] == pd.Timestamp("2025-01-01")].iloc[0]

        self.assertEqual(first_day["temperature"], 21.0)
        self.assertEqual(first_day["target_temperature"], 25.0)
        self.assertEqual(first_day["forecast_date"], pd.Timestamp("2025-01-02"))
        self.assertTrue(pd.isna(first_day["temperature_lag_1"]))
        self.assertEqual(first_day["temperature_roll3"], 21.0)


class DailyModelSelectionTests(unittest.TestCase):
    def test_compares_requested_models_and_selects_one_daily_winner_per_target(self):
        from scripts.microclimate_forecasting import run_daily_model_suite

        rows = []
        for plot_index, plot in enumerate(["A", "B", "C"]):
            for day in range(12):
                temperature = 20 + plot_index + day * 0.5
                rows.append(
                    {
                        "plot": plot,
                        "ft": f"FT{plot_index + 1}",
                        "date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=day),
                        "forecast_date": pd.Timestamp("2025-01-02") + pd.Timedelta(days=day),
                        "temperature": temperature,
                        "temperature_lag_1": temperature - 0.5,
                        "temperature_roll3": temperature - 0.25,
                        "day_of_year_sin": 0.1,
                        "day_of_year_cos": 0.9,
                        "target_temperature": temperature + 0.5,
                    }
                )
        frame = pd.DataFrame(rows)

        comparison, predictions, selected = run_daily_model_suite(
            frame,
            targets=["temperature"],
            feature_columns=[
                "ft",
                "temperature",
                "temperature_lag_1",
                "temperature_roll3",
                "day_of_year_sin",
                "day_of_year_cos",
            ],
        )

        self.assertEqual(
            set(comparison["model_name"]),
            {"Persistence", "Ridge", "Elastic net", "Random forest", "Extra trees", "Histogram gradient boosting"},
        )
        self.assertEqual(set(predictions["heldout_plot"]), {"A", "B", "C"})
        self.assertEqual(selected.shape[0], 1)
        self.assertEqual(selected.loc[0, "target"], "temperature")

    def test_selects_persistence_when_it_has_the_lowest_validation_mae(self):
        from scripts.microclimate_forecasting import run_daily_model_suite

        rows = []
        for plot_index, plot in enumerate(["A", "B", "C"]):
            for day in range(10):
                current = 20.0 + plot_index
                rows.append(
                    {
                        "plot": plot,
                        "ft": f"FT{plot_index + 1}",
                        "date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=day),
                        "forecast_date": pd.Timestamp("2025-01-02") + pd.Timedelta(days=day),
                        "temperature": current,
                        "temperature_lag_1": current,
                        "target_temperature": current,
                    }
                )
        frame = pd.DataFrame(rows)

        _, _, selected = run_daily_model_suite(
            frame,
            targets=["temperature"],
            feature_columns=["ft", "temperature", "temperature_lag_1"],
        )

        self.assertEqual(selected.loc[0, "model_name"], "Persistence")

    def test_excludes_rows_without_current_target_so_persistence_predictions_are_finite(self):
        from scripts.microclimate_forecasting import run_daily_model_suite

        frame = pd.DataFrame(
            [
                {
                    "plot": plot,
                    "ft": "FT1",
                    "date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=day),
                    "forecast_date": pd.Timestamp("2025-01-02") + pd.Timedelta(days=day),
                    "temperature": np.nan if plot == "A" and day == 2 else 20 + day,
                    "temperature_lag_1": 19 + day,
                    "target_temperature": 21 + day,
                }
                for plot in ["A", "B", "C"]
                for day in range(6)
            ]
        )

        _, predictions, _ = run_daily_model_suite(
            frame,
            targets=["temperature"],
            feature_columns=["ft", "temperature", "temperature_lag_1"],
        )

        self.assertFalse(predictions["predicted"].isna().any())

    def test_treats_pandas_string_forest_type_as_a_categorical_feature(self):
        from scripts.microclimate_forecasting import run_daily_model_suite

        frame = pd.DataFrame(
            [
                {
                    "plot": plot,
                    "ft": f"FT{site_index + 1}",
                    "date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=day),
                    "forecast_date": pd.Timestamp("2025-01-02") + pd.Timedelta(days=day),
                    "temperature": 20 + site_index + day,
                    "temperature_lag_1": 19 + site_index + day,
                    "target_temperature": 21 + site_index + day,
                }
                for site_index, plot in enumerate(["A", "B", "C"])
                for day in range(6)
            ]
        )
        frame["ft"] = frame["ft"].astype("string")

        comparison, _, _ = run_daily_model_suite(
            frame,
            targets=["temperature"],
            feature_columns=["ft", "temperature", "temperature_lag_1"],
        )

        self.assertEqual(comparison["heldout_sites"].max(), 3)


class ForecastingExportTests(unittest.TestCase):
    def test_exports_reloadable_final_model_and_heldout_artifacts(self):
        from scripts.microclimate_forecasting import run_forecasting_workflow

        rows = []
        for plot_index, plot in enumerate(["A", "B", "C"]):
            for day in range(14):
                for hour, value in [(0, 20 + plot_index + day), (12, 22 + plot_index + day)]:
                    rows.append(
                        {
                            "time": pd.Timestamp("2025-01-01") + pd.Timedelta(days=day, hours=hour),
                            "plot": plot,
                            "ft": f"FT{plot_index + 1}",
                            "param": "temp",
                            "value": value,
                        }
                    )
        with TemporaryDirectory() as temporary_directory:
            result = run_forecasting_workflow(
                pd.DataFrame(rows),
                temporary_directory,
                targets=["temperature"],
                min_daily_observations=2,
                importance_repeats=2,
            )

            output_directory = pd.Path(temporary_directory) if hasattr(pd, "Path") else None
            self.assertEqual(result["selected_models"].shape[0], 1)
            self.assertTrue(result["importance"]["heldout_sites"].eq(3).all())
            self.assertTrue((result["output_directory"] / "daily_model_comparison.csv").exists())
            self.assertTrue((result["output_directory"] / "daily_heldout_site_metrics.csv").exists())
            self.assertTrue((result["output_directory"] / "daily_model_site_variation.csv").exists())
            self.assertTrue((result["output_directory"] / "final_model_manifest.csv").exists())
            self.assertTrue((result["model_directory"] / "temperature.joblib").exists())
            self.assertEqual(result["site_metrics"]["heldout_plot"].nunique(), 3)
            prediction = result["final_models"]["temperature"].predict(
                result["daily_frame"].loc[:, result["feature_columns"]].head(1)
            )
            self.assertEqual(len(prediction), 1)


class HourlyDemonstrationTests(unittest.TestCase):
    def test_builds_one_hour_ahead_rows_for_hourly_visual_demonstration(self):
        from scripts.microclimate_forecasting import build_hourly_forecast_frame

        raw = pd.DataFrame(
            {
                "time": [
                    "2025-01-01 00:00:00",
                    "2025-01-01 01:00:00",
                    "2025-01-01 02:00:00",
                ],
                "plot": ["A"] * 3,
                "ft": ["FT1"] * 3,
                "param": ["rh"] * 3,
                "value": [70.0, 72.0, 74.0],
            }
        )

        frame = build_hourly_forecast_frame(raw, targets=["relative_humidity"])
        first_hour = frame.iloc[0]

        self.assertEqual(first_hour["relative_humidity"], 70.0)
        self.assertEqual(first_hour["target_relative_humidity"], 72.0)
        self.assertEqual(first_hour["forecast_time"], pd.Timestamp("2025-01-01 01:00:00"))
        self.assertTrue(pd.isna(first_hour["relative_humidity_lag_1h"]))


class NotebookIntegrationTests(unittest.TestCase):
    def test_forecasting_cell_converts_existing_output_root_to_path(self):
        import json
        from pathlib import Path

        notebook_path = Path(__file__).resolve().parents[1] / "notebooks" / "clean_microclimate.ipynb"
        notebook = json.loads(notebook_path.read_text())
        source = next(
            "".join(cell["source"])
            for cell in notebook["cells"]
            if "run_forecasting_workflow" in "".join(cell.get("source", []))
        )

        self.assertIn("Path(OUT_ROOT) / 'forecasting'", source)

    def test_forecasting_interpretation_explains_training_and_heldout_evaluation(self):
        import json
        from pathlib import Path

        notebook_path = Path(__file__).resolve().parents[1] / "notebooks" / "clean_microclimate.ipynb"
        notebook = json.loads(notebook_path.read_text())
        source = next(
            "".join(cell["source"])
            for cell in notebook["cells"]
            if cell.get("id") == "daily-microclimate-forecasting-interpretation"
        )

        self.assertIn("What the code cell above does", source)
        self.assertIn("How models are tested", source)
        self.assertIn("leave-one-site-out", source)
        self.assertIn("held-out", source)
        self.assertIn("persistence baseline", source)

    def test_notebook_has_an_embedded_forecasting_figure_gallery(self):
        import json
        from pathlib import Path

        notebook_path = Path(__file__).resolve().parents[1] / "notebooks" / "clean_microclimate.ipynb"
        notebook = json.loads(notebook_path.read_text())
        source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])

        self.assertIn("### 7.4 Forecasting figures", source)
        for filename in [
            "daily_model_comparison.png",
            "daily_feature_importance.png",
            "daily_soil_moisture_drydown_forecast.png",
            "hourly_forecast_demonstration.png",
        ]:
            self.assertIn(filename, source)
        self.assertIn("IPython.display import Image, display", source)


if __name__ == "__main__":
    unittest.main()
