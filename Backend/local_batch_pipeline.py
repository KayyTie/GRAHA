# ==================== LOCAL MULTI-BATCH PIPELINE (Detrend + BLS) ====================
import os
import glob
import warnings
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd
import numpy as np
from tqdm import tqdm

from detrending import apply_quality_mask, detrend_lightcurve
from bls_search import run_bls, refine_period, extract_transit_parameters

warnings.filterwarnings('ignore')

# ==========================================
# 1. CONFIGURATION & BATCH LOOP
# ==========================================
# Set your start and end batch numbers here
START_BATCH = 0
END_BATCH = 39

BASE_PATH = r"D:\Bhartiya Antariksh Hackathon\ph3\batch_020-20260806T233212Z-1-001"

N_WORKERS = 12

REQUIRED_COLS = {'TIME', 'SAP_FLUX', 'SAP_FLUX_ERR', 'QUALITY'}
QUALITY_BITMASK = 175

ORDERED_COLS = ['sample_id', 'Period', 'Period_sigma', 'Epoch', 'Epoch_sigma',
                'Depth_ppm', 'Depth_ppm_sigma', 'Duration_hr', 'Duration_hr_sigma', 'sde']


# ==========================================
# 2. PER-FILE WORKER
# ==========================================
def process_file(args):
    """
    Unpacks arguments to support passing dynamic output directories to the worker.
    """
    filepath, processed_dir = args
    warnings.filterwarnings('ignore')
    filename = os.path.basename(filepath)

    try:
        df = pd.read_csv(filepath)
    except Exception:
        return {'sample_id': filename, 'status': 'read_error'}

    if df.empty or not REQUIRED_COLS.issubset(df.columns):
        return {'sample_id': filename, 'status': 'missing_columns'}

    try:
        df_q = apply_quality_mask(df, quality_bitmask=QUALITY_BITMASK,
                                    flux_col='SAP_FLUX', err_col='SAP_FLUX_ERR')
        if len(df_q) < 100:
            return {'sample_id': filename, 'status': 'insufficient_points'}

        time_arr = df_q['TIME'].values
        flux_arr = df_q['SAP_FLUX'].values
        err_arr = df_q['SAP_FLUX_ERR'].values

        # --- Stage 1: Detrending ---
        final_time, final_flux, final_err, trend = detrend_lightcurve(time_arr, flux_arr, err_arr)
        if final_time is None or len(final_time) < 100:
            return {'sample_id': filename, 'status': 'detrend_failed'}

        out_df = pd.DataFrame({'TIME': final_time, 'FLUX': final_flux,
                                'FLUX_ERR': final_err, 'TREND': trend})
        out_df.to_csv(os.path.join(processed_dir, filename), index=False)

        # --- Stage 2: BLS ---
        coarse = run_bls(final_time, final_flux, flux_err=final_err)
        if coarse is None:
            return {'sample_id': filename, 'status': 'bls_failed'}

        try:
            fine = refine_period(
                coarse['model'], coarse['best_period'],
                coarse_duration=float(coarse['results'].duration[coarse['best_index']].value)
            )
        except Exception:
            fine = None

        params = extract_transit_parameters(coarse, fine)
        params['sample_id'] = filename
        params['status'] = 'ok'
        return params

    except Exception as e:
        return {'sample_id': filename, 'status': f'error: {e}'}


# ==========================================
# 3. MAIN — LOOP OVER BATCHES
# ==========================================
def main():
    for batch_num in range(START_BATCH, END_BATCH + 1):
        batch_str = f"batch_{batch_num:03d}"  # Formats numbers as 029, 030, etc.
        
        input_dir = os.path.join(BASE_PATH, "Sources", batch_str)
        processed_dir = os.path.join(BASE_PATH, "Processed", batch_str)
        bls_output_dir = os.path.join(BASE_PATH, "BlS_result", batch_str)

        os.makedirs(processed_dir, exist_ok=True)
        os.makedirs(bls_output_dir, exist_ok=True)

        raw_csvs = sorted(glob.glob(os.path.join(input_dir, "**/*.csv"), recursive=True))
        batch_files = [f for f in raw_csvs
                       if '.ipynb_checkpoints' not in f
                       and not os.path.basename(f).lower().endswith('-checkpoint.csv')]

        if not batch_files:
            print(f"\n[!] Warning: No CSV files found in {input_dir}. Skipping {batch_str}...")
            continue

        print(f"\nProcessing {batch_str}: Found {len(batch_files)} raw files across {N_WORKERS} cores...")

        # Prepare arguments list for workers (filepath, processed_dir)
        tasks = [(f, processed_dir) for f in batch_files]

        results = []
        with ProcessPoolExecutor(max_workers=N_WORKERS) as executor:
            futures = {executor.submit(process_file, task): task[0] for task in tasks}
            for fut in tqdm(as_completed(futures), total=len(futures), desc=f"{batch_str}"):
                src = futures[fut]
                try:
                    results.append(fut.result())
                except Exception as e:
                    results.append({'sample_id': os.path.basename(src), 'status': f'worker_crash: {e}'})

        all_df = pd.DataFrame(results)
        
        if 'status' in all_df.columns:
            ok_df = all_df[all_df['status'] == 'ok'].copy()
            skipped_df = all_df[all_df['status'] != 'ok'].copy()
        else:
            ok_df = pd.DataFrame()
            skipped_df = all_df

        if not ok_df.empty:
            # Keep only available standard output columns
            valid_cols = [col for col in ORDERED_COLS if col in ok_df.columns]
            ok_df = ok_df[valid_cols].sort_values(by='sample_id').reset_index(drop=True)

        summary_path = os.path.join(bls_output_dir, f"{batch_str}_bls_summary.csv")
        ok_df.to_csv(summary_path, index=False)

        skip_log_path = os.path.join(bls_output_dir, f"{batch_str}_skipped_log.csv")
        skipped_df.to_csv(skip_log_path, index=False)

        print("-" * 50)
        print(f"Finished {batch_str}:")
        print(f"  Successfully Processed : {len(ok_df)} files")
        print(f"  Skipped / Failed       : {len(skipped_df)} files")
        print("-" * 50)

    print("\n" + "=" * 60)
    print("ALL BATCHES COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    main()