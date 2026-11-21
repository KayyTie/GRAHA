import os, sys, glob, warnings, numpy as np, pandas as pd, joblib
from scipy import stats
from tqdm import tqdm
warnings.filterwarnings("ignore")

BASE = os.path.dirname(os.path.abspath(__file__))
PROC = os.path.join(BASE, "Processed")
RAW  = os.path.join(BASE, "Sources")
BLS  = os.path.join(BASE, "BLS_result", "blsresult.csv")
MDIR = os.path.join(BASE, "models")

SDE_MIN = 7.0; SNR_MIN = 3.0; MAX_DUR_FRAC = 0.30
OE_SIGMA = 3.0

def _ac1(x):
    x = x[~np.isnan(x)]
    if len(x) < 3: return 0.0
    x0 = x[:-1] - np.mean(x); x1 = x[1:] - np.mean(x)
    d = np.sqrt(np.sum(x0**2) * np.sum(x1**2))
    return float(np.sum(x0 * x1) / d) if d > 0 else 0.0

FEAT_LIST = [
    "g_min","g_max","g_std","g_mean","g_depth","l_min","l_max","l_std","l_depth",
    "g_nan","l_nan","g_ptp","l_ptp","l_width50","l_width10","l_w_ratio","l_bottom_std",
    "l_com_offset","l_asym","l_slope_dn","l_slope_up","l_area","l_depth_area",
    "g_oot_std","g_sec_depth","g_sec_ratio","snr_proxy","g_n_sig_bins",
    "g_iqr","g_skew","l_skew","g_kurt","l_kurt","g_ac1","l_ac1",
    "l_over_g_depth","g_p5","g_p25","g_p50","g_p75","g_p95",
    "l_p5","l_p25","l_p50","l_p75","l_p95",
]
INT2LABEL = {0: "PLANET", 1: "EB", 2: "FP"}
AU_RSUN = 215.032; NMC = 500; RNG = np.random.default_rng(42)


def phase_fold(t, p, e):
    return ((t - e) / p + 0.5) % 1.0 - 0.5

def bin_phase(ph, fl, nb, lo, hi):
    edges = np.linspace(lo, hi, nb + 1)
    bi = np.digitize(ph, edges) - 1
    out = np.full(nb, np.nan, dtype=np.float64)
    for b in range(nb):
        s = bi == b
        if s.any():
            out[b] = np.nanmedian(fl[s])
    return out

def build_views(t, f, per, epo, dur_hr):
    t = np.asarray(t, float); f = np.asarray(f, float)
    f = f - np.nanmedian(f)
    ph = phase_fold(t, per, epo)
    gv = bin_phase(ph, f, 512, -0.5, 0.5)
    hw = min((4.0 * dur_hr / 24.0) / (2.0 * per), 0.5)
    lv = bin_phase(ph, f, 256, -hw, hw)
    return gv, lv

