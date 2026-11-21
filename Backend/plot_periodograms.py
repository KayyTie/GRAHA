import os, glob, warnings
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from astropy.timeseries import BoxLeastSquares

warnings.filterwarnings('ignore')

# Load Windows fonts for matplotlib
for font_file in glob.glob(r'C:\Windows\Fonts\*.ttf'):
    try:
        fm.fontManager.addfont(font_file)
    except Exception:
        pass

OUT_DIR_ARTIFACT = r"C:\Users\kusha\.gemini\antigravity-ide\brain\461c4e48-6766-4634-80d2-ae6a974bd9b1\Planet_Periodogram_Plots"
OUT_DIR_WORKSPACE = "Planet_Periodogram_Plots"
os.makedirs(OUT_DIR_ARTIFACT, exist_ok=True)
os.makedirs(OUT_DIR_WORKSPACE, exist_ok=True)

# Load planet candidates
qc_df = pd.read_csv("submission/internal_full_with_qc.csv")
planets = qc_df[qc_df['Final_Class'] == 'PLANET'].sort_values('P_Planet', ascending=False)

# Map sample_ids to Processed file paths
proc_files = glob.glob("Processed/**/*.csv", recursive=True)
path_map = {os.path.basename(p): p for p in proc_files}

def phase_fold(time, period, epoch):
    return ((time - epoch) / period + 0.5) % 1.0 - 0.5

print(f"Generating periodograms and phase-folded plots for {len(planets)} candidates...")

markdown_lines = [
    "# 📡 Exoplanet Periodogram & Phase-Folded Light Curves",
    "",
    "This document presents the **BLS Power Spectrum (Periodogram)** alongside the **Full Light Curve** and **Phase-Folded Transit View** for each of the 38 detected planet candidates.",
    ""
]

for i, row in planets.iterrows():
    sid = row['sample_id']
    if sid not in path_map:
        continue
        
    lc = pd.read_csv(path_map[sid])
    time = lc['TIME'].values
    flux = lc['FLUX'].values
    flux = flux - np.nanmedian(flux)  # Mean-0 centered
    
    per = row['Period']
    epo = row['Epoch']
    dur_hr = row['Duration_hr']
    p_planet = row['P_Planet']
    rp_rs = row['Rp_Rstar']
    sde = row.get('sde', 10.0)
    
    # Compute BLS Periodogram
    dur_days = max(dur_hr / 24.0, 0.02)
    bls = BoxLeastSquares(time, flux)
    periods = np.linspace(max(0.4, per * 0.2), min(15.0, max(per * 2.5, 10.0)), 1500)
    bls_power = bls.power(periods, dur_days)
    
    phase = phase_fold(time, per, epo)
    
    # Create 3-panel plot
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 13))
    
    # --- Panel 1: BLS Periodogram ---
    ax1.plot(bls_power.period, bls_power.power, 'b-', linewidth=1.2, label='BLS Power Spectrum')
    ax1.axvline(per, color='r', linestyle='--', linewidth=1.5, label=f'Best Period: {per:.4f} d')
    if per * 2 <= max(periods):
        ax1.axvline(per * 2, color='gray', linestyle=':', label='Harmonic (2P)')
    if per / 2 >= min(periods):
        ax1.axvline(per / 2, color='gray', linestyle=':', label='Harmonic (P/2)')
        
    ax1.set_title(f"BLS Periodogram: {sid} (Detected Period P = {per:.4f} d, SDE = {sde:.1f})")
    ax1.set_xlabel("Period (days)")
    ax1.set_ylabel("BLS Power")
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)
    
    # --- Panel 2: Full Lightcurve ---
    ax2.plot(time, flux, 'k.', markersize=2, alpha=0.5, label='Processed Flux')
    n_transits = int((time.max() - time.min()) / per)
    for j in range(-1, n_transits + 2):
        t_mid = epo + j * per
        if time.min() <= t_mid <= time.max():
            ax2.axvline(t_mid, color='r', linestyle='--', alpha=0.5)
            ax2.axvspan(t_mid - (dur_hr/24.0)/2, t_mid + (dur_hr/24.0)/2, color='r', alpha=0.2)
            
    ax2.set_title(f"Full Light Curve (P_Planet Confidence: {p_planet:.3f})")
    ax2.set_xlabel("Time (BJD)")
    ax2.set_ylabel("Relative Flux")
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)
    
    # --- Panel 3: Phase Folded Light Curve ---
    ax3.plot(phase, flux, 'k.', markersize=2, alpha=0.4, label='Folded Data')
    
    # Binned global view
    bins = 512
    edges = np.linspace(-0.5, 0.5, bins + 1)
    bin_centers = 0.5 * (edges[:-1] + edges[1:])
    bin_idx = np.digitize(phase, edges) - 1
    bin_flux = np.array([np.nanmedian(flux[bin_idx == b]) if (bin_idx == b).any() else np.nan for b in range(bins)])
    
    ax3.plot(bin_centers, bin_flux, 'r-', linewidth=2, label='Binned View (512 bins)')
    
    hw = min((4.0 * dur_hr / 24.0) / (2.0 * per), 0.5)
    ax3.axvspan(-hw, hw, color='orange', alpha=0.2, label='Transit Window')
    
    ax3.set_title(f"Phase-Folded Light Curve (Period: {per:.4f} d | Depth: {row['Depth_ppm']:.1f} ppm | Rp/R*: {rp_rs:.4f})")
    ax3.set_xlabel("Phase")
    ax3.set_ylabel("Relative Flux")
    ax3.set_xlim(-0.5, 0.5)
    ax3.legend(loc='upper right')
    ax3.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save to both artifact and workspace
    img_name = f"{sid.replace('.csv', '')}_periodogram.png"
    file_art = os.path.join(OUT_DIR_ARTIFACT, img_name)
    file_ws  = os.path.join(OUT_DIR_WORKSPACE, img_name)
    
    plt.savefig(file_art, dpi=100, bbox_inches='tight')
    plt.savefig(file_ws,  dpi=100, bbox_inches='tight')
    plt.close()
    
    # Add entry to markdown document
    markdown_lines.append(f"### 🪐 {sid}")
    markdown_lines.append(f"- **Planet Confidence (P_Planet):** `{p_planet:.3f}`")
    markdown_lines.append(f"- **Detected Period:** `{per:.4f}` days")
    markdown_lines.append(f"- **Transit Depth:** `{row['Depth_ppm']:.1f}` ppm")
    markdown_lines.append(f"- **Radius Ratio (Rp/R★):** `{rp_rs:.4f}`")
    markdown_lines.append(f"- **Transit Duration:** `{dur_hr:.2f}` hours")
    markdown_lines.append(f"- **BLS SDE:** `{sde:.1f}`")
    markdown_lines.append(f"\n![{sid} Periodogram & Phase Folded](/C:/Users/kusha/.gemini/antigravity-ide/brain/461c4e48-6766-4634-80d2-ae6a974bd9b1/Planet_Periodogram_Plots/{img_name})\n")
    markdown_lines.append("---\n")

# Save markdown document as artifact
with open(r"C:\Users\kusha\.gemini\antigravity-ide\brain\461c4e48-6766-4634-80d2-ae6a974bd9b1\Planet_Periodograms.md", "w", encoding='utf-8') as f:
    f.write("\n".join(markdown_lines))

print("Finished generating all periodogram and phase-folded plots!")
