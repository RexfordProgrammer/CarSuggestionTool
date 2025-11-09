from enum import Enum
import pandas as pd

class drive_train_enum(Enum):
    FWD = "FWD"
    twoWD = "2WD"
    AWD = "AWD"
    fourWD = "4WD"
    RWD = "RWD"
    ADW = "ADW"
    fourx2 = "4x2"
    fourx4 = "4x4"

class vehicle_type_enum(Enum):
    PC = "PC"
    MPV = "MPV"
    PHEV = "PHEV"
    BEV = "BEV"
    SUV = "SUV"
    four_DR = "4 DR"
    TRUCK = "TRUCK"
    PU_CC = "PU/CC"
    five_HB = "5 HB"
    BUS = "BUS" #all buses will probably be dropped from database but just in case
    MPV_BUS = "MPV_BUS" #see above
    VAN = "VAN"
    SPORT_UTILITY_VEHICLE = "SPORT UTILITY VEHICLE" #originally space instead of _
    HEAVY_PASSENGER_CAR = "HEAVY PASSENGER CAR"
    MEDIUM_PASSENGER_CAR = "MEDIUM PASSENGER CAR"
    LIGHT_PASSENGER_CAR = "LIGHT PASSENGER CAR"
    COMPACT_PASSENGER_CAR = "COMPACT PASSENGER CAR"
    PICKUP = "PICKUP"
    MINI_PASSENGER_CAR = "MINI PASSENGER CAR"

class overall_stars(Enum):
    one = "1"
    two = "2"
    three = "3"
    four = "4"
    five = "5"

#excludes a lot of options that are like 5 or 7
#will include more once I confirm this works
class num_of_seating(Enum):
    one = ["1", "1 to 2", "1 to 5"]
    two = ["2"]
    three = ["3"]
    four = ["4"]
    five = ["5", "57,", '"5, 7"', ]
    six = ["6"]
    seven = ["7"]
    eight = ["8"]
    nine = ["9"]
    twelve = ["12"]
    fifteen = ["15"]

#'MAKE'
#'MODEL'
#'MODEL_YR'
#'VEHICLE_TYPE' str
#'DRIVE_TRAIN' str
#'NUM_OF_SEATING' int
#'OVERALL_STARS' int between 0 and 5 inclusive

#flags are defined as enums
#sort flags by type?
def filterCars(database, flags_list = []):
    for x in flags_list:
        if isinstance(x, drive_train_enum):
            database = database.loc[database['DRIVE_TRAIN'] == x._value_]
        elif isinstance(x, vehicle_type_enum):
            database = database.loc[database['VEHICLE_TYPE'] == x._value_]
        elif isinstance(x, num_of_seating):
            database = database[database['NUM_OF_SEATING'].isin(x._value_)]
        elif isinstance(x, overall_stars):
            database = database.loc[database['OVERALL_STARS'] == x._value_]
    return database

#creates a ranking column
def wants(database, flags_list = []):
    return database

df = pd.read_csv("backend\\data\\nhtsa_prepared.csv", dtype = str)
test_flags = [overall_stars.five, num_of_seating.four]
new_df = filterCars(df,test_flags)
print(new_df)
#print(df.loc[df['NUM_OF_SEATING'] == "4"])