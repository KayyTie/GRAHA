import os
import glob
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.ticker as ticker
import seaborn as sns

# Load Windows system fonts into fontManager
for font_path in glob.glob(r'C:\Windows\Fonts\*.ttf'):
    try:
        fm.fontManager.addfont(font_path)
    except Exception:
        pass

# Force Arial / Segoe UI sans-serif fonts
matplotlib.rcParams['font.family'] = 'Arial'
matplotlib.rcParams['font.sans-serif'] = ['Arial', 'Segoe UI', 'Tahoma', 'sans-serif']
matplotlib.rcParams['axes.formatter.use_mathtext'] = False
plt.style.use('dark_background')
sns.set_palette('crest')

# Load the merged BLS result CSV
csv_path = r"D:\Bhartiya Antariksh Hackathon\ph3\batch_020-20260806T233212Z-1-001\BLS_result\blsresult.csv"
output_dir = r"D:\Bhartiya Antariksh Hackathon\ph3\batch_020-20260806T233212Z-1-001\BLS_result"
artifact_dir = r"C:\Users\kusha\.gemini\antigravity-ide\brain\461c4e48-6766-4634-80d2-ae6a974bd9b1"

df = pd.read_csv(csv_path)
print(f"Loaded {len(df)} rows from {csv_path}")

def format_log_axis(ax, axis='x'):
    """Helper to set scalar formatting on log axes to avoid Mathtext font issues."""
    target_axis = ax.xaxis if axis == 'x' else ax.yaxis
    target_axis.set_major_formatter(ticker.FormatStrFormatter('%g'))
    target_axis.set_minor_formatter(ticker.NullFormatter())

# ==========================================
# 1. Master Distribution Overview (6 Panels)
# ==========================================
fig, axes = plt.subplots(2, 3, figsize=(18, 11), dpi=200)
fig.suptitle("BLS Transit Search Parameters Distribution (11,000 Targets)", fontsize=18, fontweight='bold', y=0.98, color='#61afef')

# Panel 1: Period Distribution
sns.histplot(df['Period'], bins=50, kde=True, ax=axes[0, 0], color='#4facfe', edgecolor='#1e1e2e')
axes[0, 0].set_title('Period Distribution (days)', fontsize=13, fontweight='bold', color='#61afef')
axes[0, 0].set_xlabel('Period (days)')
axes[0, 0].set_ylabel('Count')
median_p = df['Period'].median()
axes[0, 0].axvline(median_p, color='#e06c75', linestyle='--', linewidth=1.5, label=f'Median: {median_p:.2f} d')
axes[0, 0].legend()
axes[0, 0].grid(True, alpha=0.2)

# Panel 2: Depth (ppm) Log Distribution
sns.histplot(df['Depth_ppm'], bins=50, kde=True, ax=axes[0, 1], color='#00f2fe', log_scale=True, edgecolor='#1e1e2e')
format_log_axis(axes[0, 1], axis='x')
axes[0, 1].set_title('Transit Depth (ppm, Log Scale)', fontsize=13, fontweight='bold', color='#61afef')
axes[0, 1].set_xlabel('Depth (ppm)')
axes[0, 1].set_ylabel('Count')
median_d = df['Depth_ppm'].median()
axes[0, 1].axvline(median_d, color='#e06c75', linestyle='--', linewidth=1.5, label=f'Median: {median_d:.1f} ppm')
axes[0, 1].legend()
axes[0, 1].grid(True, alpha=0.2)

# Panel 3: Duration (hours) Distribution
sns.histplot(df['Duration_hr'], bins=50, kde=True, ax=axes[0, 2], color='#43e97b', edgecolor='#1e1e2e')
axes[0, 2].set_title('Transit Duration (hours)', fontsize=13, fontweight='bold', color='#61afef')
axes[0, 2].set_xlabel('Duration (hr)')
axes[0, 2].set_ylabel('Count')
median_dur = df['Duration_hr'].median()
axes[0, 2].axvline(median_dur, color='#e06c75', linestyle='--', linewidth=1.5, label=f'Median: {median_dur:.2f} hr')
axes[0, 2].legend()
axes[0, 2].grid(True, alpha=0.2)

