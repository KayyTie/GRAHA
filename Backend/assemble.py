"""
assemble.py - Full Pipeline Assembly (Stages 1-6)
Writes submission/evaluation1_classification.csv and submission/evaluation2_parameters.csv
Usage: prl_env/Scripts/python.exe assemble.py
"""

import os, glob, warnings
import numpy as np
import pandas as pd
import joblib
from scipy import stats
from tqdm import tqdm

warnings.filterwarnings("ignore")

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
PROCESSED_ROOT = os.path.join(BASE_DIR, "Processed")
RAW_ROOT       = os.path.join(BASE_DIR, "Sources")
BLS_CSV        = os.path.join(BASE_DIR, "BLS_result", "blsresult.csv")
MODEL_DIR      = os.path.join(BASE_DIR, "models")
OUT_DIR        = os.path.join(BASE_DIR, "submission")
os.makedirs(OUT_DIR, exist_ok=True)

# ============================================================
# STAGE 1: TRIAGE
# ============================================================
SDE_MIN           = 7.0
SNR_MIN           = 3.0
MAX_DURATION_FRAC = 0.30
BASELINE_DAYS     = 25.95
MONO_PERIOD_FRAC  = 0.40
ODD_EVEN_SIGMA    = 3.0


def triage_bls_row(bls_row):
    if bls_row is None:
        return dict(keep=False, reason="upstream_failed", n_transits=0.0, mono_flag=False)
    period      = bls_row.get("Period")
    sde         = bls_row.get("sde")
    depth_ppm   = bls_row.get("Depth_ppm")
    depth_sigma = bls_row.get("Depth_ppm_sigma")
    duration_hr = bls_row.get("Duration_hr")
    if any(v is None or not np.isfinite(v) for v in [period, sde, depth_ppm, duration_hr]):
        return dict(keep=False, reason="upstream_failed", n_transits=0.0, mono_flag=False)
    if sde < SDE_MIN:
        return dict(keep=False, reason="low_sde", n_transits=0.0, mono_flag=False)
    # SNR and duration_ratio filters removed — let the classifier decide
    n_transits = BASELINE_DAYS / period
    mono_flag  = period > (MONO_PERIOD_FRAC * BASELINE_DAYS)
    return dict(keep=True, reason=None, n_transits=n_transits, mono_flag=mono_flag)


def odd_even_test(time, flux, period, epoch, duration_hr):
    time  = np.asarray(time, dtype=float)
    flux  = np.asarray(flux, dtype=float)
    half_win  = max(duration_hr / 24.0 * 0.5, 1e-4)
    epoch_idx = np.round((time - epoch) / period).astype(int)
    phase     = (time - epoch) - epoch_idx * period
    in_tr     = np.abs(phase) < half_win
    odd_mask  = in_tr & (epoch_idx % 2 != 0)
    even_mask = in_tr & (epoch_idx % 2 == 0)
    if odd_mask.sum() < 5 or even_mask.sum() < 5:
        return dict(oe_flag=False, oe_sigma=0.0)
    d_odd  = -np.nanmedian(flux[odd_mask])
    d_even = -np.nanmedian(flux[even_mask])
    e_odd  = np.nanstd(flux[odd_mask])  / np.sqrt(odd_mask.sum())
    e_even = np.nanstd(flux[even_mask]) / np.sqrt(even_mask.sum())
    combined = np.sqrt(e_odd**2 + e_even**2) or 1e-9
    oe_sigma = abs(d_odd - d_even) / combined
    return dict(oe_flag=bool(oe_sigma > ODD_EVEN_SIGMA), oe_sigma=float(oe_sigma))


def triage_one(sample_id, bls_row, time=None, flux=None):
    base = triage_bls_row(bls_row)
    base["sample_id"] = sample_id
    base["oe_flag"]   = False
    base["oe_sigma"]  = 0.0
    if base["keep"] and time is not None and flux is not None:
        oe = odd_even_test(time, flux, bls_row["Period"], bls_row["Epoch"], bls_row["Duration_hr"])
        base["oe_flag"]  = oe["oe_flag"]
        base["oe_sigma"] = oe["oe_sigma"]
    return base


