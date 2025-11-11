#file contins enums for preference flags & method to make enum
#also includes a filterCars() method to demonstrate how flags may be used

from enum import Enum
import pandas as pd

#note: model is missing because it returned >1000 which is too much to store

class make(Enum):
    GM = ["GM"]
    BMW = ["BMW"]
    GMC = ["GMC"]
    KIA = ["KIA"]
    STI = ["STI"]
    GEO = ["GEO"]
    SRT = ["SRT"]
    RAM = ["RAM"]
    ALFA = ["ALFA", "ALFA ROMEO"]
    FIAT = ["FIAT"]
    CODA = ["CODA"]
    SAAB = ["SAAB"]
    MINI = ["MINI"]
    FORD = ["FORD"]
    JEEP = ["JEEP"]
    AUDI = ["AUDI"]
    VOLVO = ["VOLVO"]
    BUICK = ["BUICK"]
    LEXUS = ["LEXUS"]
    LUCID = ["LUCID"]
    MAZDA = ["MAZDA"]
    HONDA = ["HONDA"]
    EAGLE = ["EAGLE"]
    ISUZU = ["ISUZU"]
    SMART = ["SMART"]
    TESLA = ["TESLA"]
    ACURA = ["ACURA"]
    DODGE = ["DODGE"]
    NISSAN = ["NISSAN"]
    HUMMER = ["HUMMER"]
    JAGUAR = ["JAGUAR"]
    TOYOTA = ["TOYOTA"]
    SUBARU = ["SUBARU"]
    RIVIAN = ["RIVIAN"]
    SATURN = ["SATURN"]
    SUZUKI = ["SUZUKI"]
    DAEWOO = ["DAEWOO"]
    LINCOLN = ["LINCOLN"]
    MAYBACH = ["MAYBACH"]
    PORSCHE = ["PORSCHE"]
    PONTIAC = ["PONTIAC"]
    HYUNDAI = ["HYUNDAI"]
    GENESIS = ["GENESIS"]
    MERCURY = ["MERCURY"]
    VINFAST = ["VINFAST"]
    FERRARI = ["FERRARI"]
    BENTLEY = ["BENTLEY"]
    CHRYSLER = ["CHRYSLER"]
    POLESTAR = ["POLESTAR"]
    MASERATI = ["MASERATI"]
    PLYMOUTH = ["PLYMOUTH"]
    CADILLAC = ["CADILLAC"]
    INFINITI = ["INFINITI"]
    CHEVROLET = ["CHEVROLET"]
    VOLKSWAGEN = ["VOLKSWAGEN"]
    LAND_ROVER = ["LAND ROVER"]
    OLDSMOBILE = ["OLDSMOBILE"]
    BRIGHTDROP = ["BRIGHTDROP"]
    MITSUBISHI = ["MITSUBISHI"]
    ROLLS_ROYCE = ["ROLLS-ROYCE"]
    FREIGHTLINER = ["FREIGHTLINER"]
    MERCEDES_BENZ = ["MERCEDES-BENZ"]
    MERCEDES_MAYBACH = ["MERCEDES-MAYBACH"]

class drive_train(Enum):
    FWD = ["FWD", "AWD/FWD", "FWD/AWD", "FWD/4WD"]
    AWD = ["AWD", "AWD/FWD", "FWD/AWD", "RWD/AWD", "AWD/2WD", "2WD/AWD", "AWD/RWD"]
    RWD = ["RWD", "RWD/4WD", "RWD/AWD", "AWD/RWD"]
    fourWD = ["4WD", "RWD/4WD", "FWD/4WD", "4WD/2WD"]
    nan = ["nan"]
    twoWD = ["2WD", "AWD/2WD", "4WD/2WD", "2WD/AWD"]
    ADW = ["ADW"]
    fourx2 = ["4x2"]
    fourx4 = ["4x4"]
    fWD = ["fWD"]

class vehicle_type(Enum):
    PC = ["PC"]
    MPV = ["MPV", "MPV/BUS"]
    nan = ["nan"]
    BEV = ["BEV"]
    SUV = ["SUV"]
    BUS = ["BUS", "MPV/BUS"]
    VAN = ["VAN"]
    PHEV = ["PHEV"]
    five_HB = ["5 HB"]
    four_DR = ["4 DR"]
    TRUCK = ["TRUCK"]
    PU_CC = ["PU/CC"]
    PICKUP = ["PICKUP"]
    MINI_PASSENGER_CAR = ["MINI PASSENGER CAR"]
    HEAVY_PASSENGER_CAR = ["HEAVY PASSENGER CAR"]
    LIGHT_PASSENGER_CAR = ["LIGHT PASSENGER CAR"]
    MEDIUM_PASSENGER_CAR = ["MEDIUM PASSENGER CAR"]
    SPORT_UTILITY_VEHICLE = ["SPORT UTILITY VEHICLE"]
    COMPACT_PASSENGER_CAR = ["COMPACT PASSENGER CAR"]

