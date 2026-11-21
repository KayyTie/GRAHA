"""
BLS (Box Least Squares) Transit Search Module
================================================
Consumes the output of the batch detrending stage (TIME, FLUX, FLUX_ERR,
TREND columns) and runs a Box Least Squares search, then extracts the
higher-weightage Evaluation-2 columns:

    Period, Period_sigma, Epoch, Epoch_sigma,
    Depth_ppm, Depth_ppm_sigma, Duration_hr, Duration_hr_sigma

NOTE on scope: BLS alone cannot produce Rp_Rstar, a_Rstar, Inclination_deg,
or Impact_Parameter (the lower-weightage geometric columns) — those need a
transit-model fit (e.g. batman / exoplanet) on top of the Period/Epoch/
Duration/Depth this module gives you. That is a separate downstream stage.
"""

import numpy as np
import astropy.units as u
from astropy.timeseries import BoxLeastSquares

# Fixed search grid — matches the original combined script, unchanged.
MIN_PERIOD = 0.5
MAX_PERIOD = 15.0
N_PERIODS = 6000
MIN_DURATION = 0.03
MAX_DURATION = 0.25
N_DURATIONS = 50


def build_search_grids(min_period=MIN_PERIOD, max_period=MAX_PERIOD, n_periods=N_PERIODS,
                        min_duration=MIN_DURATION, max_duration=MAX_DURATION, n_durations=N_DURATIONS):
    """Build the period (linear) and duration (log-spaced) search grids, in days."""
    periods = np.linspace(min_period, max_period, n_periods) * u.day
    durations = np.logspace(np.log10(min_duration), np.log10(max_duration), n_durations) * u.day
    return periods, durations


def run_bls(time, flux, flux_err=None, periods=None, durations=None, **grid_kwargs):
    """
    Run BoxLeastSquares on a detrended light curve.

    Parameters
    ----------
    time : array-like, days
    flux : array-like, detrended flux (median-subtracted internally)
    flux_err : array-like, optional
        Per-point flux uncertainty (the FLUX_ERR column from detrending).
        Passed to BLS as `dy` so depth_err / depth_snr are weighted by
        real photometric noise instead of assumed unit weights.
    periods, durations : astropy Quantity arrays, optional
        If omitted, built via build_search_grids(**grid_kwargs)

    Returns
    -------
    dict with keys: model, results, best_index, best_period, best_power,
    sde, mean_power, std_power — or None if the search fails.
    """
    if periods is None or durations is None:
        periods, durations = build_search_grids(**grid_kwargs)

    time = np.asarray(time, dtype=float)
    flux = np.asarray(flux, dtype=float)
    flux_for_bls = flux - np.nanmedian(flux)

    dy = np.asarray(flux_err, dtype=float) if flux_err is not None else None

    try:
        model = BoxLeastSquares(time * u.day, flux_for_bls, dy=dy)
        results = model.power(period=periods, duration=durations)
    except Exception:
        return None

    power = np.asarray(results.power, dtype=float)
    power[~np.isfinite(power)] = 0.0

    best_idx = int(np.argmax(power))
    best_period = float(results.period[best_idx].value)
    best_power = float(power[best_idx])

    mean_power, std_power = float(np.mean(power)), float(np.std(power))
    sde = (best_power - mean_power) / std_power if std_power > 0 else 0.0

    return {
        'model': model,
        'results': results,
        'best_index': best_idx,
        'best_period': best_period,
        'best_power': best_power,
        'sde': sde,
        'mean_power': mean_power,
        'std_power': std_power,
    }


def refine_period(model, coarse_period, coarse_duration, period_padding_frac=0.01,
                   n_refine_periods=2000, n_refine_durations=25):
    """
    Re-run BLS on a tight, high-resolution grid around the coarse best
    period. This tightens the period estimate (needed for Period_sigma)
    and gives a duration grid step small enough to trust Duration_hr.

    Reuses the same `model` (same time/flux/dy) returned by run_bls, so
    call this right after run_bls with model=out['model'].
    """
    p_lo = coarse_period * (1 - period_padding_frac)
    p_hi = coarse_period * (1 + period_padding_frac)
    periods_fine = np.linspace(p_lo, p_hi, n_refine_periods) * u.day
    durations_fine = np.logspace(
        np.log10(max(coarse_duration * 0.3, 1e-4)),
        np.log10(coarse_duration * 2.0),
        n_refine_durations
    ) * u.day

    results_fine = model.power(period=periods_fine, duration=durations_fine)
    power_fine = np.asarray(results_fine.power, dtype=float)
    power_fine[~np.isfinite(power_fine)] = 0.0
    best_idx = int(np.argmax(power_fine))

    period_grid_step = float(periods_fine[1].value - periods_fine[0].value)

    return {
        'results': results_fine,
        'best_index': best_idx,
        'period_grid_step': period_grid_step,
    }


