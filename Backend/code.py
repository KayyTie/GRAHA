# ==================== STAGE 1 SURVIVORS & PHASE FOLDING PIPELINE ====================
import os
import glob
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.ticker as ticker

# Register Windows fonts if needed
for font_path in glob.glob(r'C:\Windows\Fonts\*.ttf'):
    try:
        fm.fontManager.addfont(font_path)
    except Exception:
        pass

matplotlib.rcParams['font.family'] = 'Arial'
matplotlib.rcParams['font.sans-serif'] = ['Arial', 'Segoe UI', 'Tahoma', 'sans-serif']
matplotlib.rcParams['axes.formatter.use_mathtext'] = False
plt.style.use('dark_background')

# ==========================================
# 1. PATH CONFIGURATION
# ==========================================
BASE_DIR = r"D:\Bhartiya Antariksh Hackathon\ph3\batch_020-20260806T233212Z-1-001"
BLS_RESULT_CSV = os.path.join(BASE_DIR, "BLS_result", "blsresult.csv")
PROCESSED_DIR  = os.path.join(BASE_DIR, "Processed")
OUTPUT_PLOT_DIR = os.path.join(BASE_DIR, "BLS_result", "phase_plots")
ARTIFACT_DIR   = r"C:\Users\kusha\.gemini\antigravity-ide\brain\461c4e48-6766-4634-80d2-ae6a974bd9b1"

os.makedirs(OUTPUT_PLOT_DIR, exist_ok=True)
os.makedirs(ARTIFACT_DIR, exist_ok=True)

# Triage Constants
SDE_MIN = 7.0
SNR_MIN = 3.0
MAX_DURATION_FRAC = 0.30
BASELINE_DAYS = 25.95
MONO_PERIOD_FRAC = 0.40
ODD_EVEN_SIGMA = 3.0

GAP_LO, GAP_HI = 1418.30, 1425.60

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def is_epoch_in_gap(epoch, buffer=0.2):
    return (GAP_LO - buffer) <= epoch <= (GAP_HI + buffer)

def odd_even_test(time, flux, period, epoch, duration_hr):
    time = np.asarray(time, dtype=float)
    flux = np.asarray(flux, dtype=float)
    duration_days = duration_hr / 24.0
    half_win = max(duration_days * 0.5, 1e-4)

    epoch_idx = np.round((time - epoch) / period).astype(int)
    phase = (time - epoch) - epoch_idx * period
    in_transit = np.abs(phase) < half_win

    odd_mask = in_transit & (epoch_idx % 2 != 0)
    even_mask = in_transit & (epoch_idx % 2 == 0)

    if odd_mask.sum() < 5 or even_mask.sum() < 5:
        return dict(oe_flag=False, oe_sigma=0.0, depth_odd=np.nan, depth_even=np.nan)

    depth_odd = -np.nanmedian(flux[odd_mask])
    depth_even = -np.nanmedian(flux[even_mask])
    err_odd = np.nanstd(flux[odd_mask]) / np.sqrt(odd_mask.sum())
    err_even = np.nanstd(flux[even_mask]) / np.sqrt(even_mask.sum())
    combined_err = np.sqrt(err_odd**2 + err_even**2) or 1e-9

    oe_sigma = abs(depth_odd - depth_even) / combined_err
    return dict(
        oe_flag=bool(oe_sigma > ODD_EVEN_SIGMA),
        oe_sigma=float(oe_sigma),
        depth_odd=float(depth_odd),
        depth_even=float(depth_even),
    )

def phase_fold(time, period, epoch):
    return ((time - epoch) / period + 0.5) % 1.0 - 0.5

def bin_phase_curve(phase, flux, n_bins=200):
    edges = np.linspace(-0.5, 0.5, n_bins + 1)
    bin_centers = 0.5 * (edges[:-1] + edges[1:])
    bin_idx = np.digitize(phase, edges) - 1
    binned_flux = np.full(n_bins, np.nan)
    for b in range(n_bins):
        sel = bin_idx == b
        if sel.any():
            binned_flux[b] = np.nanmedian(flux[sel])
    return bin_centers, binned_flux

