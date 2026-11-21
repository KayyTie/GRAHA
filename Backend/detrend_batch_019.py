import os
import glob
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import pandas as pd
from tqdm import tqdm

from detrending import apply_quality_mask, detrend_lightcurve

warnings.filterwarnings('ignore')

# Path Configuration
BASE_DIR = r"D:\Bhartiya Antariksh Hackathon\ph3\batch_020-20260806T233212Z-1-001"
BATCH_NAME = "batch_019"
INPUT_DIR = os.path.join(BASE_DIR, BATCH_NAME)
PROCESSED_DIR = os.path.join(BASE_DIR, "Processed", BATCH_NAME)

os.makedirs(PROCESSED_DIR, exist_ok=True)

N_WORKERS = 8
REQUIRED_COLS = {'TIME', 'SAP_FLUX', 'SAP_FLUX_ERR', 'QUALITY'}
QUALITY_BITMASK = 175

def process_file_detrend(filepath):
    """
    Worker function to detrend a single raw light curve CSV
    and save the output into PROCESSED_DIR.
    """
    warnings.filterwarnings('ignore')
    filename = os.path.basename(filepath)

    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        return {'sample_id': filename, 'status': f'read_error: {e}'}

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

        final_time, final_flux, final_err, trend = detrend_lightcurve(time_arr, flux_arr, err_arr)
        if final_time is None or len(final_time) < 100:
            return {'sample_id': filename, 'status': 'detrend_failed'}

        out_df = pd.DataFrame({'TIME': final_time, 'FLUX': final_flux,
                                'FLUX_ERR': final_err, 'TREND': trend})
        out_path = os.path.join(PROCESSED_DIR, filename)
        out_df.to_csv(out_path, index=False)

        return {'sample_id': filename, 'status': 'ok'}

    except Exception as e:
        return {'sample_id': filename, 'status': f'error: {e}'}

def main():
    raw_csvs = sorted(glob.glob(os.path.join(INPUT_DIR, "*.csv")))
    raw_csvs = [f for f in raw_csvs if not os.path.basename(f).lower().endswith('-checkpoint.csv')]

    if not raw_csvs:
        raise FileNotFoundError(f"No CSV files found in {INPUT_DIR}")

    print(f"Found {len(raw_csvs)} raw files in {INPUT_DIR}.")
    print(f"Detrending using {N_WORKERS} parallel workers...")
    print(f"Output directory: {PROCESSED_DIR}\n")

    results = []
    with ProcessPoolExecutor(max_workers=N_WORKERS) as executor:
        futures = {executor.submit(process_file_detrend, f): f for f in raw_csvs}
        for fut in tqdm(as_completed(futures), total=len(futures), desc=f"Detrending {BATCH_NAME}"):
            src = futures[fut]
            try:
                results.append(fut.result())
            except Exception as e:
                results.append({'sample_id': os.path.basename(src), 'status': f'crash: {e}'})

    res_df = pd.DataFrame(results)
    ok_count = (res_df['status'] == 'ok').sum()
    failed_count = (res_df['status'] != 'ok').sum()

    print("\n" + "=" * 60)
    print(f"Detrending Complete for {BATCH_NAME}!")
    print(f" Successfully Processed : {ok_count} files")
    print(f" Failed / Skipped       : {failed_count} files")
    print(f" Detrended CSVs saved in : {PROCESSED_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    main()
