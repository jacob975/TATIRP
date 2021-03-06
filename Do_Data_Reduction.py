#!/usr/bin/python
'''
Program:
    This is a program for data reduction on tat. 
Usage: 
    Do_Data_Reduction.py
    
    The indicators I use:   
        Y: Not finished yet
        D: Done
        X: Failed
        E: Empty, no data

Editor:
    Jacob975
20170625
#################################
update log
20180625 version alpha 1:
    1. the code works
20180727 version alpha 2:
    1. Update processed list in each loop.
20190618 version alpha 3:
    1. I update the indicator of the reduction status.
'''
import numpy as np
import time
import glob
import TAT_env
import os
import re
import warnings
import mysqlio_lib
import undo_tat_reduction
from joblib import Parallel, delayed
import subprocess

def data_reduction(site):
    #----------------------------------------------
    # Load where we save data and calibration files 
    path_of_raw_data = "{0}/{1}/image".format(TAT_env.path_of_image, site)
    path_of_raw_calibrate = "{0}/{1}/calibrate".format(TAT_env.path_of_image, site)
    #----------------------------------------------
    # Pick the files which are not processed yet
    unproced_cal_list= unproced_check(  path_of_raw_calibrate, 
                                        table_name = TAT_env.ctn_tb_name)
    # Do reduction on calibration 
    failure = check_cal(unproced_cal_list, 
                        undo = False)
    #----------------------------------------------
    # Pick the files which are not processed yet
    unproced_data_list= unproced_check( path_of_raw_data, 
                                        table_name = TAT_env.ctn_tb_name)
    # Do reduction on data
    failure = image_reduction(  unproced_data_list, 
                                undo = False)
    return failure

# The def for checking which date is not processed.
def unproced_check(path_of_raw_data, table_name):
    print ("Check unprocessed files.")
    # Initialized
    unprocessed = []
    processed = []
    #-------------------------------------
    # Load processed log data list
    # Create the database for saving informations.
    mysqlio_lib.create_TAT_tables()
    cnx = mysqlio_lib.TAT_auth()
    cursor = cnx.cursor()
    # Load data from table

    #cursor.execute('select `NAME` from TAT.{0} where `STATUS` = "D" or `STATUS` = "X"'.format(table_name))
    cursor.execute('select `NAME` from TAT.{0} where `STATUS` = "D"'.format(table_name))
    
    processed = np.array(cursor.fetchall(), dtype = str).flatten()
    cursor.close()
    cnx.close()
    #-------------------------------------
    # It takes the name of the data, and then matches with the list of processed data. 
    candidates = glob.glob("{0}/20*".format(path_of_raw_data))
    for cand in candidates:
        # Take the short (base) name
        base_cand = re.sub(TAT_env.path_of_image, '', cand)
        temp = np.where(processed == base_cand)
        # Not found
        if len(temp[0]) == 0:
            unprocessed.append(base_cand)
    unprocessed = np.array(unprocessed, dtype = str)
    return unprocessed

# The def for flattening files in a folder.
def undo_reduction(unpro):
    os.chdir(unpro)
    undo_tat_reduction.undo_tat_reduction()
    os.system('cd')
    return

# The def for check header and quality of images in calibration.
def check_cal(unproced_cal_list, undo = False):
    # check if input list is empty
    if len(unproced_cal_list) == 0:
        print "No unprocessed calibrate, check_cal stop"
        return 0
    #------------------------------
    # Do parallel
    Parallel(   n_jobs=20)(
                delayed(check_cal_single)(unpro_cal, undo) for unpro_cal in unproced_cal_list)
    return 0

def check_cal_single(unpro_cal, undo = False):
    #-------------------------------------
    # Create a row for this container into table `container`
    mysqlio_lib.update2sql_container(   unpro_cal, 
                                        stat = 'Y', 
                                        comment = 'Not finished yet, '
                                    )
    # Get the fullname of that folder
    fullpath_unpro_raw_cal = '{0}{1}'.format(  TAT_env.path_of_image,
                                                unpro_cal)
    fullpath_unpro_cal = '{0}{1}'.format(  TAT_env.path_of_data, 
                                            unpro_cal)
    # Make a directory before cleaning
    os.system('mkdir -p {0}'.format(fullpath_unpro_cal))
    # Undo everything before reduction
    if undo:
        undo_reduction(fullpath_unpro_cal)
    # Move good calibrator to the destination
    #----------------------------------------
    # Check the quality of images.
    band_list = TAT_env.band_list
    accumulated_exptime_list = []
    print "Checking DIR: {0}".format(fullpath_unpro_cal)
    os.chdir(fullpath_unpro_raw_cal)
    # Determine exptime
    image_list = glob.glob("{0}/*.fit".format(fullpath_unpro_raw_cal))
    for name_image in image_list:
        sub_name_1 = name_image.split('x')
        sub_name_2 = sub_name_1[1].split('.fit')
        accumulated_exptime_list.append(sub_name_2[0])
    exptime_list = list(set(accumulated_exptime_list))
    # Dark process
    for exptime in exptime_list:
        os.system(  "{0}/check_image.py dark 0 {1} &> /dev/null".format(
                    TAT_env.path_of_code, 
                    exptime))
    # Flat process
    for band in band_list:
        for exptime in exptime_list:
            os.system(  "{0}/check_image.py flat {1} {2} &> /dev/null".format(
                        TAT_env.path_of_code, 
                        band, 
                        exptime))
    #-------------------------------------
    # Save comments and logs into table `container`(epoch)
    mysqlio_lib.update2sql_container(   unpro_cal, 
                                        'D', 
                                        'Calibrations')
    return 0

