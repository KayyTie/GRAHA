"""
Stage 1 : TRIAGE / FILTER GATE
================================
Runs before any view construction, feature extraction, or model call.
Decides, per sample_id, whether a BLS result is worth handing to the
classifier at all, or whether it's cheaper (and more honest) to call it
'UNKNOWN' straight away.

Consumes: a row from your *_bls_summary.csv (Period, Period_sigma, Epoch,
          Epoch_sigma, Depth_ppm, Depth_ppm_sigma, Duration_hr,
          Duration_hr_sigma, sde) PLUS the raw detrended (TIME, FLUX)
          arrays for the odd/even check.

Produces: a dict per sample with `keep` (bool), `reason` (str, only set
          when keep=False), and QC flags (`oe_flag`, `mono_flag`,
          `n_transits`) that Stage 4 can use as soft evidence.
"""

import numpy as np

# ---- tunable thresholds -----------------------------------------------
SDE_MIN = 7.0                 # below this, BLS peak is indistinguishable from noise
SNR_MIN = 3.0                 # Depth_ppm / Depth_ppm_sigma
MAX_DURATION_FRAC = 0.30      # Duration_hr / (Period_days * 24); real transits/eclipses are narrow
BASELINE_DAYS = 25.95         # TESS sector length, from DATA_ANALYSIS.md
MONO_PERIOD_FRAC = 0.40       # Period > this * baseline -> only ~1 transit observed
ODD_EVEN_SIGMA = 3.0          # odd/even depth mismatch threshold (EB-at-half-period sign)


def triage_bls_row(bls_row):
    """
    Cheap, BLS-statistics-only gate. Does not need the raw light curve.

    Parameters
    ----------
    bls_row : dict-like with keys Period, Depth_ppm, Depth_ppm_sigma,
              Duration_hr, sde (matches your bls_summary.csv columns)

    Returns
    -------
    dict(keep: bool, reason: str|None, n_transits: float, mono_flag: bool)
    """
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
    """
    Soft evidence flag, not a hard gate. Splits transits by odd/even
    epoch index and compares in-transit depths. A large, significant
    mismatch is the classic signature of an eclipsing binary detected
    at half its true period (primary/secondary masquerading as one
    shallower "transit").

    Returns
    -------
    dict(oe_flag: bool, oe_sigma: float, depth_odd: float, depth_even: float)
    Returns oe_flag=False, oe_sigma=0.0 if too few transits to test.
    """
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
    """
    Full Stage-1 decision for one candidate. Pass the detrended (time,
    flux) arrays too if you want the odd/even soft-flag attached (cheap
    relative to Stage 2-4, worth always doing when data is available).
    """
    base = triage_bls_row(bls_row)
    base["sample_id"] = sample_id
    base["oe_flag"] = False
    base["oe_sigma"] = 0.0

    if base["keep"] and time is not None and flux is not None:
        oe = odd_even_test(time, flux, bls_row["Period"], bls_row["Epoch"], bls_row["Duration_hr"])
        base["oe_flag"] = oe["oe_flag"]
        base["oe_sigma"] = oe["oe_sigma"]

    return base

"""
Stage 2 : VIEW CONSTRUCTION
============================
Turns a triage-approved candidate (detrended TIME/FLUX + BLS Period/
Epoch/Duration) into the same global(512) / local(256) phase-folded,
binned representation the curated training .npz files use — this is
what makes the target-set features comparable to what the classifiers
were trained on.

NOTE: this reproduces the *shape* of the training representation
(binned median flux per phase bin, NaN where a bin has no points).
It does not know the exact bin-edge / normalization convention your
team used when building CuratedTrainingDataset. If you still have that
script, prefer it — matching it exactly matters more than anything
below.
"""

import numpy as np

GLOBAL_BINS = 512
LOCAL_BINS = 256
LOCAL_WINDOW_DURATIONS = 4.0  # local view spans +/- 2x duration (AstroNet-style zoom)


def phase_fold(time, period, epoch):
    """Return phase in [-0.5, 0.5), transit centered at phase 0."""
    phase = ((time - epoch) / period + 0.5) % 1.0 - 0.5
    return phase