# Panel 4: Epoch (BTJD) Distribution
sns.histplot(df['Epoch'], bins=50, kde=True, ax=axes[1, 0], color='#fa709a', edgecolor='#1e1e2e')
axes[1, 0].set_title('Epoch Distribution (BTJD)', fontsize=13, fontweight='bold', color='#61afef')
axes[1, 0].set_xlabel('Epoch (BTJD)')
axes[1, 0].set_ylabel('Count')
median_ep = df['Epoch'].median()
axes[1, 0].axvline(median_ep, color='#e06c75', linestyle='--', linewidth=1.5, label=f'Median: {median_ep:.2f}')
axes[1, 0].legend()
axes[1, 0].grid(True, alpha=0.2)

# Panel 5: Signal Detection Efficiency (SDE)
sns.histplot(df['sde'], bins=50, kde=True, ax=axes[1, 1], color='#fee140', edgecolor='#1e1e2e')
axes[1, 1].set_title('Signal Detection Efficiency (SDE)', fontsize=13, fontweight='bold', color='#61afef')
axes[1, 1].set_xlabel('SDE')
axes[1, 1].set_ylabel('Count')
sde_7 = (df['sde'] >= 7.0).sum()
axes[1, 1].axvline(7.0, color='#e06c75', linestyle='--', linewidth=1.5, label=f'SDE >= 7.0: {sde_7} targets')
axes[1, 1].legend()
axes[1, 1].grid(True, alpha=0.2)

# Panel 6: Period vs Depth Scatter Plot (colored by SDE)
sc = axes[1, 2].scatter(df['Period'], df['Depth_ppm'], c=df['sde'], cmap='magma', s=12, alpha=0.6)
axes[1, 2].set_yscale('log')
format_log_axis(axes[1, 2], axis='y')
axes[1, 2].set_title('Period vs Depth (colored by SDE)', fontsize=13, fontweight='bold', color='#61afef')
axes[1, 2].set_xlabel('Period (days)')
axes[1, 2].set_ylabel('Depth (ppm, log scale)')
cbar = fig.colorbar(sc, ax=axes[1, 2])
cbar.set_label('SDE', color='white')
cbar.ax.yaxis.set_tick_params(color='white')
plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color='white')
axes[1, 2].grid(True, alpha=0.2)

plt.tight_layout(rect=[0, 0.03, 1, 0.95])

# Save Overview Figure
fig1_path_local = os.path.join(output_dir, "bls_distribution_overview.png")
fig1_path_artifact = os.path.join(artifact_dir, "bls_distribution_overview.png")
plt.savefig(fig1_path_local, bbox_inches='tight')
plt.savefig(fig1_path_artifact, bbox_inches='tight')
plt.close()
print(f"Saved overview plot to:\n  - {fig1_path_local}\n  - {fig1_path_artifact}")


# ==========================================
# 2. Parameter Correlations Matrix & Joint Distributions
# ==========================================
fig, axes = plt.subplots(2, 2, figsize=(14, 11), dpi=200)
fig.suptitle("BLS Parameter Relationships & Correlations", fontsize=16, fontweight='bold', y=0.98, color='#61afef')

# Panel 1: Period vs Duration
sc1 = axes[0, 0].scatter(df['Period'], df['Duration_hr'], c=df['sde'], cmap='viridis', s=10, alpha=0.5)
axes[0, 0].set_title('Period vs Transit Duration', fontsize=12, fontweight='bold')
axes[0, 0].set_xlabel('Period (days)')
axes[0, 0].set_ylabel('Duration (hours)')
cbar1 = fig.colorbar(sc1, ax=axes[0, 0])
cbar1.set_label('SDE')
axes[0, 0].grid(True, alpha=0.2)

# Panel 2: Period vs SDE
axes[0, 1].scatter(df['Period'], df['sde'], color='#4facfe', s=10, alpha=0.4)
axes[0, 1].set_title('Period vs SDE', fontsize=12, fontweight='bold')
axes[0, 1].set_xlabel('Period (days)')
axes[0, 1].set_ylabel('SDE')
axes[0, 1].axhline(7.0, color='#e06c75', linestyle='--', label='SDE = 7 Threshold')
axes[0, 1].legend()
axes[0, 1].grid(True, alpha=0.2)