def im_red_subsub(  fullpath_unpro_data, 
                    unpro_data, 
                    target, 
                    band_exptime):
    # Move to working directory
    subsub_directory =  '{0}/{1}/{2}'.format(
                        fullpath_unpro_data, 
                        target, 
                        band_exptime)
    #--------------------------------------------------------------------------
    # check if dark were found. If no, find one.
    os.chdir(subsub_directory)
    try:
        name_dark = glob.glob("Median_dark_*.fits")[0]
    except:
        exit_status = subprocess.call(  "{0}/find_dark.py  &> /dev/null".format(
        #exit_status = subprocess.call(  "{0}/find_dark.py".format(
                                        TAT_env.path_of_code),
                                        shell = True
                                        )
        if exit_status != 0:
            mysqlio_lib.update2sql_container(unpro_data, 
                                            'Y', 
                                            '{0}/{1} dark not found, '.format(target, band_exptime),
                                            append = True,
                                            )
            return 1
    #--------------------------------------------------------------------------
    # check if flat were found. If no, find one.
    try:
        name_flat = glob.glob("Median_flat_*.fits")[0]
    except:
        exit_status = subprocess.call(  "{0}/find_flat.py  &> /dev/null".format(
        #exit_status = subprocess.call(  "{0}/find_flat.py".format(
                                        TAT_env.path_of_code),
                                        shell=True
                                        )
        if exit_status != 0:
            mysqlio_lib.update2sql_container(unpro_data, 
                                            'Y', 
                                            '{0}/{1} flat not found, '.format(target, band_exptime),
                                            append = True,
                                            )
            return 1
    #--------------------------------------------------------------------------
    # Subtracted by dark and divided by flat
    exit_status = subprocess.call(  "{0}/sub_div.py  &> /dev/null".format(
    #exit_status = subprocess.call(  "{0}/sub_div.py".format(
                                    TAT_env.path_of_code),
                                    shell = True
                                    )
    if exit_status != 0:
        mysqlio_lib.update2sql_container(unpro_data, 
                                        'Y', 
                                        '{0}/{1} sub_div.py failed, '.format(target, band_exptime),
                                        append = True,
                                        )
        return 2
    #--------------------------------------------------------------------------
    # Mask the bad pixels 
    exit_status = subprocess.call(  "{0}/mask_images.py reducted_image_list.txt  &> /dev/null".format(
    #exit_status = subprocess.call(  "{0}/mask_images.py reducted_image_list.txt".format(
                                    TAT_env.path_of_code), 
                                    shell = True
                                    )
    if exit_status != 0:
        mysqlio_lib.update2sql_container(unpro_data,
                                        'Y',
                                        '{0}/{1} mask_images.py failed, '.format(target, band_exptime),
                                        append = True,
                                        )
        return 2
    #--------------------------------------------------------------------------
    # PSF register
    # try to load registed_image_list, which is produced by register.py
    exit_status = subprocess.call(  "{0}/register_SE.py masked_image_list.txt &> /dev/null".format(
    #exit_status = subprocess.call(  "{0}/register_SE.py masked_image_list.txt".format(
                                    TAT_env.path_of_code),
                                    shell = True
                                    )
    if exit_status != 0:
        mysqlio_lib.update2sql_container(unpro_data,
                                        'Y',
                                        '{0}/{1} register_SE.py failed, '.format(target, band_exptime),
                                        append = True,
                                        )
        return 2
    #--------------------------------------------------------------------------
    # Get WCS 
    exit_status = subprocess.call(  "{0}/wcsfinder.py registed_image_list.txt &> /dev/null".format(
    #exit_status = subprocess.call(  "{0}/wcsfinder.py registed_image_list.txt".format(
                                    TAT_env.path_of_code),
                                    shell = True
                                    )
    if exit_status != 0:
        mysqlio_lib.update2sql_container(unpro_data,
                                        'Y',
                                        '{0}/{1} wcsfinder.py failed, '.format(target, band_exptime),
                                        append = True,
                                        )
        return 2

    #--------------------------------------------------------------------------
    # Find targets on images
    # Update to database.
    exit_status = subprocess.call(  "{0}/starfinder.py registed_image_list.txt &> /dev/null".format(
    #exit_status = subprocess.call(  "{0}/starfinder.py registed_image_list.txt".format(
                                    TAT_env.path_of_code),
                                    shell = True
                                    )
    if exit_status != 0:
        mysqlio_lib.update2sql_container(unpro_data,
                                        'Y',
                                        '{0}/{1} starfinder.py failed, '.format(target, band_exptime),
                                        append = True,
                                        )
        return 2
    # After the data pass all reduction process, return 0 to tell the parents. 
    return 0
    #--------------------------------------------------------------------------
    # Do more CATA photometry.
    os.system("{0}/photometry.py CATA {0} {1}".format(start_date, end_date))
    #--------------------------------------------------------------------------
    # Save results into path of result.
    os.system("rename _subDARK_divFLAT_m.fits _reduce.fits *.fits")
    #--------------------------------------------------------------------------
    return 0

