# ==================== STAGE 1+2+3 : TRIAGE + VIEWS + FEATURES ====================
# Consumes the output of local_batch_pipeline.py directly:
#   PROCESSED_DIR / <sample_id>.csv   (TIME, FLUX, FLUX_ERR, TREND)
#   BLS_OUTPUT_DIR / {BATCH_NAME}_bls_summary.csv

import os
import numpy as np
import pandas as pd
from scipy import stats

# ==========================================
# 1. PATH CONFIGURATION -- match local_batch_pipeline.py, edit BATCH_NAME per batch
# ==========================================
BATCH_NAME = "batch_017"

PROCESSED_DIR  = r"D:\Bhartiya Antariksh Hackathon\ph3\batch_020-20260806T233212Z-1-001\Processed\batch_017"
BLS_OUTPUT_DIR = r"D:\Bhartiya Antariksh Hackathon\ph3\batch_020-20260806T233212Z-1-001\BlS_result\batch_017"
STAGE4_OUTPUT_DIR = os.path.join(BLS_OUTPUT_DIR, "stage4")

os.makedirs(STAGE4_OUTPUT_DIR, exist_ok=True)

BLS_SUMMARY_PATH = os.path.join(BLS_OUTPUT_DIR, f"{BATCH_NAME}_bls_summary.csv")
TRIAGE_LOG_PATH  = os.path.join(STAGE4_OUTPUT_DIR, f"{BATCH_NAME}_triage_log.csv")
FEATURES_PATH    = os.path.join(STAGE4_OUTPUT_DIR, f"{BATCH_NAME}_features.csv")
VIEWS_NPZ_PATH   = os.path.join(STAGE4_OUTPUT_DIR, f"{BATCH_NAME}_views.npz")

print(f"batch          : {BATCH_NAME}")
print(f"BLS summary    : {BLS_SUMMARY_PATH}")
print(f"processed dir  : {PROCESSED_DIR}")
print(f"stage4 outputs : {STAGE4_OUTPUT_DIR}\n")


# ==========================================
# STAGE 1 : TRIAGE / FILTER GATE
# ==========================================
SDE_MIN = 7.0
SNR_MIN = 3.0
MAX_DURATION_FRAC = 0.30
BASELINE_DAYS = 25.95
MONO_PERIOD_FRAC = 0.40
ODD_EVEN_SIGMA = 3.0


def triage_bls_row(bls_row):
    if bls_row is None:
        return dict(keep=False, reason="upstream_failed", n_transits=0.0, mono_flag=False)

    period = bls_row.get("Period")
    sde = bls_row.get("sde")
    depth_ppm = bls_row.get("Depth_ppm")
    depth_sigma = bls_row.get("Depth_ppm_sigma")
    duration_hr = bls_row.get("Duration_hr")

    if any(v is None or not np.isfinite(v) for v in [period, sde, depth_ppm, duration_hr]):
        return dict(keep=False, reason="upstream_failed", n_transits=0.0, mono_flag=False)

    if sde < SDE_MIN:
        return dict(keep=False, reason="low_sde", n_transits=0.0, mono_flag=False)

    depth_snr = depth_ppm / depth_sigma if depth_sigma and depth_sigma > 0 else 0.0
    if depth_snr < SNR_MIN:
        return dict(keep=False, reason="low_snr", n_transits=0.0, mono_flag=False)

    duration_frac = duration_hr / (period * 24.0)
    if duration_frac > MAX_DURATION_FRAC:
        return dict(keep=False, reason="bad_duration_ratio", n_transits=0.0, mono_flag=False)

    n_transits = BASELINE_DAYS / period
    mono_flag = period > (MONO_PERIOD_FRAC * BASELINE_DAYS)

    return dict(keep=True, reason=None, n_transits=n_transits, mono_flag=mono_flag)


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


def triage_one(sample_id, bls_row, time=None, flux=None):
    base = triage_bls_row(bls_row)
    base["sample_id"] = sample_id
    base["oe_flag"] = False
    base["oe_sigma"] = 0.0

    if base["keep"] and time is not None and flux is not None:
        oe = odd_even_test(time, flux, bls_row["Period"], bls_row["Epoch"], bls_row["Duration_hr"])
        base["oe_flag"] = oe["oe_flag"]
        base["oe_sigma"] = oe["oe_sigma"]

    return base


# ==========================================
# STAGE 2 : VIEW CONSTRUCTION
# ==========================================
GLOBAL_BINS = 512
LOCAL_BINS = 256
LOCAL_WINDOW_DURATIONS = 4.0


