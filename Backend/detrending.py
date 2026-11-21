"""
Light Curve Detrending Module
==============================
Exact module extracted from your current running Colab cell
(BATCH DETRENDING VIA MODULE). Quality masking -> edge/gap trimming ->
asymmetric MAD outlier clipping -> Wotan biweight detrending, with
flux_err propagated through every stage.

Import and call `detrend_lightcurve(time, flux, flux_err)` to run the
full chain, or use the individual steps separately.
"""

import numpy as np
from astropy.stats import median_absolute_deviation
from scipy.ndimage import median_filter
from wotan import flatten


def apply_quality_mask(df, quality_bitmask=175, flux_col='SAP_FLUX', err_col='SAP_FLUX_ERR'):
    """Filter a dataframe using the TESS/Kepler QUALITY bitmask."""
    df = df.dropna(subset=['TIME', flux_col, err_col, 'QUALITY'])
    df_q = df[(df['QUALITY'].astype(int) & quality_bitmask) == 0]
    return df_q


def trim_edges_and_gaps(time, flux, flux_err, edge_buffer=0.2, gap_threshold=0.5, gap_buffer=0.1):
    """
    Remove points near the start/end of the light curve and around
    data gaps (a common source of ramp/systematic artifacts).
    """
    time = np.asarray(time)
    flux = np.asarray(flux)
    flux_err = np.asarray(flux_err)

    valid_mask = np.ones(len(time), dtype=bool)
    valid_mask[time < (time[0] + edge_buffer)] = False

    gaps = np.where(np.diff(time) > gap_threshold)[0]
    for g in gaps:
        valid_mask[(time > time[g] - gap_buffer) & (time <= time[g])] = False
        valid_mask[(time >= time[g + 1]) & (time < time[g + 1] + edge_buffer)] = False

    valid_mask[time > (time[-1] - gap_buffer)] = False

    return time[valid_mask], flux[valid_mask], flux_err[valid_mask]


def asymmetric_mad_clip(time, flux, flux_err, filter_size=31, flare_sigma=8.0,
                         upper_sigma_flare=2.0, lower_sigma_flare=-2.0,
                         upper_sigma_quiet=4.0, lower_sigma_quiet=-12.0):
    """
    Clip outliers against a median-filtered baseline. Flare-like regions
    (large local drift) get tight symmetric clipping; quiet regions get a
    loose lower bound so real transit dips aren't clipped away.
    """
    if len(time) <= 100:
        return time, flux, flux_err

    diff = np.diff(flux)
    mad = median_absolute_deviation(diff, ignore_nan=True) or 1e-5
    win = min(filter_size, len(flux) // 2 * 2 + 1)
    fast_med = median_filter(flux, size=win)

    baseline_drift = np.abs(fast_med - np.nanmedian(flux))
    is_flare = baseline_drift > (flare_sigma * 1.4826 * mad)

    upper_mult = np.where(is_flare, upper_sigma_flare, upper_sigma_quiet)
    lower_mult = np.where(is_flare, lower_sigma_flare, lower_sigma_quiet)

    m_up = (flux - fast_med) < (upper_mult * 1.4826 * mad)
    m_down = (flux - fast_med) > (lower_mult * 1.4826 * mad)
    clip_mask = m_up & m_down

    return time[clip_mask], flux[clip_mask], flux_err[clip_mask]


def wotan_detrend(time, flux, flux_err, window_length=0.5, method='biweight',
                   cval=6.0, break_tolerance=0.5, edge_cutoff=0.1):
    """
    Normalize by the median and remove stellar-variability trends with
    Wotan. Returns only the finite, detrended points plus the trend.
    """
    med_val = np.nanmedian(flux)
    flux_norm = flux / med_val
    flux_err_norm = flux_err / med_val

    flat_flux, trend = flatten(
        time, flux_norm,
        window_length=window_length,
        method=method,
        cval=cval,
        break_tolerance=break_tolerance,
        edge_cutoff=edge_cutoff,
        return_trend=True
    )

    # Condition the error by dividing it by the Wotan trend
    flat_err = flux_err_norm / trend

    valid = np.isfinite(flat_flux) & np.isfinite(flat_err)
    return time[valid], flat_flux[valid], flat_err[valid], trend[valid]


def detrend_lightcurve(time, flux, flux_err, min_points=100,
                        trim_kwargs=None, mad_kwargs=None, wotan_kwargs=None):
    """
    Full detrending pipeline: trim -> MAD clip -> Wotan flatten.

    Returns (final_time, final_flux, final_err, trend), or
    (None, None, None, None) if there isn't enough data left at any stage.
    """
    trim_kwargs = trim_kwargs or {}
    mad_kwargs = mad_kwargs or {}
    wotan_kwargs = wotan_kwargs or {}

    time = np.asarray(time)
    flux = np.asarray(flux, dtype=float)
    flux_err = np.asarray(flux_err, dtype=float)

    time_c, flux_c, err_c = trim_edges_and_gaps(time, flux, flux_err, **trim_kwargs)
    if len(time_c) < min_points:
        return None, None, None, None

    time_c, flux_c, err_c = asymmetric_mad_clip(time_c, flux_c, err_c, **mad_kwargs)
    if len(time_c) < min_points:
        return None, None, None, None

    try:
        final_time, final_flux, final_err, trend = wotan_detrend(time_c, flux_c, err_c, **wotan_kwargs)
    except Exception:
        return None, None, None, None

    return final_time, final_flux, final_err, trend


if __name__ == "__main__":
    # Minimal smoke test with synthetic data
    rng = np.random.default_rng(0)
    t = np.linspace(0, 27, 20000)
    f = 1.0 + 0.001 * np.sin(2 * np.pi * t / 5.0) + rng.normal(0, 0.0005, t.size)
    e = np.full_like(t, 0.0005)
    ft, ff, fe, trend = detrend_lightcurve(t, f, e)
    print("Detrended points:", 0 if ft is None else len(ft))
