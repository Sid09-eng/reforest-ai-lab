import unittest

import numpy as np
import pandas as pd


class ScreeningSensitivityTests(unittest.TestCase):
    def test_vpd_label_agreement_detects_threshold_crossings(self):
        from scripts.microclimate_sensitivity import compare_vpd_labels

        hard_clean = pd.DataFrame(
            {
                "plot": ["A", "A", "B"],
                "date": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-01"]),
                "vpd": [0.19, 0.51, 0.90],
            }
        )
        screened = hard_clean.copy()
        screened.loc[0, "vpd"] = 0.21

        summary, transitions = compare_vpd_labels(hard_clean, screened)

        self.assertEqual(summary.loc[0, "paired_plot_days"], 3)
        self.assertAlmostEqual(summary.loc[0, "agreement_rate"], 2 / 3)
        changed = transitions[transitions["hard_clean_state"] != transitions["screened_state"]]
        self.assertEqual(len(changed), 1)

    def test_temporal_sensitivity_keeps_persistence_eligible(self):
        from scripts.microclimate_sensitivity import evaluate_temporal_regression

        rows = []
        for plot_index, plot in enumerate(["A", "B", "C"]):
            for day in range(30):
                value = 20.0 + plot_index
                rows.append(
                    {
                        "plot": plot,
                        "ft": f"FT{plot_index + 1}",
                        "date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=day),
                        "forecast_date": pd.Timestamp("2025-01-02") + pd.Timedelta(days=day),
                        "temperature": value,
                        "temperature_lag_1": value,
                        "target_temperature": value,
                    }
                )
        final, validation, split = evaluate_temporal_regression(
            pd.DataFrame(rows), targets=["temperature"], feature_columns=["ft", "temperature", "temperature_lag_1"]
        )

        self.assertEqual(final.loc[0, "selected_model"], "Persistence")
        self.assertIn("Persistence", set(validation["model_name"]))
        self.assertEqual(set(split["split"]), {"train", "validation", "final_test"})


if __name__ == "__main__":
    unittest.main()