# Panel 3: Depth vs SDE
axes[1, 0].scatter(df['Depth_ppm'], df['sde'], color='#fa709a', s=10, alpha=0.4)
axes[1, 0].set_xscale('log')
format_log_axis(axes[1, 0], axis='x')
axes[1, 0].set_title('Depth (ppm) vs SDE', fontsize=12, fontweight='bold')
axes[1, 0].set_xlabel('Depth (ppm, log scale)')
axes[1, 0].set_ylabel('SDE')
axes[1, 0].axhline(7.0, color='#e06c75', linestyle='--', label='SDE = 7 Threshold')
axes[1, 0].legend()
axes[1, 0].grid(True, alpha=0.2)

# Panel 4: Duration vs Depth
sc2 = axes[1, 1].scatter(df['Duration_hr'], df['Depth_ppm'], c=df['sde'], cmap='plasma', s=10, alpha=0.5)
axes[1, 1].set_yscale('log')
format_log_axis(axes[1, 1], axis='y')
axes[1, 1].set_title('Duration vs Depth (ppm)', fontsize=12, fontweight='bold')
axes[1, 1].set_xlabel('Duration (hours)')
axes[1, 1].set_ylabel('Depth (ppm, log scale)')
cbar2 = fig.colorbar(sc2, ax=axes[1, 1])
cbar2.set_label('SDE')
axes[1, 1].grid(True, alpha=0.2)

plt.tight_layout(rect=[0, 0.03, 1, 0.95])

# Save Correlation Figure
fig2_path_local = os.path.join(output_dir, "bls_parameter_correlations.png")
fig2_path_artifact = os.path.join(artifact_dir, "bls_parameter_correlations.png")
plt.savefig(fig2_path_local, bbox_inches='tight')
plt.savefig(fig2_path_artifact, bbox_inches='tight')
plt.close()
print(f"Saved correlations plot to:\n  - {fig2_path_local}\n  - {fig2_path_artifact}")


# ==========================================
# 3. Uncertainties (Sigma) Distribution
# ==========================================
fig, axes = plt.subplots(2, 2, figsize=(14, 10), dpi=200)
fig.suptitle("BLS Uncertainty (Sigma) Distributions", fontsize=16, fontweight='bold', y=0.98, color='#61afef')

# Period Sigma
sns.histplot(df['Period_sigma'], bins=50, kde=True, ax=axes[0, 0], color='#00c6ff', log_scale=True)
format_log_axis(axes[0, 0], axis='x')
axes[0, 0].set_title('Period Uncertainty (Period Sigma, days)', fontsize=12, fontweight='bold')
axes[0, 0].set_xlabel('Period Sigma (days)')

# Depth Sigma
sns.histplot(df['Depth_ppm_sigma'], bins=50, kde=True, ax=axes[0, 1], color='#f7797d', log_scale=True)
format_log_axis(axes[0, 1], axis='x')
axes[0, 1].set_title('Depth Uncertainty (Depth Sigma, ppm)', fontsize=12, fontweight='bold')
axes[0, 1].set_xlabel('Depth Sigma (ppm)')

# Duration Sigma
sns.histplot(df['Duration_hr_sigma'], bins=50, kde=True, ax=axes[1, 0], color='#fbd786', log_scale=True)
format_log_axis(axes[1, 0], axis='x')
axes[1, 0].set_title('Duration Uncertainty (Duration Sigma, hrs)', fontsize=12, fontweight='bold')
axes[1, 0].set_xlabel('Duration Sigma (hrs)')

# Epoch Sigma
sns.histplot(df['Epoch_sigma'], bins=50, kde=True, ax=axes[1, 1], color='#a8ff78', log_scale=True)
format_log_axis(axes[1, 1], axis='x')
axes[1, 1].set_title('Epoch Uncertainty (Epoch Sigma, days)', fontsize=12, fontweight='bold')
axes[1, 1].set_xlabel('Epoch Sigma (days)')

for ax in axes.flat:
    ax.grid(True, alpha=0.2)

plt.tight_layout(rect=[0, 0.03, 1, 0.95])

# Save Uncertainties Figure
fig3_path_local = os.path.join(output_dir, "bls_uncertainties_distribution.png")
fig3_path_artifact = os.path.join(artifact_dir, "bls_uncertainties_distribution.png")
plt.savefig(fig3_path_local, bbox_inches='tight')
plt.savefig(fig3_path_artifact, bbox_inches='tight')
plt.close()
print(f"Saved uncertainties plot to:\n  - {fig3_path_local}\n  - {fig3_path_artifact}")

print("Distribution plotting completed successfully!")
