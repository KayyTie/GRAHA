import os, glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

import matplotlib.font_manager as fm
for font_file in glob.glob(r'C:\Windows\Fonts\*.ttf'):
    try:
        fm.fontManager.addfont(font_file)
    except Exception:
        pass

OUT_DIR = r"C:\Users\kusha\.gemini\antigravity-ide\brain\461c4e48-6766-4634-80d2-ae6a974bd9b1\Planet_Plots"
os.makedirs(OUT_DIR, exist_ok=True)

# Load the current successful pipeline outputs (SDE >= 7 run)
qc_df = pd.read_csv("submission/internal_full_with_qc.csv")
planets = qc_df[qc_df['Final_Class'] == 'PLANET'].sort_values('P_Planet', ascending=False)

# Map sample_ids to their Processed file paths
proc_files = glob.glob("Processed/**/*.csv", recursive=True)
path_map = {os.path.basename(p): p for p in proc_files}

def phase_fold(time, period, epoch):
    return ((time - epoch) / period + 0.5) % 1.0 - 0.5

print(f"Plotting {len(planets)} planet candidates...")

markdown_lines = ["# 🪐 Detected Planet Candidates Analysis", ""]
markdown_lines.append("Here are the detailed phase-folded light curves and full transit views for the top planet candidates we detected.")
markdown_lines.append("")

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
    
    phase = phase_fold(time, per, epo)
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    # Top: Full Lightcurve
    ax1.plot(time, flux, 'k.', markersize=2, alpha=0.5, label='Processed Flux')
    
    # Mark transits
    n_transits = int((time.max() - time.min()) / per)
    for j in range(-1, n_transits + 2):
        t_mid = epo + j * per
        if time.min() <= t_mid <= time.max():
            ax1.axvline(t_mid, color='r', linestyle='--', alpha=0.5)
            ax1.axvspan(t_mid - (dur_hr/24.0)/2, t_mid + (dur_hr/24.0)/2, color='r', alpha=0.2)
            
    ax1.set_title(f"Full Lightcurve: {sid} (P_Planet: {p_planet:.3f})")
    ax1.set_xlabel("Time (BJD)")
    ax1.set_ylabel("Relative Flux")
    ax1.legend(loc='upper right')
    
    # Bottom: Phase Folded
    ax2.plot(phase, flux, 'k.', markersize=2, alpha=0.5, label='Folded Flux')
    
    # Binned global view
    bins = 512
    edges = np.linspace(-0.5, 0.5, bins + 1)
    bin_centers = 0.5 * (edges[:-1] + edges[1:])
    bin_idx = np.digitize(phase, edges) - 1
    bin_flux = np.array([np.nanmedian(flux[bin_idx == b]) if (bin_idx == b).any() else np.nan for b in range(bins)])
    
    ax2.plot(bin_centers, bin_flux, 'r-', linewidth=2, label='Binned (512)')
    
    # Highlight the transit window
    hw = min((4.0 * dur_hr / 24.0) / (2.0 * per), 0.5)
    ax2.axvspan(-hw, hw, color='orange', alpha=0.2, label='Local View Window')
    
    ax2.set_title(f"Phase Folded (Period: {per:.4f} d, Depth: {row['Depth_ppm']:.1f} ppm, Rp/R*: {rp_rs:.3f})")
    ax2.set_xlabel("Phase")
    ax2.set_ylabel("Relative Flux")
    ax2.set_xlim(-0.5, 0.5)
    ax2.legend(loc='upper right')
    
    plt.tight_layout()
    plot_file = os.path.join(OUT_DIR, f"{sid.replace('.csv', '')}_plot.png")
    plt.savefig(plot_file, dpi=100, bbox_inches='tight')
    plt.close()
    
    # Add to markdown artifact
    markdown_lines.append(f"### {sid}")
    markdown_lines.append(f"- **P_Planet Confidence:** {p_planet:.3f}")
    markdown_lines.append(f"- **Period:** {per:.4f} days")
    markdown_lines.append(f"- **Depth:** {row['Depth_ppm']:.1f} ppm")
    markdown_lines.append(f"- **Radius Ratio (Rp/R★):** {rp_rs:.4f}")
    markdown_lines.append(f"- **Duration:** {dur_hr:.2f} hours")
    markdown_lines.append(f"\n![{sid} Plot](/C:/Users/kusha/.gemini/antigravity-ide/brain/461c4e48-6766-4634-80d2-ae6a974bd9b1/Planet_Plots/{sid.replace('.csv', '')}_plot.png)\n")
    markdown_lines.append("---\n")

# Write the markdown
with open(r"C:\Users\kusha\.gemini\antigravity-ide\brain\461c4e48-6766-4634-80d2-ae6a974bd9b1\Planet_Analysis.md", "w", encoding='utf-8') as f:
    f.write("\n".join(markdown_lines))

print("Done generating plots and Planet_Analysis.md")
