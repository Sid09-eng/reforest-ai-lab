"""Add the final screening-robustness section and cautious interpretation."""

from pathlib import Path

import nbformat


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "clean_microclimate.ipynb"


def main():
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    ids = {cell.get("id") for cell in notebook.cells}

    # The distribution cells must create the files that the following display cells embed.
    distribution_outputs = {
        "d15e59db": "temperature/temp_A_daily_mean_faceted.png",
        "bfd91d3d": "rh/rh_A_daily_mean_faceted.png",
        "7cfe6bd3": "vpd/vpd_A_daily_mean_faceted.png",
        "7e378396": "par/par_A_daily_mean_faceted.png",
        "73d4ca0e": "soil/soil_A_daily_mean_faceted.png",
    }
    for cell_id, relative_path in distribution_outputs.items():
        cell = next(cell for cell in notebook.cells if cell.get("id") == cell_id)
        if relative_path not in cell.source:
            save_lines = (
                f"distribution_figure_path = Path(OUT_ROOT) / '{relative_path}'\n"
                "distribution_figure_path.parent.mkdir(parents=True, exist_ok=True)\n"
                "fig.savefig(distribution_figure_path, dpi=180, bbox_inches='tight')\n"
            )
            cell.source = cell.source.replace("plt.tight_layout()\nplt.show()", f"plt.tight_layout()\n{save_lines}plt.show()")

    soil_gallery = next(cell for cell in notebook.cells if cell.get("id") == "645de69d")
    soil_gallery.source = soil_gallery.source.replace(
        "soil_moisture/soil_F_normalized_drydown_curves.png",
        "soil_moisture/soil_G_normalized_drydown_curves.png",
    )
    manifest_index = next(i for i, cell in enumerate(notebook.cells) if cell.get("id") == "reproducibility-manifest")

    robustness_markdown = nbformat.v4.new_markdown_cell(
        """### 8.8 Do the screening rules change the main conclusions?

The first sensitivity check compared daily means. This stricter check repeats the VPD labels, time-aware correlations, VPD-state classification, and chronological regression on both the hard-cleaned and analysis-screened tiers. It is included because saturated RH and zero VPD can be real humid conditions as well as possible sensor issues.

The comparison is descriptive: close results support robustness to the screening policy, while changes identify conclusions that should be reported with caution.""",
        id="screening-robustness-notes",
    )
    robustness_code = nbformat.v4.new_code_cell(
        """# Repeat the principal readiness analyses on both data tiers.
from scripts.microclimate_sensitivity import run_screening_robustness

ROBUSTNESS_OUT = Path(OUT_ROOT) / 'screening_robustness'
screening_robustness = run_screening_robustness(
    df_hard_clean,
    df_analysis_screened,
    ROBUSTNESS_OUT,
    n_bootstrap=300,
)

label_check = screening_robustness['label_summary']
correlation_check = screening_robustness['correlation_comparison']
classifier_check = screening_robustness['classifier_metrics']
regression_check = screening_robustness['regression_metrics']

agreement_pct = 100 * label_check.loc[0, 'agreement_rate']
largest_rho_change = correlation_check['screened_minus_hard_cleaned'].abs().max()
print(f'VPD-state agreement after screening: {agreement_pct:.1f}% of paired plot-days.')
print(f'Largest absolute change in a within-plot Spearman effect: {largest_rho_change:.3f}.')
print('Values close to the main result indicate robustness; larger differences should be reported as screening-sensitive.')

print('VPD label agreement:')
display(label_check.round(4))
print('Correlation comparison:')
display(correlation_check.round(4))
print('Final-period VPD classifier comparison:')
display(classifier_check.round(4))
print('Final-period regression comparison:')
display(regression_check.round(4))
display(Image(filename=str(screening_robustness['figure_path'])))""",
        id="screening-robustness-analysis",
    )
    if "screening-robustness-analysis" not in ids:
        notebook.cells[manifest_index:manifest_index] = [robustness_markdown, robustness_code]

    for cell in notebook.cells:
        if cell.cell_type != "markdown":
            continue
        replacements = {
            "### 8.8 Reproducibility manifest": "### 8.9 Reproducibility manifest",
            "### 8.9 Saved outputs and limits": "### 8.10 Saved outputs and limits",
            "which is why it does not look as buffered as `FT4MR`": "which is why its recorded range is wider than `FT4MR`",
            "Taken together, the temperature plots show a clear difference across the monitored plots rather than a random site effect. `UP2` behaves like the most heat-exposed site, `US5` is still open but somewhat moderated, and the FT4 sites remain the most buffered overall. So the main conclusion here is that canopy cover is already leaving a strong temperature signature before we even move to the later comparative time-series section.": "Taken together, the temperature plots show clear differences across the monitored plots. `UP2` recorded the warmest and widest distribution, while the FT4 plots were generally cooler and less variable. These differences are consistent with the site descriptions, but this observational dataset cannot separate canopy effects from sensor placement and other local conditions.",
            "FT4 (primary): ~85-96%, tightest spread (canopy buffering).": "FT4 (primary): ~85-96%, with the tightest recorded spread.",
            "so it is humid overall without being as buffered as FT4": "so it is humid overall but more variable than FT4",
            "which suggests a more stable humid background than FT1 but not full saturation buffering": "which records a more stable humid background than FT1 without the same saturation frequency",
            "`FT4MR` is the clearest buffered site here. Its IQR is **91.51-97.09%**, the median is **94.66%**, and the violin is compressed high in the range, which is exactly what we expect under strong canopy control.": "`FT4MR` has the highest and narrowest RH distribution here. Its IQR is **91.51-97.09%** and its median is **94.66%**. Canopy may contribute, but the plot comparison alone cannot establish that cause.",
            "`FT4MR` is again the tightest buffered site.": "`FT4MR` again has the tightest low-VPD distribution.",
            "`UP2` is the driest-demand site, `FT4MR` is the most buffered": "`UP2` records the highest atmospheric demand and `FT4MR` the lowest",
            "That makes VPD one of the most useful variables for linking canopy structure to later soil-moisture behaviour.": "That makes VPD useful for comparing atmospheric demand with later soil-moisture behaviour, without treating canopy as a confirmed cause.",
            "which matches repeated open-canopy exposure": "which is consistent with its more open site description",
            "which supports the idea of a gap, edge effect, or partial exposure around that sensor position": "which is consistent with a gap, edge, or different sensor position, although the data cannot distinguish these explanations",
            "PAR is the clearest structural variable in the exploratory set.": "PAR gives the clearest separation among plots in the exploratory set.",
            "it behaves more like a partially exposed site than a deeply buffered FT4 interior": "its recorded light distribution resembles the brighter plots more than the other FT4 plots",
            "tightest spread (buffered soils)": "tightest recorded spread",
            "`FT4MR`, in contrast, is the cleanest buffered wet site": "`FT4MR`, in contrast, has the highest and least variable soil-moisture distribution",
            "`FT4MR` is clearly the wettest and most buffered": "`FT4MR` records the highest and least variable soil moisture",
            "That makes soil moisture the first variable here where local site conditions start to matter as much as broad forest-type class.": "This shows that plot-level differences remain important even within the same forest-type class.",
            "that suggests a more local canopy or exposure effect": "that is consistent with a local site or sensor-specific effect",
            "it shows the same exposure pattern from the opposite side": "it shows a similar ordering across plots from the opposite side",
            "identify canopy openness, gap influence, and sites where light may help explain": "identify light-distribution differences and sites where PAR is associated with",
            "the more buffered FT4 sites": "the less variable FT4 sites",
            "which fits its more buffered drydown behaviour": "which matches its less variable drydown record",
        }
        for old, new in replacements.items():
            cell.source = cell.source.replace(old, new)

    manifest = next(cell for cell in notebook.cells if cell.get("id") == "reproducibility-manifest")
    if "'regression_heldout_site_metrics':" not in manifest.source:
        manifest.source = manifest.source.replace(
            "'regression_temporal_final_test': 'outputs/redesigned/forecasting/daily_temporal_final_test_metrics.csv',",
            "'regression_temporal_final_test': 'outputs/redesigned/forecasting/daily_temporal_final_test_metrics.csv',\n        'regression_heldout_site_metrics': 'outputs/redesigned/forecasting/daily_heldout_site_metrics.csv',\n        'regression_site_variation': 'outputs/redesigned/forecasting/daily_model_site_variation.csv',\n        'screening_label_agreement': 'outputs/redesigned/screening_robustness/tier_vpd_label_agreement.csv',\n        'screening_correlation_comparison': 'outputs/redesigned/screening_robustness/tier_correlation_comparison.csv',\n        'screening_classifier_comparison': 'outputs/redesigned/screening_robustness/tier_vpd_classifier_metrics.csv',\n        'screening_regression_comparison': 'outputs/redesigned/screening_robustness/tier_temporal_regression_metrics.csv',\n        'screening_robustness_figure': 'outputs/redesigned/screening_robustness/screening_robustness_summary.png',",
        )
    if "'screening_robustness': {" not in manifest.source:
        manifest.source = manifest.source.replace(
            "'outputs': {",
            "'screening_robustness': {\n        'vpd_label_agreement': label_check.to_dict(orient='records'),\n        'classifier_metrics': classifier_check.to_dict(orient='records'),\n        'temporal_regression_metrics': regression_check.to_dict(orient='records'),\n    },\n    'outputs': {",
        )

    nbformat.write(notebook, NOTEBOOK)
    print(f"Updated {NOTEBOOK} ({len(notebook.cells)} cells)")


if __name__ == "__main__":
    main()