# ==========================================
# 3. LOAD DATA & MAP LIGHTCURVES
# ==========================================
print(f"Loading BLS result from: {BLS_RESULT_CSV}")
bls_df = pd.read_csv(BLS_RESULT_CSV)
print(f"Total targets loaded: {len(bls_df)}")

# Map sample_id to processed CSV filepath
print("Mapping processed lightcurves...")
lc_map = {}
for root, dirs, files in os.walk(PROCESSED_DIR):
    for f in files:
        if f.endswith(".csv"):
            lc_map[f] = os.path.join(root, f)
print(f"Mapped {len(lc_map)} processed lightcurve files.")

# Add calculated columns
bls_df['depth_snr'] = bls_df['Depth_ppm'] / bls_df['Depth_ppm_sigma'].replace(0, np.nan)
bls_df['duration_frac'] = bls_df['Duration_hr'] / (bls_df['Period'] * 24.0)
bls_df['n_transits'] = BASELINE_DAYS / bls_df['Period']
bls_df['mono_flag'] = bls_df['Period'] > (MONO_PERIOD_FRAC * BASELINE_DAYS)

# Triage Filter
bls_df['triage_keep'] = (
    (bls_df['sde'] >= SDE_MIN) &
    (bls_df['depth_snr'] >= SNR_MIN) &
    (bls_df['duration_frac'] <= MAX_DURATION_FRAC)
)

kept = bls_df[bls_df['triage_keep']].copy()
print(f"\nPassed Primary Triage (SDE >= {SDE_MIN}, SNR >= {SNR_MIN}, Duration Frac <= {MAX_DURATION_FRAC}): {len(kept)} / {len(bls_df)}")

# Run Odd/Even and Gap tests on kept targets
oe_flags, oe_sigmas, in_gaps = [], [], []
for idx, row in kept.iterrows():
    sid = row['sample_id']
    period, epoch, dur_hr = row['Period'], row['Epoch'], row['Duration_hr']
    
    # Gap test
    ng = is_epoch_in_gap(epoch)
    in_gaps.append(ng)
    
    # Odd/Even test if lightcurve available
    if sid in lc_map:
        try:
            lcdf = pd.read_csv(lc_map[sid])
            oe = odd_even_test(lcdf['TIME'].values, lcdf['FLUX'].values, period, epoch, dur_hr)
            oe_flags.append(oe['oe_flag'])
            oe_sigmas.append(oe['oe_sigma'])
        except Exception:
            oe_flags.append(False)
            oe_sigmas.append(0.0)
    else:
        oe_flags.append(False)
        oe_sigmas.append(0.0)

kept['oe_flag'] = oe_flags
kept['oe_sigma'] = oe_sigmas
kept['epoch_in_gap'] = in_gaps

# ==========================================
# 4. PRINT TRIAGE REPORT
# ==========================================
print("\n" + "=" * 75)
print(f"TOP SURVIVORS (sorted by SDE, showing top 20 of {len(kept)})")
print("=" * 75)
print(kept[['sample_id', 'Period', 'sde', 'Depth_ppm', 'Duration_hr', 'oe_flag', 'epoch_in_gap']]
      .sort_values('sde', ascending=False).head(20).to_string(index=False))

oe_flagged = kept[kept['oe_flag']]
print("\n" + "=" * 75)
print(f"ODD/EVEN FLAGGED -- likely Eclipsing Binary at half-period ({len(oe_flagged)} of {len(kept)})")
print("=" * 75)
if len(oe_flagged):
    print(oe_flagged[['sample_id', 'Period', 'sde', 'oe_sigma', 'Depth_ppm']].head(10).to_string(index=False))
else:
    print("(none)")

