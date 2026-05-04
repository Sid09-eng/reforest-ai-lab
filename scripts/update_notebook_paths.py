import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NB_PATH = ROOT / "clean_microclimate.ipynb"
if not NB_PATH.exists():
    NB_PATH = ROOT / "notebooks" / "clean_microclimate.ipynb"


def set_code_cell(nb, idx, source):
    nb["cells"][idx]["source"] = [line + "\n" for line in source.strip("\n").split("\n")]


def main():
    nb = json.loads(NB_PATH.read_text())

    set_code_cell(
        nb,
        2,
        """
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
from pathlib import Path


def find_project_root():
    start_points = [Path.cwd().resolve()]
    if '__file__' in globals():
        start_points.append(Path(__file__).resolve().parent)

    for start in dict.fromkeys(start_points):
        for candidate in [start, *start.parents]:
            if (candidate / 'data' / 'raw' / 'microclimate_data.csv').exists():
                return candidate
    raise FileNotFoundError('Could not find the repository root containing data/raw/microclimate_data.csv')


PROJECT_ROOT = find_project_root()
RAW_DATA_PATH = PROJECT_ROOT / 'data' / 'raw'
PROCESSED_DATA_PATH = PROJECT_ROOT / 'data' / 'processed'
METADATA_PATH = PROJECT_ROOT / 'data' / 'metadata'
DOCS_PATH = PROJECT_ROOT / 'docs'
OUT_ROOT = PROJECT_ROOT / 'outputs' / 'redesigned'
OUT_ROOT.mkdir(parents=True, exist_ok=True)

DATA_PATH = str(RAW_DATA_PATH)

print(f'PROJECT_ROOT resolved to: {PROJECT_ROOT}')
print(f'RAW_DATA_PATH resolved to: {RAW_DATA_PATH}')
""",
    )

    set_code_cell(
        nb,
        4,
        """
# Load the microclimate data
candidate_files = [
    RAW_DATA_PATH / 'microclimate_data.csv',
    PROJECT_ROOT / 'microclimate_data.csv',
]

csv_file = next((candidate for candidate in candidate_files if candidate.exists()), None)
if csv_file is None:
    raise FileNotFoundError('microclimate_data.csv could not be found from the resolved project paths.')

df = pd.read_csv(csv_file, low_memory=False)

print(f'Dataset loaded successfully from: {csv_file}')
print(f'Total rows: {len(df):,}')
print(f'Total columns: {len(df.columns)}')
""",
    )

    set_code_cell(
        nb,
        25,
        """
output_file = PROCESSED_DATA_PATH / 'microclimate_data_cleaned.csv'
df.to_csv(output_file, index=False)
print(f"✓ Cleaned dataset saved to: {output_file}")
print("\\n" + "=" * 50)
print("Data cleaning complete!")
print("=" * 50)
""",
    )

    set_code_cell(
        nb,
        50,
        """
# ── Comparative analysis setup ───────────────────────────────────────────
import os
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
from pathlib import Path
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator, NullFormatter

warnings.filterwarnings('ignore')

SITE_ORDER = ['UP2', 'US5', 'CN2', 'LP3', 'FT4MD', 'FT4MR', 'FT4TH']
PLOT_TO_FT = {
    'UP2': 'FT1', 'US5': 'FT1',
    'CN2': 'FT2',
    'LP3': 'FT3',
    'FT4MD': 'FT4', 'FT4MR': 'FT4', 'FT4TH': 'FT4',
}
SITE_COLORS = {
    'UP2': '#d62728',
    'US5': '#ff7f0e',
    'CN2': '#1f77b4',
    'LP3': '#2ca02c',
    'FT4MD': '#9467bd',
    'FT4MR': '#6a3d9a',
    'FT4TH': '#b15928',
}
FT_STRIP = {'FT1': '#ffb3b3', 'FT2': '#aec7e8', 'FT3': '#b5d9a8', 'FT4': '#d4b8e0'}

if 'PROJECT_ROOT' not in globals():
    PROJECT_ROOT = Path.cwd().resolve()
OUT_ROOT = str(PROJECT_ROOT / 'outputs' / 'redesigned')
os.makedirs(OUT_ROOT, exist_ok=True)

if 'df_raw' in globals():
    comp_df_raw = df_raw.copy()
elif 'df' in globals():
    comp_df_raw = df.copy()
else:
    candidate_files = [
        PROJECT_ROOT / 'data' / 'processed' / 'microclimate_data_cleaned.csv',
        PROJECT_ROOT / 'data' / 'raw' / 'microclimate_data.csv',
        PROJECT_ROOT / 'microclimate_data_cleaned.csv',
        PROJECT_ROOT / 'microclimate_data.csv',
    ]
    source_path = next((p for p in candidate_files if p.exists()), None)
    if source_path is None:
        raise FileNotFoundError('No CSV file found for comparative analysis.')
    comp_df_raw = pd.read_csv(source_path, low_memory=False)
    print(f'Loaded source data for comparative analysis: {source_path}')

comp_df_raw['time'] = pd.to_datetime(comp_df_raw['time'], errors='coerce')
comp_df_raw['value'] = pd.to_numeric(comp_df_raw['value'], errors='coerce')
comp_df_raw['plot'] = comp_df_raw['plot'].fillna('Unknown')
comp_df_raw['param'] = comp_df_raw['param'].astype(str)
comp_df_raw = comp_df_raw.dropna(subset=['time', 'value', 'plot', 'param'])
comp_df_raw['date'] = pd.to_datetime(comp_df_raw['time'].dt.date)


def season_label(month):
    if month in [11, 12, 1, 2, 3]:
        return 'NE Monsoon'
    if month in [6, 7, 8, 9]:
        return 'SW Monsoon'
    return 'Inter-monsoon'


def add_monsoon_bands(ax, date_min, date_max):
    for year in range(date_min.year - 1, date_max.year + 2):
        spans = [
            (pd.Timestamp(year, 11, 1), pd.Timestamp(year + 1, 3, 31), '#ddeeff'),
            (pd.Timestamp(year, 6, 1), pd.Timestamp(year, 9, 30), '#fff4d6'),
        ]
        for start, end, color in spans:
            if start > date_max or end < date_min:
                continue
            ax.axvspan(max(start, date_min), min(end, date_max), color=color, alpha=0.45, zorder=0, linewidth=0)


def build_daily(param_df, min_obs=6, threshold_quantile=0.95, spike_direction='high'):
    d = (
        param_df
        .groupby(['plot', 'date'], as_index=False)
        .agg(
            daily_mean=('value', 'mean'),
            daily_min=('value', 'min'),
            daily_max=('value', 'max'),
            n_obs=('value', 'count'),
        )
    )
    d = d[d['n_obs'] >= min_obs].copy()
    d['daily_range'] = d['daily_max'] - d['daily_min']
    d['ft'] = d['plot'].map(PLOT_TO_FT)
    d['season'] = d['date'].dt.month.map(season_label)
    d = d.sort_values(['plot', 'date']).reset_index(drop=True)
    d['roll7'] = d.groupby('plot')['daily_mean'].transform(lambda s: s.rolling(7, min_periods=4).mean())
    d['roll30'] = d.groupby('plot')['daily_mean'].transform(lambda s: s.rolling(30, min_periods=15).mean())
    d['range_roll7'] = d.groupby('plot')['daily_range'].transform(lambda s: s.rolling(7, min_periods=4).mean())
    d['delta_daily_mean'] = d.groupby('plot')['daily_mean'].diff()
    d['site_mean'] = d.groupby('plot')['daily_mean'].transform('mean')
    d['anomaly7'] = d['roll7'] - d['site_mean']
    q = d.groupby('plot')['daily_mean'].quantile(threshold_quantile).rename('site_threshold').reset_index()
    d = d.merge(q, on='plot', how='left')
    if spike_direction == 'high':
        d['spike_event'] = d['daily_mean'] >= d['site_threshold']
    else:
        d['spike_event'] = d['daily_mean'] <= d['site_threshold']
    return d


def shared_ylim(series, lo=0.005, hi=0.995, pad_frac=0.05, positive_only=False):
    s = series.dropna()
    if positive_only:
        s = s[s > 0]
    q_lo, q_hi = s.quantile([lo, hi])
    pad = (q_hi - q_lo) * pad_frac if q_hi > q_lo else max(abs(q_hi) * pad_frac, 1e-6)
    ylo, yhi = q_lo - pad, q_hi + pad
    if positive_only:
        ylo = max(s[s > 0].min() * 0.8, ylo)
    return ylo, yhi


def fmt_xaxis(ax, date_min, date_max, last_row=True):
    ax.set_xlim(date_min, date_max)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    if last_row:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b\\n%Y'))
        ax.tick_params(axis='x', rotation=0)
    else:
        ax.xaxis.set_major_formatter(NullFormatter())
        ax.tick_params(axis='x', length=0)


def label_panel(ax, site, ft):
    ax.text(0.012, 0.88, site, transform=ax.transAxes, fontsize=10, fontweight='bold',
            color=SITE_COLORS.get(site, '#333333'), va='top', ha='left', zorder=5)
    ax.text(0.012, 0.72, ft, transform=ax.transAxes, fontsize=8, color='#555555',
            va='top', ha='left', zorder=5)


def make_legend_mean_context():
    handles = [
        mpatches.Patch(facecolor='#ddeeff', edgecolor='none', alpha=0.7, label='NE Monsoon'),
        mpatches.Patch(facecolor='#fff4d6', edgecolor='none', alpha=0.7, label='SW Monsoon'),
    ]
    return handles


def make_legend_range():
    return [
        mpatches.Patch(facecolor='#999999', edgecolor='none', alpha=0.22, label='Daily range'),
        Line2D([0], [0], color='#333333', lw=1.8, label='7-day range smooth'),
    ]


def draw_end_labels(ax, label_points, label_x, ylo, yhi, log_scale=False):
    if not label_points:
        return
    label_points = sorted(label_points, key=lambda d: d['y'])
    if log_scale:
        min_sep = max((np.log10(yhi) - np.log10(ylo)) * 0.045, 0.035)
        prev = np.log10(max(label_points[0]['y'], ylo * 1.01)) - min_sep
        for item in label_points:
            y_log = np.log10(max(item['y'], ylo * 1.01))
            y_log = max(y_log, prev + min_sep)
            y_log = min(y_log, np.log10(yhi * 0.97))
            item['y_adj'] = 10 ** y_log
            prev = y_log
    else:
        min_sep = max((yhi - ylo) * 0.035, 1e-6)
        prev = ylo - min_sep
        for item in label_points:
            y_adj = max(item['y'], prev + min_sep)
            y_adj = min(y_adj, yhi - min_sep)
            item['y_adj'] = y_adj
            prev = y_adj
    for item in label_points:
        ax.text(label_x, item['y_adj'], f"{item['site']} ({item['ft']})",
                color=item['color'], fontsize=10, fontweight='bold',
                va='center', ha='left', clip_on=False)


def plot_fig_A_mean(daily_df, ylabel, param_label, out_path, sites=None, log_scale=False):
    if sites is None:
        sites = [s for s in SITE_ORDER if s in daily_df['plot'].unique()]
    ylo, yhi = shared_ylim(daily_df['roll7'].dropna(), pad_frac=0.10, positive_only=log_scale)
    date_min = daily_df['date'].min()
    date_max = daily_df['date'].max()
    label_x = date_max + pd.Timedelta(days=8)
    fig, ax = plt.subplots(figsize=(22, 10.8))
    add_monsoon_bands(ax, date_min, date_max)
    if log_scale:
        positive_vals = daily_df.loc[daily_df['roll7'] > 0, 'roll7']
        positive_floor = max(positive_vals.min() * 0.8, 0.1)
    else:
        positive_floor = None
    label_points = []
    for site in sites:
        s = daily_df[daily_df['plot'] == site].copy()
        ft = PLOT_TO_FT.get(site, '?')
        col = SITE_COLORS.get(site, '#555555')
        y = s['roll7'].copy()
        if log_scale:
            y = y.clip(lower=positive_floor)
        ax.plot(s['date'], y, color=col, linewidth=2.8, alpha=0.96)
        valid = s.loc[y.notna(), ['date']].copy()
        if not valid.empty:
            valid['y'] = y[y.notna()].to_numpy()
            last = valid.iloc[-1]
            label_points.append({'site': site, 'ft': ft, 'y': float(last['y']), 'color': col})
    if log_scale:
        ax.set_yscale('log')
    ax.set_ylim(ylo, yhi)
    ax.set_xlim(date_min, date_max + pd.Timedelta(days=18))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b\\n%Y'))
    ax.set_ylabel(ylabel, fontsize=13)
    ax.set_xlabel('Date', fontsize=13)
    ax.tick_params(axis='both', labelsize=11)
    if not log_scale:
        ax.yaxis.set_major_locator(MaxNLocator(8))
    ax.grid(alpha=0.24)
    draw_end_labels(ax, label_points, label_x=label_x, ylo=ylo, yhi=yhi, log_scale=log_scale)
    ax.legend(handles=make_legend_mean_context(), loc='upper center', bbox_to_anchor=(0.5, -0.15),
              ncol=2, fontsize=10, title='Monsoon shading', title_fontsize=11,
              framealpha=0.92, edgecolor='none')
    ax.set_title(f'{param_label} — 7-day smoothed daily mean (shared axis)\\nAll sites shown on one x/y axis for direct comparison', fontsize=16, pad=14)
    fig.tight_layout(rect=[0, 0.08, 0.97, 1])
    fig.savefig(out_path, dpi=180, bbox_inches='tight')
    plt.show()
    print(f'  Saved -> {out_path}')


def plot_fig_B_range(daily_df, ylabel_range, param_label, out_path, sites=None):
    if sites is None:
        sites = [s for s in SITE_ORDER if s in daily_df['plot'].unique()]
    n = len(sites)
    ylo, yhi = shared_ylim(daily_df['daily_range'], lo=0, hi=0.995, pad_frac=0.06)
    ylo = max(0, ylo)
    date_min = daily_df['date'].min()
    date_max = daily_df['date'].max()
    fig, axes = plt.subplots(n, 1, figsize=(20, 2.5 * n), sharex=True, sharey=True)
    if n == 1:
        axes = [axes]
    for i, (ax, site) in enumerate(zip(axes, sites)):
        s = daily_df[daily_df['plot'] == site]
        ft = PLOT_TO_FT.get(site, '?')
        col = SITE_COLORS.get(site, '#555555')
        add_monsoon_bands(ax, date_min, date_max)
        ax.fill_between(s['date'], 0, s['daily_range'], color=col, alpha=0.22, zorder=2)
        ax.plot(s['date'], s['range_roll7'], color=col, alpha=0.95, linewidth=1.8, zorder=3)
        ax.set_ylim(ylo, yhi)
        fmt_xaxis(ax, date_min, date_max, last_row=(i == n - 1))
        label_panel(ax, site, ft)
        ax.set_ylabel(ylabel_range, fontsize=8)
        ax.grid(alpha=0.2)
        if i == n - 1:
            ax.set_xlabel('Date', fontsize=9)
    axes[0].legend(handles=make_legend_range(), loc='upper right', fontsize=8, framealpha=0.85, edgecolor='none')
    fig.suptitle(f'{param_label} — Daily range by site\\nFilled band = daily max - daily min · line = 7-day range smooth', fontsize=13, y=1.01)
    fig.tight_layout(h_pad=0.3)
    fig.savefig(out_path, dpi=180, bbox_inches='tight')
    plt.show()
    print(f'  Saved -> {out_path}')


def plot_fig_C_spikes(daily_df, title, out_path, sites=None):
    if sites is None:
        sites = [s for s in SITE_ORDER if s in daily_df['plot'].unique()]
    fig, ax = plt.subplots(figsize=(16, 5.2))
    site_positions = {site: pos for pos, site in enumerate(sites[::-1], start=1)}
    counts = {}
    for site in sites:
        s = daily_df[(daily_df['plot'] == site) & (daily_df['spike_event'])].sort_values('date')
        ft = PLOT_TO_FT.get(site, '?')
        col = SITE_COLORS.get(site, '#555555')
        y = np.full(len(s), site_positions[site])
        ax.scatter(s['date'], y, color=col, s=22, alpha=0.85)
        counts[site] = len(s)
    ax.set_yticks(list(site_positions.values()))
    ax.set_yticklabels(list(site_positions.keys()))
    ax.set_title(title, fontsize=13)
    ax.set_xlabel('Date')
    ax.set_ylabel('Site')
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches='tight')
    plt.show()
    print(f'  Saved -> {out_path}')
    return counts


def plot_fig_D_anomaly(daily_df, param_label, out_path, sites=None):
    if sites is None:
        sites = [s for s in SITE_ORDER if s in daily_df['plot'].unique()]
    ylo, yhi = shared_ylim(daily_df['anomaly7'].dropna(), lo=0.01, hi=0.99, pad_frac=0.12)
    date_min = daily_df['date'].min()
    date_max = daily_df['date'].max()
    label_x = date_max + pd.Timedelta(days=8)
    fig, ax = plt.subplots(figsize=(22, 9.2))
    add_monsoon_bands(ax, date_min, date_max)
    label_points = []
    for site in sites:
        s = daily_df[daily_df['plot'] == site].copy()
        ft = PLOT_TO_FT.get(site, '?')
        col = SITE_COLORS.get(site, '#555555')
        y = s['anomaly7'].copy()
        ax.plot(s['date'], y, color=col, linewidth=2.5, alpha=0.94)
        valid = s.loc[y.notna(), ['date']].copy()
        if not valid.empty:
            valid['y'] = y[y.notna()].to_numpy()
            last = valid.iloc[-1]
            label_points.append({'site': site, 'ft': ft, 'y': float(last['y']), 'color': col})
    ax.axhline(0, color='#444444', lw=1.2, ls='--', alpha=0.85)
    ax.set_ylim(ylo, yhi)
    ax.set_xlim(date_min, date_max + pd.Timedelta(days=18))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b\\n%Y'))
    ax.set_ylabel('Anomaly from site mean', fontsize=13)
    ax.set_xlabel('Date', fontsize=13)
    ax.tick_params(axis='both', labelsize=11)
    ax.yaxis.set_major_locator(MaxNLocator(8))
    ax.grid(alpha=0.24)
    draw_end_labels(ax, label_points, label_x=label_x, ylo=ylo, yhi=yhi, log_scale=False)
    ax.legend(handles=make_legend_mean_context() + [Line2D([0], [0], color='#444444', lw=1.2, ls='--', label='Site mean')],
              loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=3,
              fontsize=10, title='Reference layers', title_fontsize=11,
              framealpha=0.92, edgecolor='none')
    ax.set_title(f'{param_label} — 7-day anomaly from each site mean\\nPositive values are above a site\\'s own average, negative values are below it', fontsize=15, pad=14)
    fig.tight_layout(rect=[0, 0.08, 0.97, 1])
    fig.savefig(out_path, dpi=180, bbox_inches='tight')
    plt.show()
    print(f'  Saved -> {out_path}')


def build_summary_table(daily_df, event_counts, threshold_name, count_name, down_name, up_name):
    summary = (
        daily_df.groupby(['plot', 'ft'])
        .agg(
            MeanDailyMean=('daily_mean', 'mean'),
            MeanDailyMin=('daily_min', 'mean'),
            MeanDailyMax=('daily_max', 'mean'),
            MeanDailyRange=('daily_range', 'mean'),
            Threshold=('site_threshold', 'first'),
            DownRate=('delta_daily_mean', lambda s: -s[s < 0].mean() if (s < 0).any() else np.nan),
            UpRate=('delta_daily_mean', lambda s: s[s > 0].mean() if (s > 0).any() else np.nan),
        )
        .reset_index()
        .rename(columns={'plot': 'Site', 'ft': 'FT', 'Threshold': threshold_name, 'DownRate': down_name, 'UpRate': up_name})
    )
    summary[count_name] = summary['Site'].map(event_counts).fillna(0).astype(int)
    ordered_cols = ['Site', 'FT', 'MeanDailyMean', 'MeanDailyMin', 'MeanDailyMax', 'MeanDailyRange', threshold_name, count_name, down_name, up_name]
    return summary[ordered_cols].round(4)


def run_comparative_parameter(raw_df, slug, pretty_name, ylabel, threshold_quantile, spike_direction,
                              threshold_name, count_name, down_name, up_name,
                              range_label, spike_title, log_scale=False, include_anomaly=False):
    daily_df = build_daily(raw_df, threshold_quantile=threshold_quantile, spike_direction=spike_direction)
    sites = [s for s in SITE_ORDER if s in daily_df['plot'].unique()]
    out_dir = os.path.join(OUT_ROOT, slug)
    os.makedirs(out_dir, exist_ok=True)
    plot_fig_A_mean(daily_df, ylabel=ylabel, param_label=pretty_name,
                    out_path=os.path.join(out_dir, f'{slug}_A_daily_mean_shared.png'),
                    sites=sites, log_scale=log_scale)
    plot_fig_B_range(daily_df, ylabel_range=range_label, param_label=pretty_name,
                     out_path=os.path.join(out_dir, f'{slug}_B_daily_range_faceted.png'),
                     sites=sites)
    counts = plot_fig_C_spikes(daily_df, title=spike_title,
                               out_path=os.path.join(out_dir, f'{slug}_C_threshold_days.png'),
                               sites=sites)
    if include_anomaly:
        plot_fig_D_anomaly(daily_df, param_label=pretty_name,
                           out_path=os.path.join(out_dir, f'{slug}_D_anomaly_shared.png'),
                           sites=sites)
    summary = build_summary_table(daily_df, counts, threshold_name, count_name, down_name, up_name)
    summary.to_csv(os.path.join(out_dir, f'{slug}_summary.csv'), index=False)
    print()
    print('=' * 110)
    print(f'  {pretty_name.upper()} — COMPARATIVE SUMMARY')
    print('=' * 110)
    print(summary.to_string(index=False))
    top_mean = summary.loc[summary['MeanDailyMean'].idxmax()]
    low_mean = summary.loc[summary['MeanDailyMean'].idxmin()]
    most_events = summary.loc[summary[count_name].idxmax()]
    widest_range = summary.loc[summary['MeanDailyRange'].idxmax()]
    print()
    print(f"Highest mean level: {top_mean['Site']} ({top_mean['FT']}) at {top_mean['MeanDailyMean']:.4f}")
    print(f"Lowest mean level: {low_mean['Site']} ({low_mean['FT']}) at {low_mean['MeanDailyMean']:.4f}")
    print(f"Most {count_name}: {most_events['Site']} with {int(most_events[count_name])} days")
    print(f"Widest mean daily range: {widest_range['Site']} at {widest_range['MeanDailyRange']:.4f}")
    return {'daily': daily_df, 'summary': summary, 'counts': counts, 'out_dir': out_dir}


print('✓ Comparative analysis helpers ready')
print(f'  Rows available: {len(comp_df_raw):,}')
""",
    )

    set_code_cell(
        nb,
        63,
        """
# ── Soil moisture setup for drydown, half-life, and daily envelope work ──
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from matplotlib.lines import Line2D
from IPython.display import display, Image

if 'SITE_ORDER' not in globals():
    SITE_ORDER = ['UP2', 'US5', 'CN2', 'LP3', 'FT4MD', 'FT4MR', 'FT4TH']
if 'PROJECT_ROOT' not in globals():
    PROJECT_ROOT = Path.cwd().resolve()
if 'OUT_ROOT' not in globals():
    OUT_ROOT = str(PROJECT_ROOT / 'outputs' / 'redesigned')

if 'soil_daily' not in globals():
    source_df = None
    if 'df_raw' in globals():
        source_df = df_raw.copy()
    elif 'df' in globals():
        source_df = df.copy()
    else:
        candidate_files = [
            PROJECT_ROOT / 'data' / 'processed' / 'microclimate_data_cleaned.csv',
            PROJECT_ROOT / 'data' / 'raw' / 'microclimate_data.csv',
            PROJECT_ROOT / 'microclimate_data_cleaned.csv',
            PROJECT_ROOT / 'microclimate_data.csv',
        ]
        for candidate in candidate_files:
            if candidate.exists():
                source_df = pd.read_csv(candidate, low_memory=False)
                print(f'Loaded source data for soil-moisture analysis: {candidate}')
                break
        if source_df is None:
            raise FileNotFoundError('No source dataframe or CSV file found for soil-moisture analysis.')

    source_df['time'] = pd.to_datetime(source_df['time'], errors='coerce')
    source_df['value'] = pd.to_numeric(source_df['value'], errors='coerce')
    source_df['plot'] = source_df['plot'].fillna('Unknown')
    source_df = source_df.dropna(subset=['time', 'value', 'plot', 'param'])

    soil_raw_local = source_df[source_df['param'].astype(str).str.lower() == 'soil moisture'].copy()
    soil_raw_local = soil_raw_local[(soil_raw_local['value'] >= 0) & (soil_raw_local['value'] <= 0.6)]

    soil_daily = (
        soil_raw_local
        .groupby(['plot', pd.Grouper(key='time', freq='D')])['value']
        .agg(daily_mean='mean', daily_min='min', daily_max='max', n_obs='count')
        .reset_index()
        .rename(columns={'time': 'date'})
    )
    if 'ft' in soil_raw_local.columns:
        plot_to_ft_local = soil_raw_local[['plot', 'ft']].drop_duplicates().set_index('plot')['ft']
        soil_daily['ft'] = soil_daily['plot'].map(plot_to_ft_local)
    else:
        soil_daily['ft'] = np.nan

soil_daily_dd = soil_daily.sort_values(['plot', 'date']).copy()
soil_daily_dd['date'] = pd.to_datetime(soil_daily_dd['date'])
soil_daily_dd['ft'] = soil_daily_dd['ft'].fillna('Unknown')
soil_daily_dd['daily_range'] = soil_daily_dd['daily_max'] - soil_daily_dd['daily_min']
soil_daily_dd['mean_roll7'] = soil_daily_dd.groupby('plot')['daily_mean'].transform(lambda s: s.rolling(7, min_periods=1).mean())
soil_daily_dd['max_roll3'] = soil_daily_dd.groupby('plot')['daily_max'].transform(lambda s: s.rolling(3, min_periods=1).mean())
soil_daily_dd['min_roll3'] = soil_daily_dd.groupby('plot')['daily_min'].transform(lambda s: s.rolling(3, min_periods=1).mean())
soil_daily_dd['range_roll7'] = soil_daily_dd.groupby('plot')['daily_range'].transform(lambda s: s.rolling(7, min_periods=1).mean())

sites_soil = [s for s in SITE_ORDER if s in soil_daily_dd['plot'].unique()] if 'SITE_ORDER' in globals() else sorted(soil_daily_dd['plot'].unique())
out_soil = os.path.join(OUT_ROOT, 'soil_moisture')
os.makedirs(out_soil, exist_ok=True)

drydown_ft_colors = {
    'FT1': '#d95f02',
    'FT2': '#1b9e77',
    'FT3': '#7570b3',
    'FT4': '#1f78b4',
    'Unknown': '#444444',
}

soil_drydown_cfg = {
    'signal_col': 'daily_max',
    'min_len': 4,
    'min_drop': 0.015,
    'max_rewet': 0.003,
    'interp_days': 10,
}
print('Drydown config:', soil_drydown_cfg)
print(f'Soil daily rows: {len(soil_daily_dd):,} | Sites: {sites_soil}')


def half_crossing(t, r):
    valid = np.isfinite(r)
    t = np.asarray(t)[valid]
    r = np.asarray(r)[valid]
    if len(r) == 0 or np.nanmin(r) > 0.5:
        return np.nan
    idx = np.where(r <= 0.5)[0]
    j = idx[0]
    if j == 0:
        return float(t[0])
    t0, t1 = t[j - 1], t[j]
    r0, r1 = r[j - 1], r[j]
    if r1 == r0:
        return float(t1)
    return float(t0 + (0.5 - r0) * (t1 - t0) / (r1 - r0))


def detect_soil_drydowns(daily_df, signal_col='daily_max', min_len=4, min_drop=0.015, max_rewet=0.003, interp_days=10):
    events = []
    curves = []
    for site, s0 in daily_df.groupby('plot'):
        s = s0.sort_values('date').reset_index(drop=True).copy()
        signal = s[signal_col].to_numpy(dtype=float)
        smooth = pd.Series(signal).rolling(3, min_periods=1).mean().to_numpy()
        dates = s['date'].to_numpy()
        ft = s['ft'].iloc[0]
        event_id = 0
        i = 1
        while i < len(s) - min_len:
            if smooth[i] >= smooth[i - 1] and smooth[i] > smooth[i + 1]:
                start = i
                j = i + 1
                neg_steps = 0
                while j < len(s):
                    step = smooth[j] - smooth[j - 1]
                    if step <= max_rewet:
                        if step < 0:
                            neg_steps += 1
                        j += 1
                    else:
                        break
                end = j - 1
                if end - start + 1 >= min_len:
                    y = signal[start:end + 1].astype(float)
                    t = np.arange(len(y), dtype=float)
                    drop = y[0] - y[-1]
                    if drop >= min_drop and neg_steps >= min_len - 1:
                        remaining = (y - y[-1]) / drop
                        empirical_half = half_crossing(t, remaining)
                        mask = (t > 0) & (remaining > 0) & (remaining < 1)
                        decay_k = np.nan
                        exp_half = np.nan
                        fit_r2 = np.nan
                        if mask.sum() >= 2:
                            coeff = np.polyfit(t[mask], np.log(remaining[mask]), 1)
                            pred = np.polyval(coeff, t[mask])
                            obs = np.log(remaining[mask])
                            ss_res = ((obs - pred) ** 2).sum()
                            ss_tot = ((obs - obs.mean()) ** 2).sum()
                            fit_r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
                            decay_k = -coeff[0]
                            if decay_k > 0:
                                exp_half = np.log(2) / decay_k
                        linear_rate = np.polyfit(t, y, 1)[0] if len(t) >= 2 else np.nan
                        mean_step = np.diff(y).mean() if len(y) >= 2 else np.nan
                        events.append({
                            'plot': site,
                            'ft': ft,
                            'event_id': event_id,
                            'signal_used': signal_col,
                            'start_date': pd.Timestamp(dates[start]),
                            'end_date': pd.Timestamp(dates[end]),
                            'duration_days': int(len(y)),
                            'start_signal': float(y[0]),
                            'end_signal': float(y[-1]),
                            'total_loss': float(drop),
                            'linear_rate': float(linear_rate),
                            'mean_daily_change': float(mean_step),
                            'empirical_half_life_days': empirical_half,
                            'exp_decay_k': float(decay_k) if pd.notna(decay_k) else np.nan,
                            'exp_half_life_days': float(exp_half) if pd.notna(exp_half) else np.nan,
                            'exp_fit_r2': float(fit_r2) if pd.notna(fit_r2) else np.nan,
                        })
                        grid = np.arange(0, interp_days + 1, 1.0)
                        curve = np.interp(grid, t, remaining, left=np.nan, right=np.nan)
                        fit_curve = np.exp(-decay_k * grid) if pd.notna(decay_k) and decay_k > 0 else np.full_like(grid, np.nan, dtype=float)
                        for gd, rv, fv in zip(grid, curve, fit_curve):
                            curves.append({
                                'plot': site,
                                'ft': ft,
                                'event_id': event_id,
                                't_day': float(gd),
                                'remaining_fraction': float(rv) if pd.notna(rv) else np.nan,
                                'fit_fraction': float(fv) if pd.notna(fv) else np.nan,
                            })
                        event_id += 1
                        i = end
            i += 1
    return pd.DataFrame(events), pd.DataFrame(curves)
""",
    )

    set_code_cell(
        nb,
        74,
        """
# ── Plot-summary integration for drydown interpretation and prediction ───
from pathlib import Path
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

if 'PROJECT_ROOT' not in globals():
    PROJECT_ROOT = Path.cwd().resolve()

plot_summary_candidates = [
    PROJECT_ROOT / 'data' / 'metadata' / 'plot_summary.csv',
    PROJECT_ROOT / 'plot_summary.csv',
    Path.home() / 'Downloads' / 'plot_summary.csv',
]
plot_summary_path = next((p for p in plot_summary_candidates if p.exists()), None)
if plot_summary_path is None:
    raise FileNotFoundError('plot_summary.csv was not found in data/metadata or the fallback paths.')

plot_summary = pd.read_csv(plot_summary_path)
plot_name_map = {'MRFT4': 'FT4MR', 'THFT4': 'FT4TH'}
plot_summary['plot_key'] = plot_summary['plot'].replace(plot_name_map)

site_trait_cols = [
    'avg_absgrowthCCNR',
    'stemcount2024',
    'basal_area2024',
    'corrected_mortality',
    'corrected_recruitment',
    'shannon2024',
]
site_traits = plot_summary[['plot_key'] + site_trait_cols].rename(columns={'plot_key': 'plot'})

start_day_features = (
    soil_daily_dd[
        ['plot', 'date', 'daily_mean', 'daily_min', 'daily_max', 'daily_range', 'mean_roll7', 'max_roll3', 'min_roll3', 'range_roll7']
    ]
    .rename(
        columns={
            'date': 'start_date',
            'daily_mean': 'start_daily_mean',
            'daily_min': 'start_daily_min',
            'daily_max': 'start_daily_max',
            'daily_range': 'start_daily_range',
        }
    )
)

soil_drydown_model_df = (
    soil_drydown_events.copy()
    .assign(abs_drying_rate=lambda d: -d['linear_rate'])
    .merge(start_day_features, on=['plot', 'start_date'], how='left')
    .merge(site_traits, on='plot', how='left')
)
soil_drydown_model_df['start_month'] = soil_drydown_model_df['start_date'].dt.month
soil_drydown_model_df['month_sin'] = np.sin(2 * np.pi * soil_drydown_model_df['start_month'] / 12)
soil_drydown_model_df['month_cos'] = np.cos(2 * np.pi * soil_drydown_model_df['start_month'] / 12)

matched_site_mask = soil_drydown_model_df[site_trait_cols].notna().all(axis=1)
matched_sites = sorted(soil_drydown_model_df.loc[matched_site_mask, 'plot'].dropna().unique())
soil_drydown_model_df = soil_drydown_model_df[soil_drydown_model_df['plot'].isin(matched_sites)].copy()

baseline_features = ['start_signal', 'start_daily_range', 'mean_roll7', 'max_roll3', 'month_sin', 'month_cos']
augmented_features = baseline_features + site_trait_cols


def evaluate_logo_regression(df, target_col, feature_cols, alpha=2.0):
    df = df.dropna(subset=[target_col]).copy()
    X = df[feature_cols]
    y = df[target_col]
    groups = df['plot']
    model = Pipeline([
        ('prep', ColumnTransformer([
            ('num', Pipeline([
                ('imputer', SimpleImputer(strategy='median')),
                ('scaler', StandardScaler()),
            ]), feature_cols),
        ])),
        ('reg', Ridge(alpha=alpha)),
    ])

    logo = LeaveOneGroupOut()
    preds = []
    obs = []
    heldout_sites = []
    for train_idx, test_idx in logo.split(X, y, groups):
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        fold_pred = model.predict(X.iloc[test_idx])
        preds.extend(fold_pred)
        obs.extend(y.iloc[test_idx])
        heldout_sites.extend(groups.iloc[test_idx])

    preds = np.asarray(preds)
    obs = np.asarray(obs)
    result = {
        'mae': mean_absolute_error(obs, preds),
        'rmse': mean_squared_error(obs, preds, squared=False),
        'r2': r2_score(obs, preds),
    }
    pred_df = pd.DataFrame({
        'plot': heldout_sites,
        'target': target_col,
        'observed': obs,
        'predicted': preds,
        'feature_set': ' + '.join(feature_cols),
    })
    return result, pred_df


comparison_rows = []
prediction_frames = []
for target_col, target_label in [
    ('abs_drying_rate', 'Drying rate'),
    ('empirical_half_life_days', 'Half-life'),
]:
    baseline_metrics, baseline_preds = evaluate_logo_regression(soil_drydown_model_df, target_col, baseline_features)
    augmented_metrics, augmented_preds = evaluate_logo_regression(soil_drydown_model_df, target_col, augmented_features)
    prediction_frames.extend([
        baseline_preds.assign(model_name='Event-onset only', target_label=target_label),
        augmented_preds.assign(model_name='Event-onset + plot summary', target_label=target_label),
    ])
    comparison_rows.extend([
        {
            'target': target_col,
            'target_label': target_label,
            'model_name': 'Event-onset only',
            **baseline_metrics,
        },
        {
            'target': target_col,
            'target_label': target_label,
            'model_name': 'Event-onset + plot summary',
            **augmented_metrics,
        },
    ])

soil_model_comparison = pd.DataFrame(comparison_rows)
soil_model_predictions = pd.concat(prediction_frames, ignore_index=True)
soil_model_comparison['mae_change_vs_baseline_pct'] = soil_model_comparison.groupby('target')['mae'].transform(lambda s: 100 * (s.iloc[0] - s) / s.iloc[0])
soil_model_comparison['rmse_change_vs_baseline_pct'] = soil_model_comparison.groupby('target')['rmse'].transform(lambda s: 100 * (s.iloc[0] - s) / s.iloc[0])

soil_trait_links = (
    soil_drydown_summary[['plot', 'ft', 'abs_median_drying_rate', 'median_empirical_half_life_days']]
    .merge(site_traits, on='plot', how='inner')
)
trait_corr = soil_trait_links[
    ['abs_median_drying_rate', 'median_empirical_half_life_days'] + site_trait_cols
].corr().loc[site_trait_cols, ['abs_median_drying_rate', 'median_empirical_half_life_days']]

soil_drydown_model_df.to_csv(os.path.join(out_soil, 'soil_drydown_events_with_plot_summary.csv'), index=False)
soil_model_comparison.to_csv(os.path.join(out_soil, 'soil_plot_summary_model_comparison.csv'), index=False)
soil_model_predictions.to_csv(os.path.join(out_soil, 'soil_plot_summary_predictions.csv'), index=False)
trait_corr.to_csv(os.path.join(out_soil, 'soil_plot_summary_trait_correlations.csv'))

print(f'Plot summary loaded from: {plot_summary_path}')
print(f'Matched sites for plot-summary merge: {matched_sites}')
print(f'Total matched drydown events: {len(soil_drydown_model_df):,}')
print('\\nPrediction comparison (leave-one-site-out):')
print(soil_model_comparison.round(4).to_string(index=False))
print('\\nSite-trait correlations with drydown metrics:')
print(trait_corr.round(3).to_string())

comp_plot = soil_model_comparison.copy()
fig, axes = plt.subplots(1, 2, figsize=(13, 5.4), sharey=False)
metric_specs = [
    ('rmse', 'RMSE (lower is better)'),
    ('mae', 'MAE (lower is better)'),
]
for ax, (metric, xlabel) in zip(axes, metric_specs):
    pivot = comp_plot.pivot(index='target_label', columns='model_name', values=metric).loc[['Drying rate', 'Half-life']]
    y = np.arange(len(pivot.index))
    h = 0.35
    ax.barh(y - h/2, pivot['Event-onset only'], height=h, color='#bdbdbd', label='Event-onset only')
    ax.barh(y + h/2, pivot['Event-onset + plot summary'], height=h, color='#4c78a8', label='Event-onset + plot summary')
    for row_idx, target_label in enumerate(pivot.index):
        base = pivot.loc[target_label, 'Event-onset only']
        aug = pivot.loc[target_label, 'Event-onset + plot summary']
        delta = 100 * (base - aug) / base if base != 0 else np.nan
        ax.text(max(base, aug), row_idx + h/2, f'  {delta:+.1f}%', va='center', fontsize=8, color='#333333')
    ax.set_yticks(y)
    ax.set_yticklabels(pivot.index)
    ax.set_xlabel(xlabel)
    ax.grid(axis='x', alpha=0.25)
axes[0].legend(frameon=False, loc='lower right')
axes[0].set_title('Does plot-summary data improve held-out prediction?')
fig.tight_layout()
fig.savefig(os.path.join(out_soil, 'soil_J_plot_summary_model_comparison.png'), dpi=180, bbox_inches='tight')
plt.show()
print(f"  Saved -> {os.path.join(out_soil, 'soil_J_plot_summary_model_comparison.png')}")

trait_plot_cols = [
    ('corrected_mortality', 'abs_median_drying_rate', 'Mortality vs drying rate'),
    ('shannon2024', 'abs_median_drying_rate', 'Diversity vs drying rate'),
    ('avg_absgrowthCCNR', 'median_empirical_half_life_days', 'Growth vs half-life'),
    ('stemcount2024', 'median_empirical_half_life_days', 'Stem density vs half-life'),
]
fig, axes = plt.subplots(2, 2, figsize=(12.5, 9.5))
axes = axes.ravel()
for ax, (xcol, ycol, title) in zip(axes, trait_plot_cols):
    x = soil_trait_links[xcol]
    y = soil_trait_links[ycol]
    ax.scatter(x, y, s=80, color='#4c78a8', edgecolor='white', linewidth=0.8)
    if len(soil_trait_links) >= 2:
        coef = np.polyfit(x, y, 1)
        xx = np.linspace(x.min(), x.max(), 100)
        ax.plot(xx, coef[0] * xx + coef[1], color='#333333', lw=1.2)
        corr_val = np.corrcoef(x, y)[0, 1]
    else:
        corr_val = np.nan
    for _, row in soil_trait_links.iterrows():
        ax.text(row[xcol], row[ycol], f"  {row['plot']}", fontsize=8, va='center')
    ax.set_title(f"{title} (r={corr_val:.2f})")
    ax.set_xlabel(xcol.replace('_', ' '))
    ax.set_ylabel(ycol.replace('_', ' '))
    ax.grid(alpha=0.2)
fig.tight_layout()
fig.savefig(os.path.join(out_soil, 'soil_K_plot_summary_trait_links.png'), dpi=180, bbox_inches='tight')
plt.show()
print(f"  Saved -> {os.path.join(out_soil, 'soil_K_plot_summary_trait_links.png')}")
""",
    )

    NB_PATH.write_text(json.dumps(nb, indent=1))
    print(f"Updated notebook path logic in {NB_PATH}")


if __name__ == "__main__":
    main()