def phase_fold(time, period, epoch):
    return ((time - epoch) / period + 0.5) % 1.0 - 0.5


def _bin_phase_curve(phase, flux, n_bins, lo, hi):
    edges = np.linspace(lo, hi, n_bins + 1)
    bin_idx = np.digitize(phase, edges) - 1
    out = np.full(n_bins, np.nan, dtype=np.float64)
    for b in range(n_bins):
        sel = bin_idx == b
        if sel.any():
            out[b] = np.nanmedian(flux[sel])
    return out


def build_global_view(time, flux, period, epoch, n_bins=GLOBAL_BINS):
    phase = phase_fold(np.asarray(time), period, epoch)
    return _bin_phase_curve(phase, np.asarray(flux), n_bins, -0.5, 0.5)


def build_local_view(time, flux, period, epoch, duration_days,
                      n_bins=LOCAL_BINS, window_durations=LOCAL_WINDOW_DURATIONS):
    phase = phase_fold(np.asarray(time), period, epoch)
    half_win = (window_durations * duration_days) / (2.0 * period)
    half_win = min(half_win, 0.5)
    return _bin_phase_curve(phase, np.asarray(flux), n_bins, -half_win, half_win)


def build_views(time, flux, period, epoch, duration_hr):
    duration_days = duration_hr / 24.0
    g = build_global_view(time, flux, period, epoch)
    l = build_local_view(time, flux, period, epoch, duration_days)
    return g, l


# ==========================================
# STAGE 3 : FEATURE EXTRACTION
# ==========================================
FEATURES_BASELINE = [
    "g_min", "g_max", "g_std", "g_mean", "g_depth",
    "l_min", "l_max", "l_std", "l_depth",
    "g_nan", "l_nan", "g_ptp", "l_ptp",
]

FEATURES_PHYSICS = FEATURES_BASELINE + [
    "l_width50", "l_width10", "l_w_ratio", "l_bottom_std", "l_com_offset",
    "l_asym", "l_slope_dn", "l_slope_up", "l_area", "l_depth_area",
    "g_oot_std", "g_sec_depth", "g_sec_ratio", "snr_proxy", "g_n_sig_bins",
    "g_iqr", "g_skew", "l_skew", "g_kurt", "l_kurt", "g_ac1", "l_ac1",
    "l_over_g_depth", "g_p5", "g_p25", "g_p50", "g_p75", "g_p95",
    "l_p5", "l_p25", "l_p50", "l_p75", "l_p95",
]


def _ac1(x):
    x = x[~np.isnan(x)]
    if len(x) < 3:
        return 0.0
    x0, x1 = x[:-1] - np.mean(x), x[1:] - np.mean(x)
    denom = np.sqrt(np.sum(x0**2) * np.sum(x1**2))
    return float(np.sum(x0 * x1) / denom) if denom > 0 else 0.0


def extract_baseline_features(global_view, local_view):
    g, l = np.asarray(global_view, dtype=float), np.asarray(local_view, dtype=float)
    return {
        "g_min": float(np.nanmin(g)), "g_max": float(np.nanmax(g)),
        "g_std": float(np.nanstd(g)), "g_mean": float(np.nanmean(g)),
        "g_depth": float(-np.nanmin(g)),
        "l_min": float(np.nanmin(l)), "l_max": float(np.nanmax(l)),
        "l_std": float(np.nanstd(l)), "l_depth": float(-np.nanmin(l)),
        "g_nan": int(np.isnan(g).sum()), "l_nan": int(np.isnan(l).sum()),
        "g_ptp": float(np.nanmax(g) - np.nanmin(g)),
        "l_ptp": float(np.nanmax(l) - np.nanmin(l)),
    }