rejected = bls_df[~bls_df['triage_keep']].copy()
dur_rejects = rejected[rejected['duration_frac'] > MAX_DURATION_FRAC].sort_values('duration_frac')
borderline = dur_rejects[dur_rejects['duration_frac'] < 0.40]
print("\n" + "=" * 75)
print(f"BORDERLINE DURATION REJECTS (0.30 <= Duration Frac < 0.40): {len(borderline)}")
print("=" * 75)
if len(borderline):
    print(borderline[['sample_id', 'Period', 'Duration_hr', 'duration_frac', 'sde']].head(10).to_string(index=False))

epoch_gap_targets = kept[kept['epoch_in_gap']]
print("\n" + "=" * 75)
print(f"CANDIDATES WITH EPOCH INSIDE GAP WINDOW ({len(epoch_gap_targets)} of {len(kept)})")
print("=" * 75)
if len(epoch_gap_targets):
    print(epoch_gap_targets[['sample_id', 'Period', 'Epoch', 'sde', 'n_transits']].head(10).to_string(index=False))

clean_candidates = kept[~kept['oe_flag']].sort_values('sde', ascending=False)
print("\n" + "=" * 75)
print("TRIAGE SUMMARY")
print("=" * 75)
print(f"  Total targets in dataset   : {len(bls_df)}")
print(f"  Passed primary triage      : {len(kept)}")
print(f"  Odd/Even flagged (EB-like) : {len(oe_flagged)}")
print(f"  Epoch inside gap window    : {len(epoch_gap_targets)}")
print(f"  Clean Planetary Candidates : {len(clean_candidates)}")
print("=" * 75)

# Save Clean Candidates CSV
clean_csv_path = os.path.join(BASE_DIR, "BLS_result", "clean_candidates.csv")
clean_candidates.to_csv(clean_csv_path, index=False)
print(f"\nSaved clean candidates to: {clean_csv_path}")

# ==========================================
# 5. GENERATE PHASE FOLDING GRAPHS
# ==========================================
print("\nGenerating phase folding graphs for top candidate signals...")

