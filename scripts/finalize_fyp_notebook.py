"""Apply the examiner-driven final analysis revisions to the FYP notebook."""

from pathlib import Path

import nbformat


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "clean_microclimate.ipynb"


def cell_by_id(notebook, cell_id):
    return next(cell for cell in notebook.cells if cell.get("id") == cell_id)


def replace_once(source, old, new):
    matches = source.count(old)
    if matches == 1:
        return source.replace(old, new)
    if matches == 0 and new in source:
        return source
    raise ValueError(f"Expected one notebook source match, found {matches}: {old[:80]}")


def main():
    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)

    cell_by_id(notebook, "58f7288f").source = """## 1. Data quality and analysis datasets

The cleaning stage separates confirmed invalid records from readings that only look unusual. Confirmed invalid rows are removed. Suspected sensor issues are retained with traceable reasons in the hard-cleaned dataset, which is the primary dataset for EDA and modelling. The stricter screened tier is used only as a sensitivity check."""

    cell_by_id(notebook, "1308d1a8").source = """# Keep each data tier explicit so every result has a clear input dataset.
df_hard_clean = df_clean.copy()
df_analysis_screened = df_clean.loc[~df_clean['quality_flag']].copy().reset_index(drop=True)
df = df_hard_clean.copy()

data_tier_summary = pd.DataFrame([
    {'data_tier': 'Raw', 'rows': len(df_raw), 'purpose': 'Source audit only'},
    {'data_tier': 'Hard-cleaned', 'rows': len(df_hard_clean), 'purpose': 'Primary EDA and modelling dataset; flags retained for audit'},
    {'data_tier': 'Analysis-screened', 'rows': len(df_analysis_screened), 'purpose': 'Sensitivity check only'},
])
display(data_tier_summary)
print(f"Primary analysis dataframe: {len(df):,} hard-cleaned rows, including {df_hard_clean['quality_flag'].sum():,} traceably flagged readings.")"""

    tier_markdown = nbformat.v4.new_markdown_cell(
        """### 1.2 Does sensor screening change the daily patterns?

The primary analysis retains review-flagged readings because some flags may be real weather conditions. The table and plot below compare the hard-cleaned primary tier with the stricter screened sensitivity tier. Large differences would mean the conclusions depend on the screening rules.""",
        id="data-tier-sensitivity-notes",
    )
    tier_code = nbformat.v4.new_code_cell(
        """# Compare daily means from the hard-cleaned and analysis-screened tiers.
QUALITY_OUT = Path(OUT_ROOT) / 'quality'
QUALITY_OUT.mkdir(parents=True, exist_ok=True)

def daily_tier(frame, name):
    daily = (
        frame.assign(date=pd.to_datetime(frame['time']).dt.normalize())
        .groupby(['plot', 'date', 'param'], as_index=False)
        .agg(daily_mean=('value', 'mean'), observations=('value', 'size'))
    )
    return daily.rename(columns={'daily_mean': f'{name}_daily_mean', 'observations': f'{name}_observations'})

hard_daily = daily_tier(df_hard_clean, 'hard_clean')
screened_daily = daily_tier(df_analysis_screened, 'screened')
screening_pairs = hard_daily.merge(screened_daily, on=['plot', 'date', 'param'], how='inner')
screening_pairs['absolute_difference'] = (
    screening_pairs['screened_daily_mean'] - screening_pairs['hard_clean_daily_mean']
).abs()

screening_sensitivity = (
    screening_pairs.groupby('param', as_index=False)
    .apply(lambda group: pd.Series({
        'paired_plot_days': len(group),
        'median_absolute_difference': group['absolute_difference'].median(),
        'p95_absolute_difference': group['absolute_difference'].quantile(0.95),
        'spearman_rho': group[['hard_clean_daily_mean', 'screened_daily_mean']].corr(method='spearman').iloc[0, 1],
    }), include_groups=False)
    .reset_index(drop=True)
)
data_tier_summary.to_csv(QUALITY_OUT / 'data_tier_summary.csv', index=False)
screening_sensitivity.to_csv(QUALITY_OUT / 'screening_sensitivity_daily_means.csv', index=False)

fig, axes = plt.subplots(2, 3, figsize=(14, 8))
for axis, parameter in zip(axes.flat, sorted(screening_pairs['param'].unique())):
    sample = screening_pairs[screening_pairs['param'] == parameter]
    axis.scatter(sample['hard_clean_daily_mean'], sample['screened_daily_mean'], s=8, alpha=0.25)
    limits = [sample[['hard_clean_daily_mean', 'screened_daily_mean']].min().min(),
              sample[['hard_clean_daily_mean', 'screened_daily_mean']].max().max()]
    axis.plot(limits, limits, '--', color='#555555', linewidth=1)
    axis.set_title(parameter)
    axis.set_xlabel('Hard-cleaned daily mean')
    axis.set_ylabel('Screened daily mean')
axes.flat[-1].axis('off')
fig.suptitle('Sensitivity of daily means to sensor screening')
fig.tight_layout()
fig.savefig(QUALITY_OUT / 'screening_sensitivity_daily_means.png', dpi=180, bbox_inches='tight')
plt.show()

display(screening_sensitivity.round(4))""",
        id="data-tier-sensitivity",
    )
    tier_index = next(index for index, cell in enumerate(notebook.cells) if cell.get("id") == "1308d1a8") + 1
    existing_ids = {cell.get("id") for cell in notebook.cells}
    if "data-tier-sensitivity" in existing_ids:
        cell_by_id(notebook, "data-tier-sensitivity-notes").source = tier_markdown.source
        cell_by_id(notebook, "data-tier-sensitivity").source = tier_code.source
    else:
        notebook.cells[tier_index:tier_index] = [tier_markdown, tier_code]

    save_cell = cell_by_id(notebook, "edca22b9")
    save_cell.source = replace_once(save_cell.source, "df_clean.to_csv(output_file, index=False)", "df.to_csv(output_file, index=False)")
    save_cell.source = replace_once(save_cell.source, "Cleaned dataset saved", "Primary analysis dataset saved")

    comparative = cell_by_id(notebook, "711cff48")
    comparative.source = replace_once(
        comparative.source,
        "if 'df_raw' in globals():\n    comp_df_raw = df_raw.copy()\nelif 'df' in globals():\n    comp_df_raw = df.copy()",
        "if 'df' in globals():\n    comp_df_raw = df.copy()\nelif 'df_hard_clean' in globals():\n    comp_df_raw = df_hard_clean.copy()",
    )
    comparative.source = replace_once(
        comparative.source,
        "print(f'  Rows available: {len(comp_df_raw):,}')",
        "print(f'  Analysis-screened rows available: {len(comp_df_raw):,}')",
    )

    drydown = cell_by_id(notebook, "8a08251a")
    drydown.source = replace_once(
        drydown.source,
        "if 'df_raw' in globals():\n        source_df = df_raw.copy()\n    elif 'df' in globals():\n        source_df = df.copy()",
        "if 'df' in globals():\n        source_df = df.copy()\n    elif 'df_hard_clean' in globals():\n        source_df = df_hard_clean.copy()",
    )

    readiness = cell_by_id(notebook, "d9503874")
    readiness.source = replace_once(
        readiness.source,
        "daily_long = df_clean.loc[\n    (~df_clean['quality_flag']) & df_clean['param'].isin(readiness_params),\n    ['time', 'plot', 'ft', 'param', 'value']\n].copy()",
        "daily_long = df.loc[\n    df['param'].isin(readiness_params),\n    ['time', 'plot', 'ft', 'param', 'value']\n].copy()",
    )

    forecasting = cell_by_id(notebook, "daily-microclimate-forecasting-code")
    coverage_start = "daily_forecast_coverage.index.name = 'plot'"
    coverage_end = r"print('\nPAR has weaker coverage than the other targets; interpret its held-out scores with that limitation.')"
    coverage_code = """daily_forecast_coverage.index.name = 'plot'
daily_forecast_coverage.reset_index().to_csv(
    forecast_out / 'daily_forecast_target_coverage.csv', index=False
)
print('Daily next-day target coverage by plot:')
print(daily_forecast_coverage.to_string())
print('Coverage table saved ->', forecast_out / 'daily_forecast_target_coverage.csv')
"""
    if coverage_start in forecasting.source:
        prefix, _, remainder = forecasting.source.partition(coverage_start)
        _, marker, suffix = remainder.partition(coverage_end)
        if not marker:
            raise ValueError("Could not find the end of the forecast coverage block")
        forecasting.source = prefix + coverage_code + coverage_end + suffix
    else:
        forecasting.source = replace_once(
            forecasting.source,
            "print('Daily next-day target coverage by plot:')\nprint(daily_forecast_coverage.to_string())",
            coverage_code.rstrip(),
        )

    cell_by_id(notebook, "0484e8b2").source = """### 8.2 Daily relationships

Variables are aligned by plot and date before comparison. The table reports the median within-plot Spearman association and a 95% moving-block bootstrap interval. Fourteen-day blocks retain short-term temporal dependence, so the interval is more appropriate than treating every plot-day as independent. These are descriptive associations; VPD is calculated from temperature and humidity and should be interpreted accordingly."""

    cell_by_id(notebook, "beea00c1").source = """# Daily distributions and time-aware, within-plot associations.
from scipy import stats
from scripts.microclimate_statistics import block_spearman_table

normality_rows = []
for column in daily_value_columns:
    values = daily_microclimate[column].dropna()
    sample = values.sample(min(5000, len(values)), random_state=42)
    statistic, p_value = stats.normaltest(sample)
    normality_rows.append({
        'variable': column, 'n': len(values), 'sample_skew': sample.skew(),
        'normaltest_p_value': p_value, 'normal_at_alpha_0_05': bool(p_value > 0.05),
    })
normality_summary = pd.DataFrame(normality_rows)
normality_summary.to_csv(READINESS_OUT / 'daily_normality_checks.csv', index=False)

correlation_summary = block_spearman_table(
    daily_microclimate,
    daily_value_columns,
    plot_column='plot',
    date_column='date',
    block_days=14,
    n_bootstrap=500,
    random_state=42,
)
correlation_summary['interval_excludes_zero'] = (
    (correlation_summary['ci_low'] > 0) | (correlation_summary['ci_high'] < 0)
)
correlation_summary.to_csv(READINESS_OUT / 'daily_block_spearman_correlations.csv', index=False)

rho_matrix = pd.DataFrame(np.eye(len(daily_value_columns)), index=daily_value_columns, columns=daily_value_columns)
annotations = pd.DataFrame('', index=daily_value_columns, columns=daily_value_columns)
for variable in daily_value_columns:
    annotations.loc[variable, variable] = '1.00'
for row in correlation_summary.to_dict('records'):
    left, right = row['variable_1'], row['variable_2']
    rho_matrix.loc[left, right] = rho_matrix.loc[right, left] = row['within_plot_median_rho']
    label = f"{row['within_plot_median_rho']:.2f}\\n[{row['ci_low']:.2f}, {row['ci_high']:.2f}]"
    annotations.loc[left, right] = annotations.loc[right, left] = label

fig, ax = plt.subplots(figsize=(10, 8))
sns.heatmap(rho_matrix, annot=annotations, fmt='', cmap='RdBu_r', center=0, vmin=-1, vmax=1, square=True, ax=ax)
ax.set_title('Within-plot Spearman association\\n95% moving-block bootstrap interval in brackets')
fig.tight_layout()
fig.savefig(READINESS_OUT / 'daily_spearman_heatmap.png', dpi=180, bbox_inches='tight')
plt.show()

strongest_pairs = correlation_summary.head(2)
fig, axes = plt.subplots(1, len(strongest_pairs), figsize=(6 * len(strongest_pairs), 5))
axes = np.atleast_1d(axes)
for axis, row in zip(axes, strongest_pairs.to_dict('records')):
    sns.scatterplot(data=daily_microclimate, x=row['variable_1'], y=row['variable_2'], hue='plot', s=22, alpha=0.55, ax=axis)
    axis.set_title(f"{row['variable_1']} vs {row['variable_2']}\\nmedian within-plot rho = {row['within_plot_median_rho']:.2f}")
    axis.legend(fontsize=7)
fig.tight_layout()
fig.savefig(READINESS_OUT / 'daily_relationship_scatter.png', dpi=180, bbox_inches='tight')
plt.show()

print('Distribution checks:')
display(normality_summary.round(4))
print('Time-aware within-plot associations:')
display(correlation_summary.round(4))"""

    feature_notes = cell_by_id(notebook, "c0ee5cb3")
    feature_notes.source = feature_notes.source.replace(
        "| Plot identifier | The measured plot | Known at deployment |\n", ""
    )
    feature_notes.source += "\n\nPlot is kept for split auditing and reporting but is deliberately excluded from the classifier feature matrix."

    temporal = cell_by_id(notebook, "temporal-regression-holdout")
    temporal.source = temporal.source.replace(
        "from scripts.microclimate_forecasting import MODEL_ORDER, _fold_metrics, _regression_pipeline",
        "from scripts.microclimate_forecasting import MODEL_ORDER, MODEL_SELECTION_ORDER, _fold_metrics, _regression_pipeline",
    )
    temporal.source = replace_once(
        temporal.source,
        "    learned_candidates = target_validation_metrics[target_validation_metrics['model_name'] != 'Persistence'].copy()\n    best_mae = learned_candidates['mae'].min()\n    finalists = learned_candidates[learned_candidates['mae'] <= best_mae * 1.01].copy()\n    finalists['complexity_order'] = finalists['model_name'].map(MODEL_ORDER)\n    selected_regression = finalists.sort_values(['complexity_order', 'mae']).iloc[0]['model_name']",
        "    best_mae = target_validation_metrics['mae'].min()\n    finalists = target_validation_metrics[target_validation_metrics['mae'] <= best_mae * 1.01].copy()\n    finalists['complexity_order'] = finalists['model_name'].map(MODEL_SELECTION_ORDER)\n    selected_regression = finalists.sort_values(['complexity_order', 'mae']).iloc[0]['model_name']",
    )
    temporal.source = replace_once(
        temporal.source,
        "    selected_pipeline = _regression_pipeline(selected_regression, temporal_features, pd.concat([target_train, target_validation], ignore_index=True))\n    train_validation = pd.concat([target_train, target_validation], ignore_index=True)\n    selected_pipeline.fit(train_validation[temporal_features], train_validation[target_column])\n    selected_test_prediction = selected_pipeline.predict(target_test[temporal_features])",
        "    train_validation = pd.concat([target_train, target_validation], ignore_index=True)\n    if selected_regression == 'Persistence':\n        selected_test_prediction = target_test[target].to_numpy()\n    else:\n        selected_pipeline = _regression_pipeline(selected_regression, temporal_features, train_validation)\n        selected_pipeline.fit(train_validation[temporal_features], train_validation[target_column])\n        selected_test_prediction = selected_pipeline.predict(target_test[temporal_features])",
    )

    evaluation = cell_by_id(notebook, "vpd-evaluation-report")
    old_plot = """fig, ax = plt.subplots(figsize=(7, 5.5))
ConfusionMatrixDisplay(test_confusion, display_labels=all_vpd_classes).plot(ax=ax, colorbar=False, values_format='d')
ax.set_title('Final chronological VPD-state test confusion matrix')
fig.tight_layout()
fig.savefig(READINESS_OUT / 'vpd_state_final_test_confusion_matrix.png', dpi=180, bbox_inches='tight')
plt.show()"""
    new_plot = """short_labels = [label.replace(' atmosphere', '').replace(' demand', '') for label in all_vpd_classes]
row_totals = test_confusion.sum(axis=1, keepdims=True)
row_pct = np.divide(test_confusion, row_totals, out=np.zeros_like(test_confusion, dtype=float), where=row_totals != 0)
confusion_annotations = np.array([
    [f'{count}\\n{100 * pct:.1f}%' for count, pct in zip(count_row, pct_row)]
    for count_row, pct_row in zip(test_confusion, row_pct)
])
fig, ax = plt.subplots(figsize=(8, 6.5))
sns.heatmap(row_pct, annot=confusion_annotations, fmt='', cmap='Blues', vmin=0, vmax=1,
            xticklabels=short_labels, yticklabels=short_labels, cbar_kws={'label': 'Row percentage'}, ax=ax)
ax.set_xlabel('Predicted class')
ax.set_ylabel('Observed class')
ax.set_title('Final chronological VPD-state test confusion matrix')
ax.tick_params(axis='x', rotation=25)
ax.tick_params(axis='y', rotation=0)
fig.tight_layout()
fig.savefig(READINESS_OUT / 'vpd_state_final_test_confusion_matrix.png', dpi=180, bbox_inches='tight')
plt.show()"""
    evaluation.source = replace_once(evaluation.source, old_plot, new_plot)

    manifest = cell_by_id(notebook, "reproducibility-manifest")
    manifest.source = manifest.source.replace(
        "'clean_rows': int(len(df_clean)),",
        "'hard_clean_rows': int(len(df_hard_clean)),\n        'analysis_screened_rows': int(len(df_analysis_screened)),",
    )
    manifest.source = manifest.source.replace(
        "'quality_flag_policy': 'Candidate sensor anomalies remain in df_clean with quality_flag and quality_reason; the readiness daily frame excludes flagged rows without changing the raw file.',",
        "'quality_flag_policy': 'Candidate anomalies remain in df_hard_clean for audit. The primary EDA and modelling tier retains them; the analysis-screened tier is a sensitivity check only.',",
    )
    manifest.source = manifest.source.replace(
        "f\"- Rows: {run_manifest['data']['raw_rows']:,} raw; {run_manifest['data']['clean_rows']:,} after hard cleaning.\",\n        '- Flags are retained for audit; flagged rows are excluded only from the readiness daily frame.',",
        "f\"- Rows: {run_manifest['data']['raw_rows']:,} raw; {run_manifest['data']['hard_clean_rows']:,} hard-cleaned; {run_manifest['data']['analysis_screened_rows']:,} analysis-screened.\",\n        '- The primary EDA and modelling dataset is hard-cleaned and retains review-flagged readings; the screened tier is a sensitivity check.',",
    )
    manifest.source = manifest.source.replace(
        "'vpd_split_audit': 'outputs/redesigned/readiness/vpd_state_split_audit.csv',",
        "'data_tier_summary': 'outputs/redesigned/quality/data_tier_summary.csv',\n        'screening_sensitivity': 'outputs/redesigned/quality/screening_sensitivity_daily_means.csv',\n        'screening_sensitivity_figure': 'outputs/redesigned/quality/screening_sensitivity_daily_means.png',\n        'block_correlation_summary': 'outputs/redesigned/readiness/daily_block_spearman_correlations.csv',\n        'forecast_target_coverage': 'outputs/redesigned/forecasting/daily_forecast_target_coverage.csv',\n        'vpd_split_audit': 'outputs/redesigned/readiness/vpd_state_split_audit.csv',",
    )

    text_replacements = {
        "clear exposure gradient": "clear difference across the monitored plots",
        "better buffered against daytime atmospheric drying": "recorded lower daytime atmospheric drying",
        "help explain these drydowns": "relate to these drydowns",
        "help explain the drying ranking": "are descriptively associated with the drying ranking",
        "significance-tested daily Spearman correlations": "time-aware within-plot Spearman associations",
    }
    for cell in notebook.cells:
        if cell.cell_type == "markdown":
            for old, new in text_replacements.items():
                cell.source = cell.source.replace(old, new)

    cell_by_id(notebook, "9256963e").source = """### Reading the relationship results

The heatmap reports the median association calculated separately within each plot. Brackets show the 95% moving-block bootstrap interval. This reduces the false confidence that would come from treating neighbouring days and repeated observations from the same plot as independent. The values describe association only."""

    cell_by_id(notebook, "5cf3e760").source += "\n\nOnly seven plots are available for the trait comparison. The plotted relationships are descriptive hypotheses and are not treated as statistically confirmed effects."
    cell_by_id(notebook, "temporal-regression-notes").source = """### 8.7 Supplemental chronological regression holdout

This check asks whether current conditions predict a later period. For each target, all candidates, including persistence, are compared on the middle 20% of dates after fitting on the first 60%. The winning validation method is then reported once on the final 20%. A persistence result is a valid outcome: it means the learned models did not improve the next-day forecast."""

    cell_by_id(notebook, "bab9dc2a").source = """## 9. Conclusions and next steps

The notebook uses the hard-cleaned dataset for EDA and modelling, retaining traceably flagged readings that can be physically plausible. The stricter analysis-screened dataset is reported only as a sensitivity check. It reports descriptive site patterns, time-aware relationship intervals, soil-moisture drydowns, site-transfer benchmarks and chronological next-day tests.

The results describe the seven monitored plots and the observed period. They do not establish causal canopy effects or tree health. Those questions require matched biological measurements and a study design built around them."""

    nbformat.write(notebook, NOTEBOOK_PATH)
    print(f"Updated {NOTEBOOK_PATH} ({len(notebook.cells)} cells)")


if __name__ == "__main__":
    main()