class overall_stars(Enum):
    five = ["5"]
    four = ["4"]
    three = ["3"]
    two = ["2"]
    one = ["1"] #manually added since there is no car with a 1 rating
    nan = ["nan"]

#temp, currently the only enum that isn't working
#since num of seating is very badly formatted
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

#accepts a pandas database and a str column (case-sensitive)
def make_enum(database, column):
    if (column not in database.columns):
        print("column " + column + " does not exist")
        return
    print("class " + column.lower() + "(Enum):")
    #get data
    unique_values = pd.DataFrame(columns=[column],data=database[column].drop_duplicates())
    
    #sort by length
    unique_values['tempForSorting'] = unique_values[column].astype(str).map(len)
    unique_values = unique_values.sort_values(by=['tempForSorting'])
    unique_values = unique_values[column]
    
    enum_list = [] #2D list
    #seperaters_list = [",", " ", "/"]  
    seperaters_list = []

    for val in unique_values:
        val = str(val).replace("\n", " ")
        temp = split(str(val), seperaters_list)
        #if no seperater, add it to list
        if len(temp) == 1:
            enum_list.append([val])
        else:
            #check if seperater already exist
            #if so add it to its list
            prev_existed = False
            for i in temp:
                for j in enum_list:
                    if i == j[0]:
                        prev_existed = True
                        enum_list[enum_list.index(j)].append(val)
            if not prev_existed:
                enum_list.append([val])
    
    for l in enum_list:
        printStr = makeValidIndentifier(l[0]) + " = " + '['
        for j in l:
            printStr = printStr + '"' + str(j) + '"' + ", "
        printStr = printStr[0:len(printStr)-2]
        print(printStr + "]")

#split method for str but allows for a list of seperaters
#can use a package but too lazy to pip install (regex package)
def split(string, split_list = []):
    for x in split_list:
        string = string.replace(x, "_")
    return string.split("_")

#makes the enum name a valid identifier
def makeValidIndentifier(id):
    id = str(id).replace("/","_")
    id = str(id).replace(" ","_")
    id = str(id).replace("-","_")
    #convert first digit to word
    #num2word package exists but too lazy to pip install
    if(id[0].isdigit()):
        firstChar = id[0]
        id = id[1:len(id)]
        if firstChar == "1":
            id = "one" + id
        elif firstChar == "2":
            id = "two" + id
        elif firstChar == "3":
            id = "three" + id
        elif firstChar == "4":
            id = "four" + id
        elif firstChar == "5":
            id = "five" + id
        elif firstChar == "6":
            id = "six" + id
        elif firstChar == "7":
            id = "seven" + id
        elif firstChar == "8":
            id = "eight" + id
        elif firstChar == "9":
            id = "nine" + id
        elif firstChar == "0":
            id = "zero" + id
    return id
#if you want a enum not in list form
#def make_enum_exclusive(database, column):
#    if (column not in database.columns):
#        print("column " + column + " does not exist")
#        return
#    print("class " + column.lower() + "(Enum):")
#    #get data
#    unique_values = pd.DataFrame(columns=[column],data=database[column].drop_duplicates())
#    unique_values = unique_values[column]
#    for val in unique_values:
#        print(formatIdentifier(val) + ' = "' + val + '"')

#flags are defined as enums
#sort flags by type?
def filterCars(database, flags_list = []):
    for x in flags_list:
        if isinstance(x, drive_train):
            database = database.loc[database['DRIVE_TRAIN'] == x._value_]
        elif isinstance(x, vehicle_type):
            database = database.loc[database['VEHICLE_TYPE'] == x._value_]
        elif isinstance(x, num_of_seating):
            database = database[database['NUM_OF_SEATING'].isin(x._value_)]
        elif isinstance(x, overall_stars):
            database = database.loc[database['OVERALL_STARS'] == x._value_]
    return database

#execute the following lines:

df = pd.read_csv("backend\\data\\nhtsa_prepared.csv", dtype = str)
#test_flags = [overall_stars.five, num_of_seating.four]
#print(filterCars(df,test_flags))
make_enum(df, "DRIVE_TRAIN")

#'MAKE'
#'MODEL'            no go, too many variables
#'MODEL_YR'
#'VEHICLE_TYPE'
#'DRIVE_TRAIN'
#'NUM_OF_SEATING'   no go, format is cursed, will fix later?
#'OVERALL_STARS'