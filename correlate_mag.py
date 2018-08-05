#!/usr/bin/python
'''
Program:
    This is a program for correlating instrument magnitude and apparent magnitude in catalog  
Usage: 
    correlate_mag.py [table list]
Editor:
    Jacob975
20180805
#################################
update log
20180805 version alpha 1
    1. The code works
'''
import numpy as np
import time
from sys import argv
from astrometry import coordinates, units as u
from astroquery.vizier import Vizier

# Get catalog with Vizier
def get_catalog_magnitude(targets):
    RA = targets[]
    DEC = targets[]
    result = Vizier.query_region(RA, DEC,
                                 unit=('deg','deg'), frame='icrs'),
                                 width="20m",   catalog=["I/329"])[0]
    return result

#--------------------------------------------
# main code
if __name__ == "__main__":
    # Measure time
    start_time = time.time()
    #----------------------------------------
    # Load argv
    if len(argv) != 2:
        print "Wrong number of arguments"
        print "Usage: correlate_mag.py [table list]"
        exit(1)
    table_name_list_name = argv[2]
    #----------------------------------------
    # Load table and find apparent magnitude in catalogs
    table_name_list = np.loadtxt(table_name_list_name, dtype = str)
    for table_name in table_name_list:
        # Load table
        table = np.loadtxt(table_name, dtype = object)
        # The column for apparent magnitude
        apparent_mag_list = []
        for targets in table:
            result = get_catalog_magnitude(targets)
            # Need to be modified
            apparent_mag_list.append(result)
        table = np.insert(table, -1, apparent_mag_list, 1)
        # Save table
        np.savetxt("{0}_a.tbl".format(table_name[:-4]), table)
    #---------------------------------------
    # Measure time
    elapsed_time = time.time() - start_time
    print "Exiting Main Program, spending ", elapsed_time, "seconds."
