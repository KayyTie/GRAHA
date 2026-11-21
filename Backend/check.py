import os
import glob
import pandas as pd

# Base path containing the batch files/folders
base_dir = r"D:\Bhartiya Antariksh Hackathon\ph3\batch_020-20260806T233212Z-1-001\BLS_result"

# Find all batch summary files (batch_000_bls_summary.csv to batch_021_bls_summary.csv)
summary_files = sorted(glob.glob(os.path.join(base_dir, "batch_*", "*_bls_summary.csv")))

all_dfs = []
for file in summary_files:
    df = pd.read_csv(file)
    all_dfs.append(df)

if all_dfs:
    merged_df = pd.concat(all_dfs, ignore_index=True)
    output_path = os.path.join(base_dir, "blsresult.csv")
    merged_df.to_csv(output_path, index=False)
    print(f"Successfully merged {len(all_dfs)} summary files ({len(merged_df)} total rows). Saved to: {output_path}")
else:
    print("No summary CSV files found.")