def extract_physics_features(global_view, local_view):
    feats = extract_baseline_features(global_view, local_view)
    g, l = np.asarray(global_view, dtype=float).copy(), np.asarray(local_view, dtype=float).copy()
    n_g, n_l = len(g), len(l)
    l_depth, g_depth = feats["l_depth"], feats["g_depth"]
    l_baseline = np.nanmedian(l)

    def width_at_frac(frac):
        thresh = l_baseline - frac * l_depth
        mask = (l < thresh) & ~np.isnan(l)
        return int(mask.sum())

    l_width50 = width_at_frac(0.5)
    l_width10 = width_at_frac(0.1)
    l_w_ratio = l_width50 / l_width10 if l_width10 > 0 else 0.0

    thresh50 = l_baseline - 0.5 * l_depth
    bottom_mask = (l < thresh50) & ~np.isnan(l)
    l_bottom_std = float(np.nanstd(l[bottom_mask])) if bottom_mask.sum() >= 2 else 0.0

    weights = np.nan_to_num(np.clip(l_baseline - l, 0, None), nan=0.0)
    bin_idx = np.arange(n_l)
    center = (n_l - 1) / 2.0
    if weights.sum() > 0:
        com = np.sum(bin_idx * weights) / np.sum(weights)
        l_com_offset = float((com - center) / n_l)
    else:
        l_com_offset = 0.0

    left, right = weights[: n_l // 2].sum(), weights[n_l // 2:].sum()
    l_asym = float((left - right) / (left + right)) if (left + right) > 0 else 0.0

    l_min_idx = int(np.nanargmin(l)) if np.isfinite(np.nanmin(l)) else n_l // 2
    k = max(2, n_l // 50)
    lo_idx, hi_idx = max(l_min_idx - k, 0), min(l_min_idx + k, n_l - 1)
    l_slope_dn = float((l[l_min_idx] - l[lo_idx]) / max(l_min_idx - lo_idx, 1)) if lo_idx < l_min_idx else 0.0
    l_slope_up = float((l[hi_idx] - l[l_min_idx]) / max(hi_idx - l_min_idx, 1)) if hi_idx > l_min_idx else 0.0

    l_area = float(np.nansum(np.clip(l_baseline - l, 0, None)) / n_l)
    l_depth_area = float(l_area / l_depth) if l_depth > 0 else 0.0

    g_center = (n_g - 1) / 2.0
    oot_mask = np.ones(n_g, dtype=bool)
    oot_mask[int(g_center - 0.1 * n_g): int(g_center + 0.1 * n_g)] = False
    g_oot_std = float(np.nanstd(g[oot_mask])) if oot_mask.any() else 0.0
    g_oot_median = float(np.nanmedian(g[oot_mask])) if oot_mask.any() else float(np.nanmedian(g))

    g_sec_depth = float(max(g_oot_median - np.nanmin(g[oot_mask]), 0.0)) if oot_mask.any() else 0.0
    g_sec_ratio = float(g_sec_depth / g_depth) if g_depth > 0 else 0.0

    snr_proxy = float(g_depth / g_oot_std) if g_oot_std > 0 else 0.0

    sig_mask = ((g_oot_median - g) > 3 * g_oot_std) & ~np.isnan(g)
    g_n_sig_bins = int(sig_mask.sum())

    g_valid, l_valid = g[~np.isnan(g)], l[~np.isnan(l)]
    g_iqr = float(np.nanpercentile(g, 75) - np.nanpercentile(g, 25))
    g_skew = float(stats.skew(g_valid)) if len(g_valid) > 2 else 0.0
    l_skew = float(stats.skew(l_valid)) if len(l_valid) > 2 else 0.0
    g_kurt = float(stats.kurtosis(g_valid)) if len(g_valid) > 2 else 0.0
    l_kurt = float(stats.kurtosis(l_valid)) if len(l_valid) > 2 else 0.0

    g_ac1, l_ac1 = _ac1(g), _ac1(l)
    l_over_g_depth = float(l_depth / g_depth) if g_depth > 0 else 0.0

    g_p5, g_p25, g_p50, g_p75, g_p95 = (float(x) for x in np.nanpercentile(g, [5, 25, 50, 75, 95]))
    l_p5, l_p25, l_p50, l_p75, l_p95 = (float(x) for x in np.nanpercentile(l, [5, 25, 50, 75, 95]))

    feats.update(dict(
        l_width50=l_width50, l_width10=l_width10, l_w_ratio=l_w_ratio,
        l_bottom_std=l_bottom_std, l_com_offset=l_com_offset, l_asym=l_asym,
        l_slope_dn=l_slope_dn, l_slope_up=l_slope_up, l_area=l_area, l_depth_area=l_depth_area,
        g_oot_std=g_oot_std, g_sec_depth=g_sec_depth, g_sec_ratio=g_sec_ratio,
        snr_proxy=snr_proxy, g_n_sig_bins=g_n_sig_bins, g_iqr=g_iqr,
        g_skew=g_skew, l_skew=l_skew, g_kurt=g_kurt, l_kurt=l_kurt,
        g_ac1=g_ac1, l_ac1=l_ac1, l_over_g_depth=l_over_g_depth,
        g_p5=g_p5, g_p25=g_p25, g_p50=g_p50, g_p75=g_p75, g_p95=g_p95,
        l_p5=l_p5, l_p25=l_p25, l_p50=l_p50, l_p75=l_p75, l_p95=l_p95,
    ))
    return feats


def to_ordered_vector(feats, feature_list):
    vec = np.array([feats.get(k, 0.0) for k in feature_list], dtype=float)
    bad = ~np.isfinite(vec)
    if bad.any():
        vec[bad] = 0.0
    return vec, bad.any()


# ==========================================
# RUNNER
# ==========================================
if not os.path.exists(BLS_SUMMARY_PATH):
    raise SystemExit(f"BLS summary not found: {BLS_SUMMARY_PATH}")

bls_df = pd.read_csv(BLS_SUMMARY_PATH)
print(f"loaded {len(bls_df)} BLS rows from {BLS_SUMMARY_PATH}\n")

triage_rows = []
feature_rows = []
views_store = {}

for _, row in bls_df.iterrows():
    sample_id = row['sample_id']
    bls_row = row.to_dict()

    # NOTE: PROCESSED_DIR files have TIME, FLUX, FLUX_ERR, TREND -- we only
    # need TIME/FLUX here for views + odd/even, matching local_batch_pipeline.py's output.
    detrended_path = os.path.join(PROCESSED_DIR, sample_id)
    time, flux = None, None
    if os.path.exists(detrended_path):
        star_df = pd.read_csv(detrended_path)
        if 'TIME' in star_df.columns and 'FLUX' in star_df.columns:
            time = star_df['TIME'].values
            flux = star_df['FLUX'].values

    result = triage_one(sample_id, bls_row, time=time, flux=flux)
    triage_rows.append(result)

    if result['keep'] and time is not None and flux is not None:
        g, l = build_views(time, flux, bls_row['Period'], bls_row['Epoch'], bls_row['Duration_hr'])
        feats_phys = extract_physics_features(g, l)

        feat_row = dict(sample_id=sample_id)
        feat_row.update({f"phys_{k}": v for k, v in feats_phys.items()})
        feat_row['n_transits'] = result['n_transits']
        feat_row['mono_flag'] = result['mono_flag']
        feat_row['oe_flag'] = result['oe_flag']
        feat_row['oe_sigma'] = result['oe_sigma']
        feature_rows.append(feat_row)

        key = sample_id.replace('.csv', '')
        views_store[f"{key}__global"] = g
        views_store[f"{key}__local"] = l
    # if keep=True but detrended file/columns missing, triage_log still
    # records it as kept from BLS stats alone -- no feature row is built.

triage_log = pd.DataFrame(triage_rows)
triage_log.to_csv(TRIAGE_LOG_PATH, index=False)

if feature_rows:
    features_df = pd.DataFrame(feature_rows)
    features_df.to_csv(FEATURES_PATH, index=False)
    np.savez(VIEWS_NPZ_PATH, **views_store)
else:
    features_df = pd.DataFrame()
    print("No candidates passed triage -- no features/views file written.")

# ==========================================
# SUMMARY
# ==========================================
n_total = len(triage_log)
n_kept = triage_log['keep'].sum()
n_with_features = len(feature_rows)
n_oe_flagged = triage_log.loc[triage_log['keep'], 'oe_flag'].sum() if n_kept else 0
n_mono = triage_log.loc[triage_log['keep'], 'mono_flag'].sum() if n_kept else 0

print("=" * 58)
print(f"  {BATCH_NAME} -- TRIAGE + FEATURE EXTRACTION REPORT")
print("=" * 58)
print(f"  total BLS rows       : {n_total}")
print(f"  passed triage        : {n_kept}   ({100*n_kept/max(n_total,1):.1f}%)")
print(f"  with features built  : {n_with_features}")
print(f"  odd/even flagged     : {n_oe_flagged}  (likely EB-at-half-period)")
print(f"  mono-transit flagged : {n_mono}  (period > {MONO_PERIOD_FRAC} x baseline)")
print("  reject reason breakdown (Stage 1 gate only):")
for k, v in triage_log.loc[~triage_log['keep'], 'reason'].value_counts().items():
    print(f"      {k:24s} {v}")
print("-" * 58)
print(f"  triage log  -> {TRIAGE_LOG_PATH}")
print(f"  features    -> {FEATURES_PATH}")
print(f"  views (npz) -> {VIEWS_NPZ_PATH}")
print("=" * 58)