def _bin_phase_curve(phase, flux, n_bins, lo, hi):
    """
    Median-bin flux over [lo, hi) in phase into n_bins. Bins with no
    points are left as NaN (matches the 'occasional NaNs' noted in
    DATA_ANALYSIS.md for the curated views).
    """
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
    half_win = min(half_win, 0.5)  # never exceed a full phase cycle
    return _bin_phase_curve(phase, np.asarray(flux), n_bins, -half_win, half_win)


def build_views(time, flux, period, epoch, duration_hr):
    """Convenience wrapper returning (global_view, local_view)."""
    duration_days = duration_hr / 24.0
    g = build_global_view(time, flux, period, epoch)
    l = build_local_view(time, flux, period, epoch, duration_days)
    return g, l

"""
Stage 3 : FEATURE EXTRACTION
==============================
Turns (global_view, local_view) into the two feature sets your models
were trained on.

The 13-feature `features_baseline` set is verified EXACTLY against
training_sample_stats.csv (g_depth = -g_min, etc. all check out).

The 31 additional `features_physics` columns are NOT present in any
file you gave me, so these are best-effort, clearly-documented,
standard transit-vetting definitions (width ratios, secondary-eclipse
depth, odd-even-adjacent shape stats, etc). >>> If you (or a teammate)
still have the original feature-engineering script used to train
xgb_phys, use that instead of this file. A silent mismatch between how
features_physics was computed at train time vs here will quietly
tank accuracy below the 78.5% CV number in metrics.json, with no error
to warn you. <<<
"""

import numpy as np
from scipy import stats

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

assert FEATURES_PHYSICS == [
    "g_min", "g_max", "g_std", "g_mean", "g_depth", "l_min", "l_max", "l_std", "l_depth",
    "g_nan", "l_nan", "g_ptp", "l_ptp", "l_width50", "l_width10", "l_w_ratio", "l_bottom_std",
    "l_com_offset", "l_asym", "l_slope_dn", "l_slope_up", "l_area", "l_depth_area", "g_oot_std",
    "g_sec_depth", "g_sec_ratio", "snr_proxy", "g_n_sig_bins", "g_iqr", "g_skew", "l_skew",
    "g_kurt", "l_kurt", "g_ac1", "l_ac1", "l_over_g_depth", "g_p5", "g_p25", "g_p50", "g_p75",
    "g_p95", "l_p5", "l_p25", "l_p50", "l_p75", "l_p95",
], "feature order drifted from metrics.json — fix before training/inference mismatch happens"