def plot_phase_folding(sample_id, row, lc_path, out_dir):
    try:
        lcdf = pd.read_csv(lc_path)
        time = lcdf['TIME'].values
        flux = lcdf['FLUX'].values
        
        period = row['Period']
        epoch  = row['Epoch']
        depth_ppm = row['Depth_ppm']
        duration_hr = row['Duration_hr']
        sde = row['sde']
        
        phase = phase_fold(time, period, epoch)
        bin_centers, bin_flux = bin_phase_curve(phase, flux, n_bins=200)
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10), dpi=180)
        fig.suptitle(f"Phase Folded Light Curve: {sample_id}\nPeriod = {period:.6f} d | Depth = {depth_ppm:.1f} ppm | SDE = {sde:.2f}",
                     fontsize=15, fontweight='bold', color='#61afef', y=0.98)
        
        # Panel 1: Full Detrended Light Curve
        axes[0, 0].scatter(time, flux, s=2, color='#4facfe', alpha=0.4, label='Detrended Flux')
        axes[0, 0].set_title('Full Detrended Light Curve', fontsize=12, fontweight='bold')
        axes[0, 0].set_xlabel('Time (BTJD)')
        axes[0, 0].set_ylabel('Normalized Flux')
        axes[0, 0].grid(True, alpha=0.2)
        axes[0, 0].legend(loc='upper right')
        
        # Panel 2: Global Phase Fold (-0.5 to 0.5)
        axes[0, 1].scatter(phase, flux, s=2, color='#00f2fe', alpha=0.25, label='Raw Phase Points')
        valid_bin = ~np.isnan(bin_flux)
        axes[0, 1].plot(bin_centers[valid_bin], bin_flux[valid_bin], color='#e06c75', linewidth=2.0, label='Binned Median')
        axes[0, 1].set_title('Global Phase Fold (-0.5 to +0.5)', fontsize=12, fontweight='bold')
        axes[0, 1].set_xlabel('Phase')
        axes[0, 1].set_ylabel('Normalized Flux')
        axes[0, 1].grid(True, alpha=0.2)
        axes[0, 1].legend(loc='upper right')
        
        # Panel 3: Zoomed In-Transit Phase Fold
        dur_phase = (duration_hr / 24.0) / period
        zoom_win = max(dur_phase * 3.0, 0.04)
        zoom_mask = np.abs(phase) <= zoom_win
        
        axes[1, 0].scatter(phase[zoom_mask], flux[zoom_mask], s=6, color='#43e97b', alpha=0.4, label='In-transit Phase')
        bin_z_centers, bin_z_flux = bin_phase_curve(phase[zoom_mask], flux[zoom_mask], n_bins=80)
        valid_z = ~np.isnan(bin_z_flux)
        axes[1, 0].plot(bin_z_centers[valid_z], bin_z_flux[valid_z], color='#fee140', linewidth=2.5, label='Binned Median')
        
        # Draw transit depth line
        expected_depth = 1.0 - (depth_ppm / 1e6)
        axes[1, 0].axhline(expected_depth, color='#fa709a', linestyle='--', linewidth=1.5, label=f'Depth: {depth_ppm:.1f} ppm')
        axes[1, 0].set_title('Zoomed In-Transit Phase Fold', fontsize=12, fontweight='bold')
        axes[1, 0].set_xlabel('Phase (centered at 0)')
        axes[1, 0].set_ylabel('Normalized Flux')
        axes[1, 0].set_xlim(-zoom_win, zoom_win)
        axes[1, 0].grid(True, alpha=0.2)
        axes[1, 0].legend(loc='lower right')
        
        # Panel 4: Candidate Parameter Summary Table
        axes[1, 1].axis('off')
        summary_text = [
            ["Target Sample ID", f"{sample_id}"],
            ["Orbital Period", f"{period:.6f} days"],
            ["Transit Epoch", f"{epoch:.4f} BTJD"],
            ["Transit Depth", f"{depth_ppm:.2f} ppm"],
            ["Depth SNR", f"{row['depth_snr']:.2f}"],
            ["Transit Duration", f"{duration_hr:.3f} hours"],
            ["Signal Efficiency (SDE)", f"{sde:.2f}"],
            ["Odd/Even EB Flag", f"{row['oe_flag']} (sigma={row['oe_sigma']:.2f})"],
            ["Epoch In Gap Window", f"{row['epoch_in_gap']}"],
            ["Est. Transits in Baseline", f"{row['n_transits']:.1f}"]
        ]
        table = axes[1, 1].table(cellText=summary_text, loc='center', cellLoc='left')
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1.2, 1.8)

        # Style table cells
        for (r, c), cell in table.get_celld().items():
            cell.set_facecolor('#1e1e2e')
            cell.set_edgecolor('#313244')
            cell.set_text_props(color='#cdd6f4', fontweight='bold' if c == 0 else 'normal')

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        
        out_name = f"{sample_id.replace('.csv', '')}_phase_fold.png"
        p_local = os.path.join(out_dir, out_name)
        p_artifact = os.path.join(ARTIFACT_DIR, out_name)
        
        plt.savefig(p_local, bbox_inches='tight')
        plt.savefig(p_artifact, bbox_inches='tight')
        plt.close()
        return p_local
    except Exception as e:
        print(f"  Error plotting {sample_id}: {e}")
        return None

# Plot top 15 clean candidates
top_candidates = clean_candidates.head(15)
saved_plots = []
for idx, row in top_candidates.iterrows():
    sid = row['sample_id']
    if sid in lc_map:
        res = plot_phase_folding(sid, row, lc_map[sid], OUTPUT_PLOT_DIR)
        if res:
            saved_plots.append(res)
            print(f"  Generated phase fold plot for {sid} -> {os.path.basename(res)}")

print(f"\nSuccessfully generated {len(saved_plots)} phase folding graphs in:\n  - {OUTPUT_PLOT_DIR}\n  - {ARTIFACT_DIR}")
print("code.py execution complete!")