# ============================================================
# STAGE 2: VIEW CONSTRUCTION
# ============================================================
GLOBAL_BINS = 512
LOCAL_BINS  = 256
LOCAL_WIN_DUR = 4.0


def _phase_fold(time, period, epoch):
    return ((time - epoch) / period + 0.5) % 1.0 - 0.5


def _bin_phase(phase, flux, n_bins, lo, hi):
    edges   = np.linspace(lo, hi, n_bins + 1)
    bin_idx = np.digitize(phase, edges) - 1
    out     = np.full(n_bins, np.nan, dtype=np.float64)
    for b in range(n_bins):
        sel = bin_idx == b
        if sel.any():
            out[b] = np.nanmedian(flux[sel])
    return out


def build_views(time, flux, period, epoch, duration_hr):
    time  = np.asarray(time, dtype=float)
    flux  = np.asarray(flux, dtype=float)
    # Normalize flux to mean-0 (fractional deviation from baseline).
    # Processed lightcurves are Wotan-flattened around 1.0; models were
    # trained on flux - 1 convention (transit dip is a small negative value).
    flux  = flux - np.nanmedian(flux)
    phase = _phase_fold(time, period, epoch)
    g     = _bin_phase(phase, flux, GLOBAL_BINS, -0.5, 0.5)
    dur_d = duration_hr / 24.0
    hw    = min((LOCAL_WIN_DUR * dur_d) / (2.0 * period), 0.5)
    l     = _bin_phase(phase, flux, LOCAL_BINS, -hw, hw)
    return g, l


# ============================================================
# STAGE 3: FEATURE EXTRACTION (46 features)
# ============================================================
FEATURES_PHYSICS = [
    "g_min","g_max","g_std","g_mean","g_depth",
    "l_min","l_max","l_std","l_depth",
    "g_nan","l_nan","g_ptp","l_ptp",
    "l_width50","l_width10","l_w_ratio","l_bottom_std","l_com_offset",
    "l_asym","l_slope_dn","l_slope_up","l_area","l_depth_area",
    "g_oot_std","g_sec_depth","g_sec_ratio","snr_proxy","g_n_sig_bins",
    "g_iqr","g_skew","l_skew","g_kurt","l_kurt","g_ac1","l_ac1",
    "l_over_g_depth","g_p5","g_p25","g_p50","g_p75","g_p95",
    "l_p5","l_p25","l_p50","l_p75","l_p95",
]


def _ac1(x):
    x = x[~np.isnan(x)]
    if len(x) < 3:
        return 0.0
    x0  = x[:-1] - np.mean(x)
    x1  = x[1:]  - np.mean(x)
    den = np.sqrt(np.sum(x0**2) * np.sum(x1**2))
    return float(np.sum(x0 * x1) / den) if den > 0 else 0.0


