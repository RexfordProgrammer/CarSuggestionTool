# make_pk_sk.py
import pandas as pd

#what columns to save
nhtsaSafetyFields = ['MAKE', 'MODEL', 'MODEL_YR', 'BODY_STYLE', 'VEHICLE_TYPE', 'DRIVE_TRAIN', 'NUM_OF_SEATING', 'OVERALL_STARS']
minimumYear = 2000; #drop any car made before 2000.

#the file to read
nhtsaSafetyDf = pd.read_csv("backend\\data\\Safercar_data.csv", dtype = str)

#set default value
for col, default in [("MAKE",""), ("MODEL",""), ("MODEL_YR","0000"), ("BODY_STYLE",""), ("VEHICLE_TYPE", ""), ("DRIVE_TRAIN", ""), ("NUM_OF_SEATING", ""), ("OVERALL_STARS", "")]:
    if col not in nhtsaSafetyDf:
        nhtsaSafetyDf[col] = default
    nhtsaSafetyDf[col] = nhtsaSafetyDf[col].fillna(default).astype(str).str.strip()

#remove unneeded columns
nhtsaSafetyDf = nhtsaSafetyDf[nhtsaSafetyFields]

#key, can use multiindexing but this is probably easier
nhtsaSafetyDf['PK'] = nhtsaSafetyDf['MAKE'] + "#" + nhtsaSafetyDf['MODEL']
nhtsaSafetyDf['SK'] = nhtsaSafetyDf['MODEL_YR'] + "#" + nhtsaSafetyDf['BODY_STYLE']

#drop all cars made before 2000
nhtsaSafetyDf['MODEL_YR'] = pd.to_numeric(nhtsaSafetyDf['MODEL_YR'], downcast='integer')
nhtsaSafetyDf.drop(nhtsaSafetyDf.loc[nhtsaSafetyDf['MODEL_YR'] <= minimumYear].index, inplace=False)

nhtsaSafetyDf.to_csv("backend\\data\\nhtsa_prepared.csv", index=False)
print("✅ Wrote nhtsa_prepared.csv")
