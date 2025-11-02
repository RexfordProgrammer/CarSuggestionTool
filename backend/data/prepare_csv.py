# make_pk_sk.py
import pandas as pd

df = pd.read_csv("nhtsa.csv", dtype=str)  # keep everything as strings
for col, default in [("MAKE",""), ("MODEL",""), ("MODEL_YR",""), ("BODY_STYLE","NA")]:
    if col not in df.columns:
        df[col] = default
    df[col] = df[col].fillna(default).astype(str).str.strip()

# normalize MODEL_YR to 4-digit or '0000'
df["MODEL_YR"] = df["MODEL_YR"].str.extract(r'(\d{4})', expand=False).fillna("0000")

df["PK"] = df["MAKE"] + "#" + df["MODEL"]
df["SK"] = df["MODEL_YR"] + "#" + df["BODY_STYLE"]

df.to_csv("nhtsa_prepared.csv", index=False)
print("✅ Wrote nhtsa_prepared.csv")