def _ac1(x):
    """Lag-1 autocorrelation — separates structured dips from pure noise."""
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
    """Best-effort reconstruction of the 31 physics-informed extras. See module docstring."""
    feats = extract_baseline_features(global_view, local_view)
    g, l = np.asarray(global_view, dtype=float).copy(), np.asarray(local_view, dtype=float).copy()
    n_g, n_l = len(g), len(l)
    l_depth, g_depth = feats["l_depth"], feats["g_depth"]
    l_baseline = np.nanmedian(l)

    # --- local shape: width @ 50%/10% of depth, box-vs-V ratio ---
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

    # --- centroid offset / asymmetry of the dip within the local window ---
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

    # --- ingress/egress slope steepness around the deepest bin ---
    l_min_idx = int(np.nanargmin(l)) if np.isfinite(np.nanmin(l)) else n_l // 2
    k = max(2, n_l // 50)
    lo_idx, hi_idx = max(l_min_idx - k, 0), min(l_min_idx + k, n_l - 1)
    l_slope_dn = float((l[l_min_idx] - l[lo_idx]) / max(l_min_idx - lo_idx, 1)) if lo_idx < l_min_idx else 0.0
    l_slope_up = float((l[hi_idx] - l[l_min_idx]) / max(hi_idx - l_min_idx, 1)) if hi_idx > l_min_idx else 0.0

    # --- integrated dip area, and depth-normalized area (~ effective width) ---
    l_area = float(np.nansum(np.clip(l_baseline - l, 0, None)) / n_l)
    l_depth_area = float(l_area / l_depth) if l_depth > 0 else 0.0

    # --- global: out-of-transit noise, secondary eclipse search, SNR ---
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
    """dict -> 1D np.array in the exact column order a model expects. NaN/inf -> 0.0 (flagged)."""
    vec = np.array([feats.get(k, 0.0) for k in feature_list], dtype=float)
    bad = ~np.isfinite(vec)
    if bad.any():
        vec[bad] = 0.0
    return vec, bad.any()

"""
Stage 4 : CLASSIFICATION
===========================
Only runs for candidates that passed Stage-1 triage (`keep=True`).
Everything else was already resolved to 'UNKNOWN' for free.

RUN THE VERIFICATION CELL BELOW FIRST, before processing 19,992 files,
to confirm the xgb_view feature-count assumption documented in
00_PIPELINE_PLAN.md (I could not load xgboost in this sandbox to check
it myself — no internet to install it here).
"""

import numpy as np
import joblib

LABEL2INT = {"Planet": 0, "EB": 1, "FP": 2}
INT2LABEL = {v: k for k, v in LABEL2INT.items()}

CONF_THRESHOLD = None  # e.g. 0.4 to also emit 'UNKNOWN' below this max-prob; None = always commit to a label


# ---------------------------------------------------------------- #
# VERIFICATION CELL — run this once in your Colab env before Stage 4
# ---------------------------------------------------------------- #
def verify_model_inputs(rf_path="rf_base.joblib", xgb_phys_path="xgb_phys.joblib", xgb_view_path="xgb_view.joblib"):
    rf = joblib.load(rf_path)
    xgb_phys = joblib.load(xgb_phys_path)
    xgb_view = joblib.load(xgb_view_path)
    print("rf_base       n_features_in_ =", getattr(rf, "n_features_in_", "?"), "(expect 13)")
    print("xgb_phys      n_features_in_ =", getattr(xgb_phys, "n_features_in_", "?"), "(expect 44)")
    print("xgb_view      n_features_in_ =", getattr(xgb_view, "n_features_in_", "?"),
          "(expect 768 = 512 global + 256 local, if the flattened-view assumption is right)")
    return rf, xgb_phys, xgb_view


class Classifier:
    def __init__(self, rf_path="rf_base.joblib", xgb_phys_path="xgb_phys.joblib", xgb_view_path="xgb_view.joblib"):
        self.rf = joblib.load(rf_path)
        self.xgb_phys = joblib.load(xgb_phys_path)
        self.xgb_view = joblib.load(xgb_view_path)

    def predict_proba_ensemble(self, phys_vec, view_vec):
        """
        Averages xgb_phys and xgb_view probabilities — matches metrics.json's
        'ensemble_phys_view_acc' (0.7859, the best of the four reported numbers).
        rf_base (13-feat baseline, 0.7373 acc) is loaded for reference/ablation
        but not included in the default ensemble since it underperforms both.
        """
        p_phys = self.xgb_phys.predict_proba(phys_vec.reshape(1, -1))[0]
        p_view = self.xgb_view.predict_proba(view_vec.reshape(1, -1))[0]
        return (p_phys + p_view) / 2.0

    def classify_one(self, phys_vec, view_vec, oe_flag=False, centroid_flag=False):
        """
        Returns (final_class: str, proba: dict, overridden: str|None)

        Two physics-informed overrides run AFTER the ML vote, since neither
        model saw centroid data at train time and the odd-even flag is a
        much stronger, cleaner EB signal than what's implicit in the shape
        features alone:

          - oe_flag=True (from Stage 1's odd_even_test)  -> force EB
          - centroid_flag=True (from a centroid-vs-phase test you run on
            MOM_CENTR1/2, see note below) and prediction=='Planet' -> force FP
        """
        proba = self.predict_proba_ensemble(phys_vec, view_vec)
        pred_int = int(np.argmax(proba))
        final_class = INT2LABEL[pred_int]
        overridden = None

        if oe_flag and final_class != "EB":
            overridden = f"{final_class}->EB (odd-even)"
            final_class = "EB"
        elif centroid_flag and final_class == "Planet":
            overridden = "Planet->FP (centroid offset)"
            final_class = "FP"

        if CONF_THRESHOLD is not None and float(np.max(proba)) < CONF_THRESHOLD and overridden is None:
            overridden = f"{final_class}->UNKNOWN (low confidence)"
            final_class = "UNKNOWN"

        proba_dict = {INT2LABEL[i]: float(p) for i, p in enumerate(proba)}
        return final_class, proba_dict, overridden


def centroid_shift_flag(time, mom_centr1, mom_centr2, period, epoch, duration_hr, sigma_thresh=4.0):
    """
    Optional but recommended: a real centroid-vs-phase test using columns
    already present in the raw target CSVs (MOM_CENTR1/2) but NOT used
    anywhere upstream yet. A transit signal that is actually on a nearby
    blended star shows a centroid that shifts in phase with the dip;
    a real transit on the target star does not.

    This is a coarse version (compare in-transit vs out-of-transit
    centroid mean, in quadrature) — good enough to flag likely blends
    for the FP override above. Swap for a proper difference-image
    centroid test if you have time before the deadline.
    """
    time = np.asarray(time, dtype=float)
    c1, c2 = np.asarray(mom_centr1, dtype=float), np.asarray(mom_centr2, dtype=float)
    duration_days = duration_hr / 24.0
    phase = ((time - epoch) / period + 0.5) % 1.0 - 0.5
    in_tr = np.abs(phase) < (duration_days / (2.0 * period))
    out_tr = ~in_tr

    valid = np.isfinite(c1) & np.isfinite(c2)
    in_tr, out_tr = in_tr & valid, out_tr & valid
    if in_tr.sum() < 5 or out_tr.sum() < 20:
        return False

    d1 = np.nanmean(c1[in_tr]) - np.nanmean(c1[out_tr])
    d2 = np.nanmean(c2[in_tr]) - np.nanmean(c2[out_tr])
    err1 = np.nanstd(c1[out_tr]) / np.sqrt(in_tr.sum())
    err2 = np.nanstd(c2[out_tr]) / np.sqrt(in_tr.sum())
    shift_sigma = np.sqrt((d1 / err1) ** 2 + (d2 / err2) ** 2) if err1 > 0 and err2 > 0 else 0.0
    return bool(shift_sigma > sigma_thresh)

"""
Stage 5 : GEOMETRIC PARAMETERS (Eval-2 lower-weightage columns)
==================================================================
Rp_Rstar, a_Rstar, Inclination_deg, Impact_Parameter (+ sigmas).

Only worth running for rows where Final_Class == 'Planet' (Eval-2 is
scored "for >85% efficient planet detections" per the mentor's sheet)
— running it on EB/FP/UNKNOWN rows just spends compute on numbers
nobody will check. Call `derive_geometry` per Planet-classified
sample_id.

Method: standard circular-orbit transit geometry (Kepler's third law +
Winn 2010-style duration relation), not a fitted transit model. This
is the cheap, defensible choice for ~all Planet candidates; if time
allows, refit the highest-confidence candidates with `batman`
(least-squares on the folded local view) for tighter, more accurate
values — this analytic version is what makes that optional rather than
required for every row.

Uncertainties come from a lightweight Monte Carlo: sample each input
(period, depth, duration, stellar mass, stellar radius) from its own
Gaussian, propagate through the same formulas, take std of the outputs.
Simpler to get right than hand-derived partial derivatives for a
composite formula like this, and cheap enough at ~500 draws x a few
thousand Planet rows.
"""

import numpy as np

AU_IN_RSUN = 215.032
N_MC = 500
RNG = np.random.default_rng(42)

# Fallback stellar params when the catalog is missing them for a target
# (Teff ~4%, Radius ~5% missing; Mass/logg ~21% missing per DATA_ANALYSIS.md).
# Solar defaults are the least-bad assumption for a mixed dwarf-dominated sample.
DEFAULT_MASS_MSUN = 1.0
DEFAULT_RADIUS_RSUN = 1.0


def _draw_positive_gaussian(mean, sigma, n, floor=1e-6):
    sigma = sigma if (sigma and sigma > 0) else abs(mean) * 0.05 + floor
    draws = RNG.normal(mean, sigma, n)
    return np.clip(draws, floor, None)


def derive_geometry(period_days, period_sigma, depth_ppm, depth_ppm_sigma,
                     duration_hr, duration_hr_sigma,
                     mass_msun=None, mass_sigma=None,
                     radius_rsun=None, radius_sigma=None,
                     n_mc=N_MC):
    """
    Returns dict with Rp_Rstar, Rp_Rstar_sigma, a_Rstar, a_Rstar_sigma,
    Inclination_deg, Inclination_deg_sigma, Impact_Parameter,
    Impact_Parameter_sigma, and a `geometry_flag` ('' / 'stellar_params_imputed'
    / 'geometry_inconsistent').
    """
    flag = ""
    if mass_msun is None or not np.isfinite(mass_msun):
        mass_msun, mass_sigma = DEFAULT_MASS_MSUN, DEFAULT_MASS_MSUN * 0.15
        flag = "stellar_params_imputed"
    if radius_rsun is None or not np.isfinite(radius_rsun):
        radius_rsun, radius_sigma = DEFAULT_RADIUS_RSUN, DEFAULT_RADIUS_RSUN * 0.15
        flag = "stellar_params_imputed"

    periods = _draw_positive_gaussian(period_days, period_sigma, n_mc)
    depths_frac = _draw_positive_gaussian(depth_ppm / 1e6, (depth_ppm_sigma or 0) / 1e6, n_mc)
    durations_days = _draw_positive_gaussian(duration_hr / 24.0, (duration_hr_sigma or 0) / 24.0, n_mc)
    masses = _draw_positive_gaussian(mass_msun, mass_sigma, n_mc)
    radii = _draw_positive_gaussian(radius_rsun, radius_sigma, n_mc)

    rp_rstar = np.sqrt(depths_frac)

    period_yr = periods / 365.25
    a_au = (masses * period_yr ** 2) ** (1.0 / 3.0)
    a_rstar = (a_au * AU_IN_RSUN) / radii

    term = (durations_days * np.pi / periods) * a_rstar
    b_sq = (1 + rp_rstar) ** 2 - term ** 2
    valid = b_sq >= 0
    if valid.sum() < 0.2 * n_mc:
        # geometry mostly inconsistent (grazing/impossible for most draws) - still
        # report the central-value estimate but flag it as unreliable
        flag = (flag + "+" if flag else "") + "geometry_inconsistent"

    b = np.full(n_mc, np.nan)
    b[valid] = np.sqrt(b_sq[valid])
    cos_i = np.clip(b[valid] / a_rstar[valid], -1, 1)
    incl_deg = np.degrees(np.arccos(cos_i))

    def summarize(x):
        x = x[np.isfinite(x)]
        if len(x) == 0:
            return np.nan, np.nan
        return float(np.mean(x)), float(np.std(x))

    rp_rstar_mean, rp_rstar_sig = summarize(rp_rstar)
    a_rstar_mean, a_rstar_sig = summarize(a_rstar)
    b_mean, b_sig = summarize(b)
    incl_mean, incl_sig = summarize(incl_deg)

    return dict(
        Rp_Rstar=rp_rstar_mean, Rp_Rstar_sigma=rp_rstar_sig,
        a_Rstar=a_rstar_mean, a_Rstar_sigma=a_rstar_sig,
        Inclination_deg=incl_mean, Inclination_deg_sigma=incl_sig,
        Impact_Parameter=b_mean, Impact_Parameter_sigma=b_sig,
        geometry_flag=flag,
    )

# ==================== CELL : ASSEMBLE FINAL SUBMISSION ====================
"""
Stage 6 : ASSEMBLY
=====================
Wires stages 1-5 together over every batch, and — this is the part your
current per-batch loops don't do — guarantees every one of the ~19,992
sample_ids ends up in the output, including the ones detrending/BLS
skipped. Those are legitimate UNKNOWNs, not files you get to omit; the
mentor's deliverable spec is explicit that all ~20k rows must be present.

Writes:
  evaluation1_classification.csv  -> sample_id, Final_Class
  evaluation2_parameters.csv      -> sample_id, Final_Class, + all params

Run this AFTER you've run the verification cell in 04_classify.py.
"""

import os
import glob
import warnings
import numpy as np
import pandas as pd
from tqdm import tqdm

warnings.filterwarnings("ignore")

# these must be importable (same folder as this script, or on sys.path) —
# importlib.import_module tolerates the leading-digit filenames fine, even
# though you couldn't write `import 01_triage_filter` literally.
from importlib import import_module
triage_mod = import_module("01_triage_filter")
views_mod = import_module("02_view_construction")
feats_mod = import_module("03_feature_extraction")
clf_mod = import_module("04_classify")
geom_mod = import_module("05_geometric_params")

# ---- PATH CONFIG (match your existing Drive layout) -----------------------
RAW_ROOT = "/content/drive/MyDrive/PRL/raw/target_batches"
PROCESSED_ROOT = "/content/drive/MyDrive/PRL/processed"
BLS_ROOT = "/content/drive/MyDrive/PRL/bls_results"
CATALOG_CSV = "/content/drive/MyDrive/PRL/targetdataset_catalog_Set-1.csv"
OUT_DIR = "/content/drive/MyDrive/PRL/submission"
os.makedirs(OUT_DIR, exist_ok=True)

MODEL_DIR = "/content/drive/MyDrive/PRL/models"  # wherever rf_base/xgb_phys/xgb_view.joblib live


def load_all_bls_rows():
    """Concat every batch's *_bls_summary.csv into one dict keyed by sample_id."""
    rows = {}
    for f in glob.glob(os.path.join(BLS_ROOT, "*", "*_bls_summary.csv")):
        df = pd.read_csv(f)
        for _, r in df.iterrows():
            rows[r["sample_id"]] = r.to_dict()
    return rows


def find_processed_path(sample_id):
    hits = glob.glob(os.path.join(PROCESSED_ROOT, "*", sample_id))
    return hits[0] if hits else None


def find_raw_path(sample_id):
    hits = glob.glob(os.path.join(RAW_ROOT, "*", sample_id))
    return hits[0] if hits else None


def main():
    # 1. canonical list of ALL sample_ids expected in the deliverable
    catalog = pd.read_csv(CATALOG_CSV)
    id_col = "sample_id" if "sample_id" in catalog.columns else catalog.columns[0]
    all_sample_ids = sorted(catalog[id_col].astype(str).tolist())
    catalog = catalog.set_index(id_col)

    bls_rows = load_all_bls_rows()
    classifier = clf_mod.Classifier(
        rf_path=os.path.join(MODEL_DIR, "rf_base.joblib"),
        xgb_phys_path=os.path.join(MODEL_DIR, "xgb_phys.joblib"),
        xgb_view_path=os.path.join(MODEL_DIR, "xgb_view.joblib"),
    )

    results = []
    n_unknown_upstream = n_unknown_triage = n_classified = 0

    for sample_id in tqdm(all_sample_ids, desc="Assembling submission"):
        row = dict(sample_id=sample_id, Final_Class="UNKNOWN",
                   Period=np.nan, Period_sigma=np.nan, Epoch=np.nan, Epoch_sigma=np.nan,
                   Depth_ppm=np.nan, Depth_ppm_sigma=np.nan, Duration_hr=np.nan, Duration_hr_sigma=np.nan,
                   Rp_Rstar=np.nan, Rp_Rstar_sigma=np.nan, a_Rstar=np.nan, a_Rstar_sigma=np.nan,
                   Inclination_deg=np.nan, Inclination_deg_sigma=np.nan,
                   Impact_Parameter=np.nan, Impact_Parameter_sigma=np.nan,
                   qc_reason="", qc_override="")

        bls_row = bls_rows.get(sample_id)
        proc_path = find_processed_path(sample_id)
        time_arr = flux_arr = None
        if proc_path is not None:
            try:
                lc = pd.read_csv(proc_path)
                time_arr, flux_arr = lc["TIME"].values, lc["FLUX"].values
            except Exception:
                pass

        triage = triage_mod.triage_one(sample_id, bls_row, time=time_arr, flux=flux_arr)

        if not triage["keep"]:
            row["qc_reason"] = triage["reason"] or "upstream_failed"
            n_unknown_upstream += 1
            results.append(row)
            continue

        # carry the higher-weightage BLS params through regardless of downstream classification
        for k in ["Period", "Period_sigma", "Epoch", "Epoch_sigma",
                  "Depth_ppm", "Depth_ppm_sigma", "Duration_hr", "Duration_hr_sigma"]:
            row[k] = bls_row.get(k, np.nan)

        # Stage 2+3: views -> features
        g_view, l_view = views_mod.build_views(time_arr, flux_arr, bls_row["Period"], bls_row["Epoch"], bls_row["Duration_hr"])
        feats = feats_mod.extract_physics_features(g_view, l_view)
        phys_vec, _ = feats_mod.to_ordered_vector(feats, feats_mod.FEATURES_PHYSICS)
        view_vec = np.concatenate([np.nan_to_num(g_view, nan=0.0), np.nan_to_num(l_view, nan=0.0)])

        # optional centroid check (needs the RAW csv, not the processed one, for MOM_CENTR1/2)
        centroid_flag = False
        raw_path = find_raw_path(sample_id)
        if raw_path is not None:
            try:
                raw = pd.read_csv(raw_path)
                raw = raw[raw["QUALITY"] == 0]
                centroid_flag = clf_mod.centroid_shift_flag(
                    raw["TIME"].values, raw["MOM_CENTR1"].values, raw["MOM_CENTR2"].values,
                    bls_row["Period"], bls_row["Epoch"], bls_row["Duration_hr"],
                )
            except Exception:
                pass

        final_class, proba, overridden = classifier.classify_one(
            phys_vec, view_vec, oe_flag=triage["oe_flag"], centroid_flag=centroid_flag
        )
        row["Final_Class"] = final_class.upper() if final_class != "UNKNOWN" else "UNKNOWN"
        row["qc_override"] = overridden or ""
        n_classified += 1

        # Stage 5: geometry, Planet rows only
        if final_class == "Planet":
            cat_row = catalog.loc[sample_id] if sample_id in catalog.index else {}
            geom = geom_mod.derive_geometry(
                period_days=row["Period"], period_sigma=row["Period_sigma"],
                depth_ppm=row["Depth_ppm"], depth_ppm_sigma=row["Depth_ppm_sigma"],
                duration_hr=row["Duration_hr"], duration_hr_sigma=row["Duration_hr_sigma"],
                mass_msun=cat_row.get("Mass") if hasattr(cat_row, "get") else None,
                mass_sigma=cat_row.get("Mass_err") if hasattr(cat_row, "get") else None,
                radius_rsun=cat_row.get("Radius") if hasattr(cat_row, "get") else None,
                radius_sigma=cat_row.get("Radius_err") if hasattr(cat_row, "get") else None,
            )
            for k in ["Rp_Rstar", "Rp_Rstar_sigma", "a_Rstar", "a_Rstar_sigma",
                      "Inclination_deg", "Inclination_deg_sigma",
                      "Impact_Parameter", "Impact_Parameter_sigma"]:
                row[k] = geom[k]
            if geom["geometry_flag"]:
                row["qc_reason"] = (row["qc_reason"] + "+" if row["qc_reason"] else "") + geom["geometry_flag"]

        results.append(row)

    df = pd.DataFrame(results).sort_values("sample_id", ascending=True).reset_index(drop=True)

    # per-mentor naming convention: PLANET / EB / FP / UNKNOWN (uppercase)
    df["Final_Class"] = df["Final_Class"].replace({"Planet": "PLANET"})

    eval1_cols = ["sample_id", "Final_Class"]
    eval2_cols = ["sample_id", "Final_Class",
                  "Period", "Period_sigma", "Epoch", "Epoch_sigma",
                  "Depth_ppm", "Depth_ppm_sigma", "Duration_hr", "Duration_hr_sigma",
                  "Rp_Rstar", "Rp_Rstar_sigma", "a_Rstar", "a_Rstar_sigma",
                  "Inclination_deg", "Inclination_deg_sigma",
                  "Impact_Parameter", "Impact_Parameter_sigma"]

    df[eval1_cols].to_csv(os.path.join(OUT_DIR, "evaluation1_classification.csv"), index=False)
    df[eval2_cols].to_csv(os.path.join(OUT_DIR, "evaluation2_parameters.csv"), index=False)
    df.to_csv(os.path.join(OUT_DIR, "internal_full_with_qc.csv"), index=False)  # keep qc_reason/qc_override for your own debugging

    print("=" * 60)
    print(f"Total sample_ids       : {len(df)}")
    print(f"UNKNOWN (upstream/triage): {n_unknown_upstream}")
    print(f"Classified by model     : {n_classified}")
    print(f"Class counts:\n{df['Final_Class'].value_counts()}")
    print("=" * 60)


if __name__ == "__main__":
    main()