from enum import Enum

#'MAKE'
#'MODEL'
#'MODEL_YR'
#'VEHICLE_TYPE' str
#'DRIVE_TRAIN' str
#'NUM_OF_SEATING' int
#'OVERALL_STARS' int between 0 and 5 inclusive

class drive_train(Enum):
    FWD = 1
    twoWD = 2 #originally 2WD, same applies to other uses of "two" and "four"
    AWD = 3
    fourWD = 4
    RWD = 5
    ADW = 6
    fourx2 = 7
    fourx4 = 8

class vehicle_type(Enum):
    PC = 1
    MPV = 2
    PHEV = 3
    BEV = 4
    SUV = 5
    four_DR = 6 #originally "4 DR"
    TRUCK = 7
    PU_CC = 8 #originally PU/CC
    five_HB = 9 #originally "5 HB"
    BUS = 10 #all buses will be dropped from database
    MPV/BUS = 11 #see above
    VAN = 12
    SPORT_UTILITY_VEHICLE = 13 #originally space instead of _
    HEAVY_PASSENGER_CAR = 14 #above applies this all other spaces
    MEDIUM_PASSENGER_CAR = 15
    LIGHT_PASSENGER_CAR = 16
    COMPACT_PASSENGER_CAR = 17
    PICKUP = 18
    MINI_PASSENGER_CAR = 19

