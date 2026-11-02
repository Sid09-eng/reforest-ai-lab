import unittest

import numpy as np
import pandas as pd


class MovingBlockCorrelationTests(unittest.TestCase):
    def test_truncates_blocks_at_end_of_series_instead_of_wrapping(self):
        from scripts.microclimate_statistics import non_circular_block_positions

        positions = non_circular_block_positions(
            series_length=5,
            block_days=3,
            starts=np.array([4, 1]),
        )

        np.testing.assert_array_equal(positions, np.array([4, 1, 2, 3]))

    def test_returns_positive_within_plot_effect_and_interval(self):
        from scripts.microclimate_statistics import moving_block_spearman

        rows = []
        for plot_index, plot in enumerate(["A", "B", "C"]):
            for day in range(60):
                x = day + plot_index * 0.1
                rows.append(
                    {
                        "plot": plot,
                        "date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=day),
                        "x": x,
                        "y": 2 * x + np.sin(day / 5),
                    }
                )

        result = moving_block_spearman(
            pd.DataFrame(rows), "x", "y", block_days=7, n_bootstrap=120, random_state=42
        )

        self.assertEqual(result["plots"], 3)
        self.assertGreater(result["within_plot_median_rho"], 0.95)
        self.assertGreater(result["ci_low"], 0.9)
        self.assertLessEqual(result["ci_high"], 1.0)

    def test_rejects_frames_without_required_columns(self):
        from scripts.microclimate_statistics import moving_block_spearman

        with self.assertRaisesRegex(ValueError, "missing required columns"):
            moving_block_spearman(pd.DataFrame({"x": [1], "y": [2]}), "x", "y")


if __name__ == "__main__":
    unittest.main()