def extract_physics_features(gv, lv):
    g, l   = np.asarray(gv, dtype=float), np.asarray(lv, dtype=float)
    n_g, n_l = len(g), len(l)
    g_depth = float(-np.nanmin(g))
    l_depth = float(-np.nanmin(l))
    l_base  = float(np.nanmedian(l))

    feats = {
        "g_min":  float(np.nanmin(g)),  "g_max": float(np.nanmax(g)),
        "g_std":  float(np.nanstd(g)),  "g_mean":float(np.nanmean(g)),
        "g_depth": g_depth,
        "l_min":  float(np.nanmin(l)),  "l_max": float(np.nanmax(l)),
        "l_std":  float(np.nanstd(l)),  "l_depth": l_depth,
        "g_nan":  int(np.isnan(g).sum()),"l_nan": int(np.isnan(l).sum()),
        "g_ptp":  float(np.nanmax(g)-np.nanmin(g)),
        "l_ptp":  float(np.nanmax(l)-np.nanmin(l)),
    }

    def w(frac):
        return int(((l < l_base - frac*l_depth) & ~np.isnan(l)).sum())

    l_w50 = w(0.5); l_w10 = w(0.1)
    l_w_r = l_w50 / l_w10 if l_w10 > 0 else 0.0
    bm    = (l < l_base - 0.5*l_depth) & ~np.isnan(l)
    l_bst = float(np.nanstd(l[bm])) if bm.sum() >= 2 else 0.0

    wts = np.nan_to_num(np.clip(l_base - l, 0, None), nan=0.0)
    bi  = np.arange(n_l); cen = (n_l-1)/2.0
    com = float(np.sum(bi*wts)/np.sum(wts)) if wts.sum()>0 else cen
    l_com = (com - cen) / n_l
    lft = wts[:n_l//2].sum(); rgt = wts[n_l//2:].sum()
    l_asym = (lft-rgt)/(lft+rgt) if (lft+rgt)>0 else 0.0

    lmi = int(np.nanargmin(l)) if np.isfinite(np.nanmin(l)) else n_l//2
    k   = max(2, n_l//50)
    li  = max(lmi-k, 0); hi2 = min(lmi+k, n_l-1)
    lsd = float((l[lmi]-l[li])/max(lmi-li,1)) if li<lmi else 0.0
    lsu = float((l[hi2]-l[lmi])/max(hi2-lmi,1)) if hi2>lmi else 0.0

    l_area = float(np.nansum(np.clip(l_base-l, 0, None))/n_l)
    l_da   = float(l_area/l_depth) if l_depth>0 else 0.0

    gc = (n_g-1)/2.0
    oot = np.ones(n_g, dtype=bool)
    oot[int(gc-0.1*n_g):int(gc+0.1*n_g)] = False
    gos  = float(np.nanstd(g[oot]))    if oot.any() else 0.0
    gom  = float(np.nanmedian(g[oot])) if oot.any() else float(np.nanmedian(g))
    gsd  = float(max(gom - np.nanmin(g[oot]), 0.0)) if oot.any() else 0.0
    gsr  = float(gsd/g_depth) if g_depth>0 else 0.0
    snr  = float(g_depth/gos) if gos>0 else 0.0
    gsb  = int((((gom-g) > 3*gos) & (~np.isnan(g))).sum())

    gv2  = g[~np.isnan(g)]; lv2 = l[~np.isnan(l)]
    giqr = float(np.nanpercentile(g,75)-np.nanpercentile(g,25))
    gsk  = float(stats.skew(gv2))     if len(gv2)>2 else 0.0
    lsk  = float(stats.skew(lv2))     if len(lv2)>2 else 0.0
    gku  = float(stats.kurtosis(gv2)) if len(gv2)>2 else 0.0
    lku  = float(stats.kurtosis(lv2)) if len(lv2)>2 else 0.0
    gac  = _ac1(g); lac = _ac1(l)
    log  = float(l_depth/g_depth) if g_depth>0 else 0.0

    gp   = [float(x) for x in np.nanpercentile(g,[5,25,50,75,95])]
    lp   = [float(x) for x in np.nanpercentile(l,[5,25,50,75,95])]

    feats.update({
        "l_width50":l_w50,"l_width10":l_w10,"l_w_ratio":l_w_r,
        "l_bottom_std":l_bst,"l_com_offset":l_com,"l_asym":l_asym,
        "l_slope_dn":lsd,"l_slope_up":lsu,"l_area":l_area,"l_depth_area":l_da,
        "g_oot_std":gos,"g_sec_depth":gsd,"g_sec_ratio":gsr,
        "snr_proxy":snr,"g_n_sig_bins":gsb,
        "g_iqr":giqr,"g_skew":gsk,"l_skew":lsk,"g_kurt":gku,"l_kurt":lku,
        "g_ac1":gac,"l_ac1":lac,"l_over_g_depth":log,
        "g_p5":gp[0],"g_p25":gp[1],"g_p50":gp[2],"g_p75":gp[3],"g_p95":gp[4],
        "l_p5":lp[0],"l_p25":lp[1],"l_p50":lp[2],"l_p75":lp[3],"l_p95":lp[4],
    })
    return feats


def to_vec(feats, feature_list):
    v = np.array([feats.get(k, 0.0) for k in feature_list], dtype=float)
    v[~np.isfinite(v)] = 0.0
    return v


# ============================================================
# STAGE 4: CLASSIFICATION
# ============================================================
INT2LABEL = {0: "PLANET", 1: "EB", 2: "FP"}
CONF_THRESHOLD = None


class Classifier:
    def __init__(self, rf_path, xgb_phys_path, xgb_view_path):
        self.rf       = joblib.load(rf_path)
        self.xgb_phys = joblib.load(xgb_phys_path)
        self.xgb_view = joblib.load(xgb_view_path)

    def ensemble_proba(self, phys_vec, view_vec):
        p1 = self.xgb_phys.predict_proba(phys_vec.reshape(1, -1))[0]
        p2 = self.xgb_view.predict_proba(view_vec.reshape(1, -1))[0]
        return (p1 + p2) / 2.0

    def classify_one(self, phys_vec, view_vec, oe_flag=False, centroid_flag=False):
        proba = self.ensemble_proba(phys_vec, view_vec)
        fc    = INT2LABEL[int(np.argmax(proba))]
        ov    = None
        if oe_flag and fc != "EB":
            ov = f"{fc}->EB (odd-even)"; fc = "EB"
        elif centroid_flag and fc == "PLANET":
            ov = "PLANET->FP (centroid offset)"; fc = "FP"
        if CONF_THRESHOLD and float(np.max(proba)) < CONF_THRESHOLD and ov is None:
            ov = f"{fc}->UNKNOWN (low conf)"; fc = "UNKNOWN"
        pd_dict = {INT2LABEL[i]: float(p) for i, p in enumerate(proba)}
        return fc, pd_dict, ov


def centroid_flag_check(time, c1, c2, period, epoch, duration_hr, thresh=4.0):
    phase = ((np.asarray(time,float) - epoch)/period + 0.5) % 1.0 - 0.5
    dur   = duration_hr / 24.0
    in_tr = np.abs(phase) < dur/(2.0*period)
    out_tr= ~in_tr
    ok    = np.isfinite(c1) & np.isfinite(c2)
    it    = in_tr & ok; ot = out_tr & ok
    if it.sum() < 5 or ot.sum() < 20:
        return False
    d1 = np.nanmean(c1[it])-np.nanmean(c1[ot]); d2 = np.nanmean(c2[it])-np.nanmean(c2[ot])
    e1 = np.nanstd(c1[ot])/np.sqrt(it.sum());   e2 = np.nanstd(c2[ot])/np.sqrt(it.sum())
    sig = np.sqrt((d1/e1)**2+(d2/e2)**2) if e1>0 and e2>0 else 0.0
    return bool(sig > thresh)


# ============================================================
# STAGE 5: GEOMETRY
# ============================================================
AU_RSUN = 215.032
N_MC    = 500
RNG2    = np.random.default_rng(42)
DEF_M   = 1.0; DEF_R = 1.0


def _pg(mean, sig, n):
    sig = sig if sig and sig > 0 else abs(mean)*0.05 + 1e-6
    return np.clip(RNG2.normal(mean, sig, n), 1e-6, None)


def derive_geometry(period, period_sig, depth_ppm, depth_sig, dur_hr, dur_sig):
    periods = _pg(period, period_sig or 0, N_MC)
    depths  = _pg(depth_ppm/1e6, (depth_sig or 0)/1e6, N_MC)
    durs    = _pg(dur_hr/24.0, (dur_sig or 0)/24.0, N_MC)
    masses  = _pg(DEF_M, DEF_M*0.15, N_MC)
    radii   = _pg(DEF_R, DEF_R*0.15, N_MC)

    rp    = np.sqrt(depths)
    a_au  = (masses * (periods/365.25)**2) ** (1.0/3.0)
    a_rs  = (a_au * AU_RSUN) / radii
    term  = (durs * np.pi / periods) * a_rs
    b_sq  = (1 + rp)**2 - term**2
    valid = b_sq >= 0
    flag  = "stellar_params_imputed"
    if valid.sum() < 0.2*N_MC:
        flag += "+geometry_inconsistent"

    b     = np.full(N_MC, np.nan)
    b[valid] = np.sqrt(b_sq[valid])
    cos_i = np.clip(b[valid]/a_rs[valid], -1, 1)
    incl  = np.degrees(np.arccos(cos_i))

    def sm(x):
        x = x[np.isfinite(x)]
        return (float(np.mean(x)), float(np.std(x))) if len(x) else (np.nan, np.nan)

    rp_m, rp_s   = sm(rp)
    ar_m, ar_s   = sm(a_rs)
    b_m,  b_s    = sm(b)
    i_m,  i_s    = sm(incl)
    return dict(Rp_Rstar=rp_m, Rp_Rstar_sigma=rp_s,
                a_Rstar=ar_m,  a_Rstar_sigma=ar_s,
                Inclination_deg=i_m, Inclination_deg_sigma=i_s,
                Impact_Parameter=b_m, Impact_Parameter_sigma=b_s,
                geometry_flag=flag)


# ============================================================
# STAGE 6: ASSEMBLY
# ============================================================
def idx_files(root):
    d = {}
    for p in glob.glob(os.path.join(root, "**", "*.csv"), recursive=True):
        d[os.path.basename(p)] = p
    return d


def main():
    print("Loading BLS results...")
    bls_df   = pd.read_csv(BLS_CSV)
    bls_rows = {r["sample_id"]: r.to_dict() for _, r in bls_df.iterrows()}
    all_ids  = sorted(bls_df["sample_id"].astype(str).tolist())
    print(f"  {len(all_ids)} sample_ids")

    print("Indexing Processed/ ...")
    proc_idx = idx_files(PROCESSED_ROOT)
    print(f"  {len(proc_idx)} files")

    print("Indexing Sources/ ...")
    raw_idx  = idx_files(RAW_ROOT)
    print(f"  {len(raw_idx)} files")

    print("Loading models...")
    clf = Classifier(
        os.path.join(MODEL_DIR, "rf_base.joblib"),
        os.path.join(MODEL_DIR, "xgb_phys.joblib"),
        os.path.join(MODEL_DIR, "xgb_view.joblib"),
    )
    print("  Models loaded OK")

    results = []
    n_unk_up = n_unk_tri = n_ok = 0

    BLANK = dict(
        Final_Class="UNKNOWN",
        Period=np.nan, Period_sigma=np.nan, Epoch=np.nan, Epoch_sigma=np.nan,
        Depth_ppm=np.nan, Depth_ppm_sigma=np.nan,
        Duration_hr=np.nan, Duration_hr_sigma=np.nan,
        Rp_Rstar=np.nan, Rp_Rstar_sigma=np.nan,
        a_Rstar=np.nan, a_Rstar_sigma=np.nan,
        Inclination_deg=np.nan, Inclination_deg_sigma=np.nan,
        Impact_Parameter=np.nan, Impact_Parameter_sigma=np.nan,
        P_Planet=np.nan, P_EB=np.nan, P_FP=np.nan,
        qc_reason="", qc_override="",
    )

    for sid in tqdm(all_ids, desc="Classifying"):
        row = {"sample_id": sid, **BLANK}

        bls_row   = bls_rows.get(sid)
        proc_path = proc_idx.get(sid)

        # load processed lightcurve
        time_arr = flux_arr = None
        if proc_path:
            try:
                lc = pd.read_csv(proc_path)
                time_arr = lc["TIME"].values
                flux_arr = lc["FLUX"].values
            except Exception:
                pass

        # Stage 1: triage
        tri = triage_one(sid, bls_row, time=time_arr, flux=flux_arr)
        if not tri["keep"]:
            row["qc_reason"] = tri.get("reason") or "upstream_failed"
            n_unk_up += 1
            results.append(row)
            continue

        for k in ["Period","Period_sigma","Epoch","Epoch_sigma",
                  "Depth_ppm","Depth_ppm_sigma","Duration_hr","Duration_hr_sigma"]:
            row[k] = bls_row.get(k, np.nan)

        if time_arr is None:
            row["qc_reason"] = "no_processed_lc"
            n_unk_tri += 1
            results.append(row)
            continue

        # Stage 2+3: views + features
        try:
            gv, lv   = build_views(time_arr, flux_arr,
                                   bls_row["Period"], bls_row["Epoch"], bls_row["Duration_hr"])
            feats    = extract_physics_features(gv, lv)
            phys_vec = to_vec(feats, FEATURES_PHYSICS)
            view_vec = np.concatenate([np.nan_to_num(gv, nan=0.0),
                                       np.nan_to_num(lv, nan=0.0)])
        except Exception as e:
            row["qc_reason"] = f"feat_err:{e}"
            n_unk_tri += 1
            results.append(row)
            continue

        # optional centroid check
        cent_flag = False
        raw_path  = raw_idx.get(sid)
        if raw_path:
            try:
                raw = pd.read_csv(raw_path)
                raw = raw[raw["QUALITY"] == 0]
                cent_flag = centroid_flag_check(
                    raw["TIME"].values, raw["MOM_CENTR1"].values, raw["MOM_CENTR2"].values,
                    bls_row["Period"], bls_row["Epoch"], bls_row["Duration_hr"])
            except Exception:
                pass

        # Stage 4: classify
        try:
            fc, proba, ov = clf.classify_one(phys_vec, view_vec,
                                             oe_flag=tri["oe_flag"],
                                             centroid_flag=cent_flag)
        except Exception as e:
            row["qc_reason"] = f"clf_err:{e}"
            n_unk_tri += 1
            results.append(row)
            continue

        row["Final_Class"] = fc
        row["qc_override"] = ov or ""
        row["P_Planet"] = proba.get("PLANET", np.nan)
        row["P_EB"]     = proba.get("EB",     np.nan)
        row["P_FP"]     = proba.get("FP",     np.nan)
        n_ok += 1

        # Stage 5: geometry for planets only
        if fc == "PLANET":
            try:
                g = derive_geometry(row["Period"], row["Period_sigma"],
                                    row["Depth_ppm"], row["Depth_ppm_sigma"],
                                    row["Duration_hr"], row["Duration_hr_sigma"])
                for k in ["Rp_Rstar","Rp_Rstar_sigma","a_Rstar","a_Rstar_sigma",
                          "Inclination_deg","Inclination_deg_sigma",
                          "Impact_Parameter","Impact_Parameter_sigma"]:
                    row[k] = g[k]
                if g["geometry_flag"]:
                    row["qc_reason"] = g["geometry_flag"]
            except Exception as e:
                row["qc_reason"] = f"geom_err:{e}"

        results.append(row)

    df = pd.DataFrame(results).sort_values("sample_id").reset_index(drop=True)

    e1 = ["sample_id","Final_Class"]
    e2 = ["sample_id","Final_Class",
          "Period","Period_sigma","Epoch","Epoch_sigma",
          "Depth_ppm","Depth_ppm_sigma","Duration_hr","Duration_hr_sigma",
          "Rp_Rstar","Rp_Rstar_sigma","a_Rstar","a_Rstar_sigma",
          "Inclination_deg","Inclination_deg_sigma",
          "Impact_Parameter","Impact_Parameter_sigma"]

    df[e1].to_csv(os.path.join(OUT_DIR, "evaluation1_classification.csv"), index=False)
    df[e2].to_csv(os.path.join(OUT_DIR, "evaluation2_parameters.csv"),      index=False)
    df.to_csv(    os.path.join(OUT_DIR, "internal_full_with_qc.csv"),       index=False)

    print("\n" + "="*60)
    print(f"Total              : {len(df)}")
    print(f"UNKNOWN (triage)   : {n_unk_up}")
    print(f"UNKNOWN (no lc/err): {n_unk_tri}")
    print(f"Classified         : {n_ok}")
    print(f"\nClass counts:\n{df['Final_Class'].value_counts().to_string()}")
    print("="*60)
    print(f"\nOutputs in: {OUT_DIR}")


if __name__ == "__main__":
    main()