def extract_transit_parameters(bls_out, refine_out=None):
    """
    Pull the Evaluation-2 higher-weightage columns out of a run_bls (and
    optionally refine_period) result.

    Parameters
    ----------
    bls_out : dict returned by run_bls
    refine_out : dict returned by refine_period, optional but recommended
        — without it, Period_sigma falls back to the coarse grid step
        (0.5-15 d over 6000 points -> ~0.0024 d), which is usually too
        loose to satisfy a 3-sigma catalog check.

    Returns
    -------
    dict with keys: Period, Period_sigma, Epoch, Epoch_sigma,
    Depth_ppm, Depth_ppm_sigma, Duration_hr, Duration_hr_sigma, sde
    """
    results = refine_out['results'] if refine_out is not None else bls_out['results']
    idx = refine_out['best_index'] if refine_out is not None else bls_out['best_index']

    period = float(results.period[idx].value)
    duration_days = float(results.duration[idx].value)
    depth = float(results.depth[idx])
    depth_err = float(results.depth_err[idx])
    epoch = float(results.transit_time[idx].value)
    depth_snr = float(results.depth_snr[idx]) if np.isfinite(results.depth_snr[idx]) else 1.0
    depth_snr = max(depth_snr, 1e-3)

    # --- Period_sigma ---
    # Half the local grid step from the refined search (or coarse grid if
    # no refinement was run). This is a resolution-based lower bound, not
    # a full statistical fit — good enough for a 3-sigma catalog check,
    # but bootstrap/MCMC will give a tighter, more defensible number.
    if refine_out is not None:
        period_sigma = refine_out['period_grid_step'] / 2.0
    else:
        period_sigma = (MAX_PERIOD - MIN_PERIOD) / (N_PERIODS - 1) / 2.0

    # --- Epoch_sigma ---
    # Ingress/egress timing precision scales roughly as duration / SNR.
    epoch_sigma = duration_days / (2.0 * depth_snr)

    # --- Depth / Duration in required units ---
    depth_ppm = depth * 1e6
    depth_ppm_sigma = depth_err * 1e6
    duration_hr = duration_days * 24.0

    # --- Duration_hr_sigma ---
    # No native duration uncertainty from BLS; approximate from local
    # spacing of the log-spaced duration grid around the best duration.
    duration_grid_frac_step = (np.log(MAX_DURATION) - np.log(MIN_DURATION)) / (N_DURATIONS - 1)
    duration_hr_sigma = duration_hr * duration_grid_frac_step / 2.0

    return {
        'Period': period,
        'Period_sigma': period_sigma,
        'Epoch': epoch,
        'Epoch_sigma': epoch_sigma,
        'Depth_ppm': depth_ppm,
        'Depth_ppm_sigma': depth_ppm_sigma,
        'Duration_hr': duration_hr,
        'Duration_hr_sigma': duration_hr_sigma,
        'sde': bls_out['sde'],
    }


if __name__ == "__main__":
    # Minimal smoke test with a synthetic transit signal + errors
    rng = np.random.default_rng(0)
    t = np.linspace(0, 27, 20000)
    period_true = 3.2
    depth_true = 0.01
    phase = (t % period_true) / period_true
    err = np.full_like(t, 0.0005)
    f = 1.0 + rng.normal(0, 0.0005, t.size)
    f[(phase > 0.48) & (phase < 0.52)] -= depth_true

    coarse = run_bls(t, f, flux_err=err)
    fine = refine_period(coarse['model'], coarse['best_period'], coarse_duration=0.1)
    params = extract_transit_parameters(coarse, fine)

    print("Coarse best period:", coarse['best_period'], "SDE:", coarse['sde'])
    print("Extracted parameters:")
    for k, v in params.items():
        print(f"  {k}: {v}")
