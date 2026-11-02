import json
import unittest
from pathlib import Path


class DrydownModelingContractTests(unittest.TestCase):
    def test_compares_requested_models_and_exports_heldout_importance(self):
        notebook_path = Path(__file__).resolve().parents[1] / "notebooks" / "clean_microclimate.ipynb"
        notebook = json.loads(notebook_path.read_text())
        correlation_index = next(
            index
            for index, cell in enumerate(notebook["cells"])
            if "# Part 8: Correlation matrices" in "".join(cell["source"])
        )
        extension_index, source = next(
            (index, "".join(cell["source"]))
            for index, cell in enumerate(notebook["cells"])
            if "run_drydown_model_suite" in "".join(cell["source"])
        )

        self.assertGreater(
            extension_index,
            correlation_index,
            "The predictive modelling suite must appear after correlation analysis.",
        )

        for expected_fragment in (
            "RandomForestRegressor",
            "HistGradientBoostingRegressor",
            "permutation_importance",
            "soil_logo_permutation_importance.csv",
            "soil_logo_feature_importance_summary.csv",
        ):
            self.assertIn(expected_fragment, source)


if __name__ == "__main__":
    unittest.main()
