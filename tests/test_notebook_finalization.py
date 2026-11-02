import unittest
from pathlib import Path

import nbformat


NOTEBOOK_PATH = Path(__file__).resolve().parents[1] / "notebooks" / "clean_microclimate.ipynb"


class NotebookFinalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)

    @classmethod
    def source(cls, cell_id):
        return next(cell.source for cell in cls.notebook.cells if cell.get("id") == cell_id)

    def test_declares_hard_cleaned_data_as_the_primary_analysis_dataset(self):
        source = self.source("1308d1a8")
        self.assertIn("df_hard_clean = df_clean.copy()", source)
        self.assertIn("df_analysis_screened", source)
        self.assertIn("df = df_hard_clean.copy()", source)
        self.assertIn("Primary EDA and modelling dataset", source)
        self.assertIn("Sensitivity check only", source)

    def test_forecast_coverage_is_saved_for_reporting(self):
        source = self.source("daily-microclimate-forecasting-code")
        self.assertIn("daily_forecast_target_coverage.csv", source)

    def test_forecast_coverage_cell_is_valid_python(self):
        compile(self.source("daily-microclimate-forecasting-code"), "forecasting-cell", "exec")

    def test_notebook_creates_output_directories_from_a_clean_checkout(self):
        source = self.source("06aec44a")
        self.assertIn("PROCESSED_DATA_PATH.mkdir(parents=True, exist_ok=True)", source)
        self.assertIn("OUT_ROOT.mkdir(parents=True, exist_ok=True)", source)

    def test_comparative_and_drydown_analyses_prefer_primary_dataset(self):
        comparative = self.source("711cff48")
        drydown = self.source("8a08251a")
        self.assertLess(comparative.index("if 'df' in globals()"), comparative.index("elif 'df_hard_clean'"))
        self.assertLess(drydown.index("if 'df' in globals()"), drydown.index("elif 'df_hard_clean'"))

    def test_temporal_model_selection_allows_persistence_to_win(self):
        source = self.source("temporal-regression-holdout")
        self.assertIn("MODEL_SELECTION_ORDER", source)
        self.assertNotIn("model_name'] != 'Persistence'", source)
        self.assertIn("if selected_regression == 'Persistence'", source)

    def test_relationship_analysis_uses_block_bootstrap(self):
        source = self.source("beea00c1")
        self.assertIn("block_spearman_table", source)
        self.assertIn("block_days=14", source)
        self.assertNotIn("spearman_p", source)

    def test_plot_is_documented_as_audit_field_not_a_model_feature(self):
        source = self.source("c0ee5cb3")
        self.assertNotIn("| Plot identifier |", source)
        self.assertIn("excluded from the classifier feature matrix", source)

    def test_repeats_principal_results_across_both_data_tiers(self):
        source = self.source("screening-robustness-analysis")
        self.assertIn("run_screening_robustness", source)
        self.assertIn("df_hard_clean", source)
        self.assertIn("df_analysis_screened", source)
        manifest = self.source("reproducibility-manifest")
        self.assertIn("screening_label_agreement", manifest)
        self.assertIn("screening_regression_comparison", manifest)

    def test_loso_is_described_as_an_exploratory_benchmark(self):
        source = self.source("daily-microclimate-forecasting-interpretation")
        self.assertIn("exploratory benchmark", source)
        self.assertIn("same seven folds", source)
        self.assertIn("not confidence intervals", source)

    def test_final_wording_does_not_claim_tree_stress_or_calibrated_thresholds(self):
        vpd_notes = self.source("7abecb76")
        robustness_notes = self.source("screening-robustness-notes")
        self.assertIn("not measured tree-stress events", vpd_notes)
        self.assertNotIn("StressDays", vpd_notes)
        self.assertIn("not externally calibrated", robustness_notes)

    def test_manifest_has_one_robustness_block_and_site_variation_output(self):
        manifest = self.source("reproducibility-manifest")
        self.assertEqual(manifest.count("'screening_robustness': {"), 1)
        self.assertIn("regression_site_variation", manifest)
        self.assertNotIn("regression_site_uncertainty", manifest)


if __name__ == "__main__":
    unittest.main()
