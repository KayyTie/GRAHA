import os
import glob
import pandas as pd

base_dir = r"D:\Bhartiya Antariksh Hackathon\ph3\batch_020-20260806T233212Z-1-001\BLS_result"

# Find all batch summary files (batch_000_bls_summary.csv to batch_021_bls_summary.csv)
summary_files = sorted(glob.glob(os.path.join(base_dir, "batch_*", "*_bls_summary.csv")))
print(f"Found {len(summary_files)} BLS summary files.")

dfs = []
for f in summary_files:
    df = pd.read_csv(f)
    dfs.append(df)
    print(f"  {os.path.basename(f)}: {len(df)} rows")

if dfs:
    merged_df = pd.concat(dfs, ignore_index=True)
    print("\n--- Merged Summary Info ---")
    print(f"Total rows: {len(merged_df)}")
    print(f"Columns ({len(merged_df.columns)}): {list(merged_df.columns)}")
    print(f"Unique sample_ids: {merged_df['sample_id'].nunique()}")

    # Save output files inside BLS_result
    out_blsresult = os.path.join(base_dir, "blsresult.csv")
    merged_df.to_csv(out_blsresult, index=False)
    print(f"Saved merged CSV to: {out_blsresult}")

    out_bls_result = os.path.join(base_dir, "bls_result.csv")
    merged_df.to_csv(out_bls_result, index=False)
    print(f"Saved merged CSV to: {out_bls_result}")
else:
    print("No summary CSV files found.")