def im_red_sub(unpro_data, undo = False):
    mysqlio_lib.update2sql_container(   unpro_data, 
                                        stat = 'Y', 
                                        comment = 'Not finished yet, ')
    
    # Get the fullname of that folder
    fullpath_unpro_raw_data = '{0}{1}'.format( TAT_env.path_of_image, 
                                                unpro_data)
    fullpath_unpro_data = '{0}{1}'.format(  TAT_env.path_of_data, 
                                            unpro_data)
    
    # Make directory before cleaning
    os.system('mkdir -p {0}'.format(fullpath_unpro_data))
    # Undo everything before reduction
    if undo:
        undo_reduction(fullpath_unpro_data)
    #-----------------------------
    # For each container
    print "Reducing DIR: {0}".format(fullpath_unpro_data)
    # Move to the raw data
    os.chdir(fullpath_unpro_raw_data)
    # Check the quality of the images.
    for band in TAT_env.band_list:
        os.system(  "{0}/check_image.py data {1} 0 &> /dev/null".format(
        #os.system(  "{0}/check_image.py data {1} 0".format(
                    TAT_env.path_of_code, 
                    band))
    # Move to the reduction
    os.chdir(fullpath_unpro_data)
    # Confirm whether is any image in there.
    image_list = glob.glob('./*.fit')
    num_image = len(image_list)
    if num_image == 0:
        mysqlio_lib.update2sql_container(   unpro_data, 
                                            'E', 
                                            'No data',
                                            )
        return 3
    # Arrange
    os.system(  "{0}/arrange_images.py &> /dev/null".format(
                TAT_env.path_of_code))
    target_list = [d for d in os.listdir(os.getcwd()) if os.path.isdir(d)] 
    cwd = os.getcwd()
    exit_status_list = []
    for target in target_list:
        # Move to the reduction with specific band and exptime.
        os.chdir('{0}/{1}'.format(fullpath_unpro_data, target))
        band_exptime_list = [d for d in os.listdir(os.getcwd()) if os.path.isdir(d)]
        for band_exptime in band_exptime_list:
            exit_status = im_red_subsub(fullpath_unpro_data, 
                                        unpro_data,
                                        target, 
                                        band_exptime)
            exit_status_list.append(exit_status)
    #-------------------------------------
    # Say done if all file are processed 
    if 0 in exit_status_list:
        mysqlio_lib.update2sql_container(   unpro_data, 
                                            'D', 
                                            '',
                                            )
        return 0
    # If the observation is not complete, it stops and sends emails to all co-works.
    elif 1 in exit_status_list:
        mysqlio_lib.update2sql_container(   unpro_data, 
                                            'Y', 
                                            '',
                                            append = True,
                                            )
        return 1
    # If the program could not process the data, it stops and THAT'S IT.
    elif 2 in exit_status_list:
        mysqlio_lib.update2sql_container(   unpro_data, 
                                            'X', 
                                            '',
                                            append = True,
                                            )
        return 2
    # Unexpected status
    return -1

def image_reduction(unprocessed_data_list, undo = False): 
    # check if input list is empty
    if len(unprocessed_data_list) == 0:
        print "No unprocessed data, image_reduction stop"
        return 1
    # Do it parallel
    '''
    for unpro_data in unprocessed_data_list:
        failure = im_red_sub(unpro_data, undo)
    '''
    Parallel(   n_jobs=20)(
                delayed(im_red_sub)(unpro_data, undo) for unpro_data in unprocessed_data_list)
    return 0 

#--------------------------------------------
# main code
if __name__ == "__main__":
    # Measure time
    start_time = time.time()
    #----------------------------------------
    # Initialize
    warnings.filterwarnings("ignore")
    site_list = TAT_env.site_list
    #---------------------------------------
    # Data reduction
    for site in site_list:
        print "### site {0} ###".format(site)
        failure = data_reduction(site)
    #---------------------------------------
    # Measure time
    elapsed_time = time.time() - start_time
    print "Exiting Main Program, spending ", elapsed_time, "seconds."