def extract_feats(g, l):
    ng, nl = len(g), len(l)
    gd = float(-np.nanmin(g)); ld = float(-np.nanmin(l))
    lb = float(np.nanmedian(l))
    f = {
        "g_min": float(np.nanmin(g)), "g_max": float(np.nanmax(g)),
        "g_std": float(np.nanstd(g)), "g_mean": float(np.nanmean(g)), "g_depth": gd,
        "l_min": float(np.nanmin(l)), "l_max": float(np.nanmax(l)),
        "l_std": float(np.nanstd(l)), "l_depth": ld,
        "g_nan": int(np.isnan(g).sum()), "l_nan": int(np.isnan(l).sum()),
        "g_ptp": float(np.nanmax(g) - np.nanmin(g)),
        "l_ptp": float(np.nanmax(l) - np.nanmin(l)),
    }
    def w(fr):
        return int(((l < lb - fr * ld) & ~np.isnan(l)).sum())
    w50 = w(0.5); w10 = w(0.1)
    wr = w50 / w10 if w10 > 0 else 0.0
    bm = (l < lb - 0.5 * ld) & ~np.isnan(l)
    bs = float(np.nanstd(l[bm])) if bm.sum() >= 2 else 0.0
    wts = np.nan_to_num(np.clip(lb - l, 0, None), nan=0.0)
    bi2 = np.arange(nl); cn = (nl - 1) / 2.0
    cm = float(np.sum(bi2 * wts) / np.sum(wts)) if wts.sum() > 0 else cn
    co = (cm - cn) / nl
    lt = wts[:nl // 2].sum(); rt = wts[nl // 2:].sum()
    la2 = (lt - rt) / (lt + rt) if (lt + rt) > 0 else 0.0
    mi = int(np.nanargmin(l)) if np.isfinite(np.nanmin(l)) else nl // 2
    k = max(2, nl // 50); lo2 = max(mi - k, 0); hi2 = min(mi + k, nl - 1)
    sd2 = float((l[mi] - l[lo2]) / max(mi - lo2, 1)) if lo2 < mi else 0.0
    su2 = float((l[hi2] - l[mi]) / max(hi2 - mi, 1)) if hi2 > mi else 0.0
    ar = float(np.nansum(np.clip(lb - l, 0, None)) / nl)
    da = ar / ld if ld > 0 else 0.0
    gc = (ng - 1) / 2.0
    oot = np.ones(ng, dtype=bool)
    oot[int(gc - 0.1 * ng):int(gc + 0.1 * ng)] = False
    gs = float(np.nanstd(g[oot])) if oot.any() else 0.0
    gm2 = float(np.nanmedian(g[oot])) if oot.any() else float(np.nanmedian(g))
    gsd2 = float(max(gm2 - np.nanmin(g[oot]), 0.0)) if oot.any() else 0.0
    gsr = gsd2 / gd if gd > 0 else 0.0
    snr2 = gd / gs if gs > 0 else 0.0
    gsb = int((((gm2 - g) > 3 * gs) & (~np.isnan(g))).sum())
    gv2 = g[~np.isnan(g)]; lv2 = l[~np.isnan(l)]
    gi = float(np.nanpercentile(g, 75) - np.nanpercentile(g, 25))
    gsk = float(stats.skew(gv2)) if len(gv2) > 2 else 0.0
    lsk = float(stats.skew(lv2)) if len(lv2) > 2 else 0.0
    gku = float(stats.kurtosis(gv2)) if len(gv2) > 2 else 0.0
    lku = float(stats.kurtosis(lv2)) if len(lv2) > 2 else 0.0
    ga = _ac1(g); laa = _ac1(l)
    lg = ld / gd if gd > 0 else 0.0
    gp = [float(x) for x in np.nanpercentile(g, [5, 25, 50, 75, 95])]
    lp = [float(x) for x in np.nanpercentile(l, [5, 25, 50, 75, 95])]
    f.update({
        "l_width50": w50, "l_width10": w10, "l_w_ratio": wr, "l_bottom_std": bs,
        "l_com_offset": co, "l_asym": la2, "l_slope_dn": sd2, "l_slope_up": su2,
        "l_area": ar, "l_depth_area": da, "g_oot_std": gs, "g_sec_depth": gsd2,
        "g_sec_ratio": gsr, "snr_proxy": snr2, "g_n_sig_bins": gsb, "g_iqr": gi,
        "g_skew": gsk, "l_skew": lsk, "g_kurt": gku, "l_kurt": lku,
        "g_ac1": ga, "l_ac1": laa, "l_over_g_depth": lg,
        "g_p5": gp[0], "g_p25": gp[1], "g_p50": gp[2], "g_p75": gp[3], "g_p95": gp[4],
        "l_p5": lp[0], "l_p25": lp[1], "l_p50": lp[2], "l_p75": lp[3], "l_p95": lp[4],
    })
    return f

def _pg(m, s, n):
    s = s if s and s > 0 else abs(m) * 0.05 + 1e-6
    return np.clip(RNG.normal(m, s, n), 1e-6, None)

def derive_geo(per, psig, dep, dsig, dur, dursig):
    ps = _pg(per, psig or 0, NMC)
    ds = _pg(dep / 1e6, (dsig or 0) / 1e6, NMC)
    dd = _pg(dur / 24.0, (dursig or 0) / 24.0, NMC)
    ms = _pg(1.0, 0.15, NMC); rs = _pg(1.0, 0.15, NMC)
    rp = np.sqrt(ds)
    a_au = (ms * (ps / 365.25) ** 2) ** (1 / 3)
    a_rs = (a_au * AU_RSUN) / rs
    t = (dd * np.pi / ps) * a_rs
    bsq = (1 + rp) ** 2 - t ** 2
    v = bsq >= 0
    fl = "stellar_params_imputed"
    if v.sum() < 0.2 * NMC:
        fl += "+geometry_inconsistent"
    b = np.full(NMC, np.nan); b[v] = np.sqrt(bsq[v])
    ci = np.clip(b[v] / a_rs[v], -1, 1)
    inc = np.degrees(np.arccos(ci))
    def sm(x):
        x = x[np.isfinite(x)]
        return (float(np.mean(x)), float(np.std(x))) if len(x) else (np.nan, np.nan)
    r1, r2 = sm(rp); a1, a2 = sm(a_rs); b1, b2 = sm(b); i1, i2 = sm(inc)
    return dict(Rp_Rstar=r1, Rp_Rstar_sigma=r2, a_Rstar=a1, a_Rstar_sigma=a2,
                Inclination_deg=i1, Inclination_deg_sigma=i2,
                Impact_Parameter=b1, Impact_Parameter_sigma=b2, geometry_flag=fl)

def odd_even(t, f, per, epo, dur):
    t = np.asarray(t, float); f = np.asarray(f, float)
    hw = max(dur / 24.0 * 0.5, 1e-4)
    ei = np.round((t - epo) / per).astype(int)
    ph = (t - epo) - ei * per
    it = np.abs(ph) < hw
    om = it & (ei % 2 != 0); em = it & (ei % 2 == 0)
    if om.sum() < 5 or em.sum() < 5:
        return False, 0.0
    do = -np.nanmedian(f[om]); de = -np.nanmedian(f[em])
    eo = np.nanstd(f[om]) / np.sqrt(om.sum())
    ee = np.nanstd(f[em]) / np.sqrt(em.sum())
    ce = np.sqrt(eo ** 2 + ee ** 2) or 1e-9
    s = abs(do - de) / ce
    return bool(s > OE_SIGMA), float(s)

def centroid_check(t, c1, c2, per, epo, dur):
    ph = ((np.asarray(t, float) - epo) / per + 0.5) % 1.0 - 0.5
    d = dur / 24.0
    it = np.abs(ph) < d / (2 * per); ot = ~it
    ok = np.isfinite(c1) & np.isfinite(c2)
    it = it & ok; ot = ot & ok
    if it.sum() < 5 or ot.sum() < 20:
        return False
    d1 = np.nanmean(c1[it]) - np.nanmean(c1[ot])
    d2 = np.nanmean(c2[it]) - np.nanmean(c2[ot])
    e1 = np.nanstd(c1[ot]) / np.sqrt(it.sum())
    e2 = np.nanstd(c2[ot]) / np.sqrt(it.sum())
    s = np.sqrt((d1 / e1) ** 2 + (d2 / e2) ** 2) if e1 > 0 and e2 > 0 else 0.0
    return bool(s > 4.0)

def idx(root):
    d = {}
    for p in glob.glob(os.path.join(root, "**", "*.csv"), recursive=True):
        d[os.path.basename(p)] = p
    return d


def main():
    bls_df = pd.read_csv(BLS)
    bls_rows = {r["sample_id"]: r.to_dict() for _, r in bls_df.iterrows()}
    all_ids = [f"BAH_SampleData_Set-1_{i:06d}.csv" for i in range(1, 20001)]
    print(f"Total dataset size: {len(all_ids)} samples (from 1 to 20000)")

    pi = idx(PROC); ri = idx(RAW)
    print(f"Processed: {len(pi)}  Sources: {len(ri)}")
    print("Loading models...")
    xp = joblib.load(os.path.join(MDIR, "xgb_phys.joblib"))
    xv = joblib.load(os.path.join(MDIR, "xgb_view.joblib"))
    print("Models OK. Classifying ALL 11,000...")

    rows = []
    for sid in tqdm(all_ids, desc="Classifying ALL"):
        br = bls_rows.get(sid)
        r = dict(
            sample_id=sid,
            sde=br.get("sde", np.nan) if br else np.nan,
            depth_snr=np.nan, dur_frac=np.nan,
            Final_Class="UNKNOWN",
            P_Planet=np.nan, P_EB=np.nan, P_FP=np.nan,
            Period=np.nan, Period_sigma=np.nan, Epoch=np.nan, Epoch_sigma=np.nan,
            Depth_ppm=np.nan, Depth_ppm_sigma=np.nan,
            Duration_hr=np.nan, Duration_hr_sigma=np.nan,
            Rp_Rstar=np.nan, Rp_Rstar_sigma=np.nan,
            a_Rstar=np.nan, a_Rstar_sigma=np.nan,
            Inclination_deg=np.nan, Inclination_deg_sigma=np.nan,
            Impact_Parameter=np.nan, Impact_Parameter_sigma=np.nan,
            oe_flag=False, centroid_flag=False,
            qc_override="", classify_status="",
        )

        if br is None or any(
            not np.isfinite(br.get(k, np.nan))
            for k in ["Period", "sde", "Depth_ppm", "Duration_hr"]
        ):
            r["classify_status"] = "no_bls"
            rows.append(r)
            continue

        for k in ["Period", "Period_sigma", "Epoch", "Epoch_sigma",
                   "Depth_ppm", "Depth_ppm_sigma", "Duration_hr", "Duration_hr_sigma"]:
            r[k] = br.get(k, np.nan)
        r["sde"] = br["sde"]
        ds = br.get("Depth_ppm_sigma", 0)
        r["depth_snr"] = br["Depth_ppm"] / ds if ds and ds > 0 else 0.0
        r["dur_frac"] = br["Duration_hr"] / (br["Period"] * 24.0)

        pp = pi.get(sid)
        ta = fa = None
        if pp:
            try:
                lc = pd.read_csv(pp)
                ta = lc["TIME"].values; fa = lc["FLUX"].values
            except Exception:
                pass

        if ta is None:
            r["classify_status"] = "no_lc"
            rows.append(r)
            continue

        # odd-even test
        try:
            oe, _ = odd_even(ta, fa, br["Period"], br["Epoch"], br["Duration_hr"])
            r["oe_flag"] = oe
        except Exception:
            pass

        # build views + features + classify
        try:
            gv, lv = build_views(ta, fa, br["Period"], br["Epoch"], br["Duration_hr"])
            ft = extract_feats(gv, lv)
            pv = np.array([ft.get(k, 0.0) for k in FEAT_LIST], dtype=float)
            pv[~np.isfinite(pv)] = 0.0
            vv = np.concatenate([np.nan_to_num(gv, nan=0.0), np.nan_to_num(lv, nan=0.0)])

            pp2 = xp.predict_proba(pv.reshape(1, -1))[0]
            pv2 = xv.predict_proba(vv.reshape(1, -1))[0]
            ens = (pp2 + pv2) / 2.0
            fc = INT2LABEL[int(np.argmax(ens))]
            ov = None

            if r["oe_flag"] and fc != "EB":
                ov = fc + "->EB (odd-even)"; fc = "EB"

            # centroid check
            rp2 = ri.get(sid)
            if rp2:
                try:
                    raw = pd.read_csv(rp2)
                    raw = raw[raw["QUALITY"] == 0]
                    cf = centroid_check(
                        raw["TIME"].values, raw["MOM_CENTR1"].values,
                        raw["MOM_CENTR2"].values,
                        br["Period"], br["Epoch"], br["Duration_hr"],
                    )
                    r["centroid_flag"] = cf
                    if cf and fc == "PLANET":
                        ov = "PLANET->FP (centroid)"; fc = "FP"
                except Exception:
                    pass

            r["Final_Class"] = fc
            r["qc_override"] = ov or ""
            r["P_Planet"] = float(ens[0])
            r["P_EB"] = float(ens[1])
            r["P_FP"] = float(ens[2])
            r["classify_status"] = "ok"

            # geometry for planets
            if fc == "PLANET":
                try:
                    g2 = derive_geo(
                        r["Period"], r["Period_sigma"],
                        r["Depth_ppm"], r["Depth_ppm_sigma"],
                        r["Duration_hr"], r["Duration_hr_sigma"],
                    )
                    for k2 in ["Rp_Rstar", "Rp_Rstar_sigma", "a_Rstar", "a_Rstar_sigma",
                               "Inclination_deg", "Inclination_deg_sigma",
                               "Impact_Parameter", "Impact_Parameter_sigma"]:
                        r[k2] = g2[k2]
                except Exception:
                    pass
        except Exception as e:
            r["classify_status"] = "err: " + str(e)

        rows.append(r)

    df = pd.DataFrame(rows).sort_values("sample_id").reset_index(drop=True)
    n_ok = (df["classify_status"] == "ok").sum()
    print(f"\nClassified OK: {n_ok} / {len(df)}")

    E1 = ["sample_id", "Final_Class"]
    E2 = ["sample_id", "Final_Class",
          "Period", "Period_sigma", "Epoch", "Epoch_sigma",
          "Depth_ppm", "Depth_ppm_sigma", "Duration_hr", "Duration_hr_sigma",
          "Rp_Rstar", "Rp_Rstar_sigma", "a_Rstar", "a_Rstar_sigma",
          "Inclination_deg", "Inclination_deg_sigma",
          "Impact_Parameter", "Impact_Parameter_sigma"]
    GEO = ["Rp_Rstar", "Rp_Rstar_sigma", "a_Rstar", "a_Rstar_sigma",
           "Inclination_deg", "Inclination_deg_sigma",
           "Impact_Parameter", "Impact_Parameter_sigma"]

    def write_mode(df_in, dirname, label):
        d = os.path.join(BASE, dirname)
        os.makedirs(d, exist_ok=True)
        # clear geometry for non-PLANET
        for gc in GEO:
            df_in.loc[df_in["Final_Class"] != "PLANET", gc] = np.nan
        # clear BLS params for UNKNOWN
        for bc in ["Period", "Period_sigma", "Epoch", "Epoch_sigma",
                    "Depth_ppm", "Depth_ppm_sigma", "Duration_hr", "Duration_hr_sigma"]:
            df_in.loc[df_in["Final_Class"] == "UNKNOWN", bc] = np.nan
        df_in[E1].to_csv(os.path.join(d, "evaluation1_classification.csv"), index=False)
        df_in[E2].to_csv(os.path.join(d, "evaluation2_parameters.csv"), index=False)
        df_in.to_csv(os.path.join(d, "internal_full.csv"), index=False)
        vc = df_in["Final_Class"].value_counts()
        print(f"\n=== {label} ===")
        for cls in ["PLANET", "EB", "FP", "UNKNOWN"]:
            print(f"  {cls:8s}: {vc.get(cls, 0):5d}")
        return vc

    # Mode 1: NO FILTER — all classified results as-is
    df1 = df.copy()
    c1 = write_mode(df1, "submission_no_filter", "NO FILTER (all 11,000 classified)")

    # Mode 2: SDE >= 7 only
    df2 = df.copy()
    df2.loc[df2["sde"] < SDE_MIN, "Final_Class"] = "UNKNOWN"
    c2 = write_mode(df2, "submission_sde_only", "SDE >= 7 ONLY")

    # Mode 3: ALL FILTERS (SDE + SNR + Duration)
    df3 = df.copy()
    fail = (df3["sde"] < SDE_MIN) | (df3["depth_snr"] < SNR_MIN) | (df3["dur_frac"] > MAX_DUR_FRAC)
    df3.loc[fail, "Final_Class"] = "UNKNOWN"
    c3 = write_mode(df3, "submission_all_filters", "ALL FILTERS (SDE+SNR+Duration)")

    # Comparison table
    print("\n" + "=" * 60)
    print("COMPARISON TABLE")
    print("=" * 60)
    print(f"{'Class':8s}  {'NoFilter':>10s}  {'SDE>=7':>10s}  {'AllFilters':>10s}")
    print("-" * 44)
    for cls in ["PLANET", "EB", "FP", "UNKNOWN"]:
        print(f"{cls:8s}  {c1.get(cls, 0):10d}  {c2.get(cls, 0):10d}  {c3.get(cls, 0):10d}")
    total_clf = lambda c: sum(c.get(x, 0) for x in ["PLANET", "EB", "FP"])
    print("-" * 44)
    print(f"{'TOTAL':8s}  {total_clf(c1):10d}  {total_clf(c2):10d}  {total_clf(c3):10d}")
    print("=" * 60)


if __name__ == "__main__":
    main()
