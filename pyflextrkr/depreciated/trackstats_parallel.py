# Purpose: This gets statistics about each track from the satellite data.

# Author: Orginial IDL version written by Sally A. McFarline (sally.mcfarlane@pnnl.gov) and modified for Zhe Feng (zhe.feng@pnnl.gov). Python version written by Hannah C. Barnes (hannah.barnes@pnnl.gov)

# Define function that calculates track statistics for satellite data
def trackstats_tb(
    datasource,
    datadescription,
    pixel_radius,
    geolimits,
    areathresh,
    cloudtb_threshs,
    absolutetb_threshs,
    startdate,
    enddate,
    timegap,
    cloudid_filebase,
    tracking_inpath,
    stats_path,
    track_version,
    tracknumbers_version,
    tracknumbers_filebase,
    nprocesses,
    lengthrange=[2, 120],
):
    # Inputs:
    # datasource - source of the data
    # datadescription - description of data source, included in all output file names
    # pixel_radius - radius of pixels in km
    # latlon_file - filename of the file that contains the latitude and longitude data
    # geolimits - 4-element array with plotting boundaries [lat_min, lon_min, lat_max, lon_max]
    # areathresh - minimum core + cold anvil area of a tracked cloud
    # cloudtb_threshs - brightness temperature thresholds for convective classification
    # absolutetb_threshs - brightness temperature thresholds defining the valid data range
    # startdate - starting date and time of the data
    # enddate - ending date and time of the data
    # cloudid_filebase - header of the cloudid data files
    # tracking_inpath - location of the cloudid and single track data
    # stats_path - location of the track data. also the location where the data from this code will be saved
    # track_version - Version of track single cloud files
    # tracknumbers_version - Verison of the complete track files
    # tracknumbers_filebase - header of the tracking matrix generated in the previous code.
    # cloudid_filebase -
    # lengthrange - Optional. Set this keyword to a vector [minlength,maxlength] to specify the lifetime range for the tracks.Fdef

    # Outputs: (One netcdf file with with each track represented as a row):
    # lifetime - duration of each track
    # basetime - seconds since 1970-01-01 for each cloud in a track
    # cloudidfiles - cloudid filename associated with each cloud in a track
    # meanlat - mean latitude of each cloud in a track of the core and cold anvil
    # meanlon - mean longitude of each cloud in a track of the core and cold anvil
    # minlat - minimum latitude of each cloud in a track of the core and cold anvil
    # minlon - minimum longitude of each cloud in a track of the core and cold anvil
    # maxlat - maximum latitude of each cloud in a track of the core and cold anvil
    # maxlon - maximum longitude of each cloud in a track of the core and cold anvil
    # radius - equivalent radius of each cloud in a track of the core and cold anvil
    # radius_warmanvil - equivalent radius of core, cold anvil, and warm anvil
    # npix - number of pixels in the core and cold anvil
    # nconv - number of pixels in the core
    # ncoldanvil - number of pixels in the cold anvil
    # nwarmanvil - number of pixels in the warm anvil
    # cloudnumber - number that corresponds to this cloud in the cloudid file
    # status - flag indicating how a cloud evolves over time
    # startstatus - flag indicating how this track started
    # endstatus - flag indicating how this track ends
    # mergenumbers - number indicating which track this cloud merges into
    # splitnumbers - number indicating which track this cloud split from
    # trackinterruptions - flag indicating if this track has incomplete data
    # boundary - flag indicating whether the track intersects the edge of the data
    # mintb - minimum brightness temperature of the core and cold anvil
    # meantb - mean brightness temperature of the core and cold anvil
    # meantb_conv - mean brightness temperature of the core
    # histtb - histogram of the brightness temperatures in the core and cold anvil
    # majoraxis - length of the major axis of the core and cold anvil
    # orientation - angular position of the core and cold anvil
    # eccentricity - eccentricity of the core and cold anvil
    # perimeter - approximate size of the perimeter in the core and cold anvil
    # xcenter - x-coordinate of the geometric center
    # ycenter - y-coordinate of the geometric center
    # xcenter_weighted - x-coordinate of the brightness temperature weighted center
    # ycenter_weighted - y-coordinate of the brightness temperature weighted center

    ###################################################################################
    # Initialize modules
    import numpy as np
    from netCDF4 import Dataset, chartostring
    import os
    import time
    import gc
    from multiprocessing import Pool
    from pyflextrkr.trackstats_single import calc_stats_single
    from pyflextrkr import netcdf_io_trackstats as net
    import logging

    logger = logging.getLogger(__name__)

    np.set_printoptions(threshold=np.inf)

    #############################################################################
    # Set constants

    # Isolate core and cold anvil brightness temperature thresholds
    thresh_core = cloudtb_threshs[0]
    thresh_cold = cloudtb_threshs[1]

    # Set output filename
    trackstats_outfile = (
        stats_path
        + "stats_"
        + tracknumbers_filebase
        + "_"
        + startdate
        + "_"
        + enddate
        + ".nc"
    )

    ###################################################################################
    # # Load latitude and longitude grid. These were created in subroutine_idclouds and is saved in each file.
    # logger.info('Determining which files will be processed')
    # logger.info((time.ctime()))

    # # Find filenames of idcloud files
    # temp_cloudidfiles = fnmatch.filter(os.listdir(tracking_inpath), cloudid_filebase +'*')
    # cloudidfiles_list = temp_cloudidfiles  # KB ADDED

    # # Sort the files by date and time   # KB added
    # def fdatetime(x):
    #     return(x[-11:])
    # cloudidfiles_list = sorted(cloudidfiles_list, key = fdatetime)

    # # Select one file. Any file is fine since they all have the map of latitude and longitude saved.
    # temp_cloudidfiles = temp_cloudidfiles[0]

    # # Load latitude and longitude grid
    # latlondata = Dataset(tracking_inpath + temp_cloudidfiles, 'r')
    # longitude = latlondata.variables['longitude'][:]
    # latitude = latlondata.variables['latitude'][:]
    # latlondata.close()

    #############################################################################
    # Load track data
    logger.info("Loading gettracks data")
    logger.info((time.ctime()))
    cloudtrack_file = (
        stats_path + tracknumbers_filebase + "_" + startdate + "_" + enddate + ".nc"
    )

    cloudtrackdata = Dataset(cloudtrack_file, "r")
    numtracks = cloudtrackdata["ntracks"][:]
    cloudidfiles = cloudtrackdata["cloudid_files"][:]
    nfiles = cloudtrackdata.dimensions["nfiles"].size
    tracknumbers = cloudtrackdata["track_numbers"][:]
    trackreset = cloudtrackdata["track_reset"][:]
    tracksplit = cloudtrackdata["track_splitnumbers"][:]
    trackmerge = cloudtrackdata["track_mergenumbers"][:]
    trackstatus = cloudtrackdata["track_status"][:]
    cloudtrackdata.close()

    # Convert filenames and timegap to string
    # numcharfilename = len(list(cloudidfiles_list[0]))
    tmpfname = "".join(chartostring(cloudidfiles[0]))
    numcharfilename = len(list(tmpfname))

    # Load latitude and longitude grid from any cloudidfile since they all have the map of latitude and longitude saved
    latlondata = Dataset(tracking_inpath + tmpfname, "r")
    longitude = latlondata.variables["longitude"][:]
    latitude = latlondata.variables["latitude"][:]
    latlondata.close()

    # Determine dimensions of data
    # nfiles = len(cloudidfiles_list)
    ny, nx = np.shape(latitude)

    ############################################################################
    # Initialize grids
    logger.info("Initiailizinng matrices")
    logger.info((time.ctime()))

    nmaxclouds = max(lengthrange)

    mintb_thresh = absolutetb_threshs[0]
    maxtb_thresh = absolutetb_threshs[1]
    tbinterval = 2
    tbbins = np.arange(mintb_thresh, maxtb_thresh + tbinterval, tbinterval)
    nbintb = len(tbbins)

    finaltrack_tracklength = np.zeros(int(numtracks), dtype=np.int32)
    finaltrack_corecold_boundary = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=np.int32) * -9999
    )
    # finaltrack_corecold_boundary = np.zeros((int(numtracks), int(nmaxclouds)), dtype=np.int32) # kb playing with field
    # finaltrack_basetime = np.empty((int(numtracks),int(nmaxclouds)), dtype='datetime64[s]')
    finaltrack_basetime = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * np.nan
    )
    finaltrack_corecold_mintb = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * np.nan
    )
    finaltrack_corecold_meantb = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * np.nan
    )
    finaltrack_core_meantb = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * np.nan
    )
    # finaltrack_corecold_histtb = np.zeros((int(numtracks),int(nmaxclouds), nbintb-1))
    finaltrack_corecold_radius = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * np.nan
    )
    finaltrack_corecoldwarm_radius = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * np.nan
    )
    finaltrack_corecold_meanlat = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * np.nan
    )
    finaltrack_corecold_meanlon = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * np.nan
    )
    finaltrack_corecold_maxlon = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * np.nan
    )
    finaltrack_corecold_maxlat = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * np.nan
    )
    finaltrack_ncorecoldpix = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=np.int32) * -9999
    )
    finaltrack_corecold_minlon = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * np.nan
    )
    finaltrack_corecold_minlat = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * np.nan
    )
    finaltrack_ncorepix = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=np.int32) * -9999
    )
    finaltrack_ncoldpix = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=np.int32) * -9999
    )
    finaltrack_nwarmpix = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=np.int32) * -9999
    )
    finaltrack_corecold_status = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=np.int32) * -9999
    )
    finaltrack_corecold_trackinterruptions = (
        np.ones(int(numtracks), dtype=np.int32) * -9999
    )
    finaltrack_corecold_mergenumber = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=np.int32) * -9999
    )
    finaltrack_corecold_splitnumber = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=np.int32) * -9999
    )
    finaltrack_corecold_cloudnumber = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=np.int32) * -9999
    )
    finaltrack_datetimestring = [
        [["" for x in range(13)] for y in range(int(nmaxclouds))]
        for z in range(int(numtracks))
    ]
    finaltrack_cloudidfile = np.chararray(
        (int(numtracks), int(nmaxclouds), int(numcharfilename))
    )
    finaltrack_corecold_majoraxis = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * np.nan
    )
    finaltrack_corecold_orientation = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * np.nan
    )
    finaltrack_corecold_eccentricity = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * np.nan
    )
    finaltrack_corecold_perimeter = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * np.nan
    )
    finaltrack_corecold_xcenter = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * -9999
    )
    finaltrack_corecold_ycenter = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * -9999
    )
    finaltrack_corecold_xweightedcenter = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * -9999
    )
    finaltrack_corecold_yweightedcenter = (
        np.ones((int(numtracks), int(nmaxclouds)), dtype=float) * -9999
    )

    #########################################################################################
    # loop over files. Calculate statistics and organize matrices by tracknumber and cloud
    logger.info("Looping over files and calculating statistics for each file")
    logger.info((time.ctime()))
    # parallel here, by Jianfeng Li

    with Pool(nprocesses) as pool:
        Results = pool.starmap(
            calc_stats_single,
            [
                (
                    tracknumbers[0, nf, :],
                    cloudidfiles[nf],
                    tracking_inpath,
                    cloudid_filebase,
                    nbintb,
                    numcharfilename,
                    latitude,
                    longitude,
                    geolimits,
                    nx,
                    ny,
                    mintb_thresh,
                    maxtb_thresh,
                    tbbins,
                    pixel_radius,
                    trackstatus[0, nf, :],
                    trackmerge[0, nf, :],
                    tracksplit[0, nf, :],
                    trackreset[0, nf, :],
                )
                for nf in range(0, nfiles)
            ],
        )
        pool.close()
    # for nf in range(0,nfiles):
    #     Results = calc_stats_single(tracknumbers[0, nf, :],cloudidfiles[nf],tracking_inpath,cloudid_filebase,nbintb, \
    #             numcharfilename, latitude, longitude, geolimits, nx, ny, mintb_thresh, maxtb_thresh, tbbins, pixel_radius, trackstatus[0, nf, :], \
    #             trackmerge[0, nf, :], tracksplit[0, nf, :], trackreset[0, nf, :])
    # import pdb; pdb.set_trace()

    # collect pool results
    for nf in range(0, nfiles):
        tmp = Results[nf]
        if tmp is not None:
            tracknumbertmp = tmp[0] - 1
            numtrackstmp = tmp[1]
            finaltrack_tracklength[tracknumbertmp] = (
                finaltrack_tracklength[tracknumbertmp] + 1
            )
            for iitrack in range(numtrackstmp):
                if finaltrack_tracklength[tracknumbertmp[iitrack]] <= nmaxclouds:
                    finaltrack_basetime[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[2][iitrack]
                    finaltrack_corecold_cloudnumber[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[3][iitrack]
                    finaltrack_cloudidfile[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                        :,
                    ] = tmp[4][iitrack, :]
                    finaltrack_datetimestring[tracknumbertmp[iitrack]][
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1
                    ][:] = tmp[5][iitrack][:]
                    finaltrack_corecold_meanlat[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[6][iitrack]
                    finaltrack_corecold_meanlon[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[7][iitrack]
                    finaltrack_corecold_minlat[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[8][iitrack]
                    finaltrack_corecold_minlon[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[9][iitrack]
                    finaltrack_corecold_maxlat[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[10][iitrack]
                    finaltrack_corecold_maxlon[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[11][iitrack]
                    finaltrack_corecold_boundary[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[12][iitrack]
                    finaltrack_ncorecoldpix[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[13][iitrack]
                    finaltrack_ncorepix[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[14][iitrack]
                    finaltrack_ncoldpix[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[15][iitrack]
                    finaltrack_nwarmpix[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[16][iitrack]
                    finaltrack_corecold_eccentricity[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[17][iitrack]
                    finaltrack_corecold_majoraxis[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[18][iitrack]
                    finaltrack_corecold_orientation[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[19][iitrack]
                    finaltrack_corecold_perimeter[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[20][iitrack]
                    finaltrack_corecold_ycenter[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[21][iitrack]
                    finaltrack_corecold_xcenter[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[22][iitrack]
                    finaltrack_corecold_yweightedcenter[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[23][iitrack]
                    finaltrack_corecold_xweightedcenter[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[24][iitrack]
                    finaltrack_corecold_radius[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[25][iitrack]
                    finaltrack_corecoldwarm_radius[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[26][iitrack]
                    finaltrack_corecold_mintb[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[27][iitrack]
                    finaltrack_corecold_meantb[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[28][iitrack]
                    # finaltrack_corecold_histtb[tracknumbertmp[iitrack],finaltrack_tracklength[tracknumbertmp[iitrack]]-1] = tmp[29][iitrack]
                    finaltrack_corecold_status[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[29][iitrack]
                    finaltrack_corecold_mergenumber[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[30][iitrack]
                    finaltrack_corecold_splitnumber[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[31][iitrack]
                    finaltrack_corecold_trackinterruptions[
                        tracknumbertmp[iitrack]
                    ] = tmp[32][iitrack]
                    finaltrack_core_meantb[
                        tracknumbertmp[iitrack],
                        finaltrack_tracklength[tracknumbertmp[iitrack]] - 1,
                    ] = tmp[33][iitrack]
                    basetime_units = tmp[34]
                    # basetime_calendar = tmp[36]

    ###############################################################
    ## Remove tracks that have no cells. These tracks are short.
    logger.info("Removing tracks with no cells")
    logger.info((time.ctime()))
    gc.collect()

    # logger.info('finaltrack_tracklength shape at line 385: ', finaltrack_tracklength.shape)
    # logger.info('finaltrack_tracklength(4771): ', finaltrack_tracklength[4770])
    cloudindexpresent = np.array(np.where(finaltrack_tracklength != 0))[0, :]
    numtracks = len(cloudindexpresent)
    # logger.info('length of cloudindex present: ', len(cloudindexpresent))

    # maxtracklength = np.nanmax(finaltrack_tracklength)
    maxtracklength = nmaxclouds
    # logger.info('maxtracklength: ', maxtracklength)

    finaltrack_tracklength = finaltrack_tracklength[cloudindexpresent]
    finaltrack_corecold_boundary = finaltrack_corecold_boundary[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_basetime = finaltrack_basetime[cloudindexpresent, 0:maxtracklength]
    finaltrack_corecold_mintb = finaltrack_corecold_mintb[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_corecold_meantb = finaltrack_corecold_meantb[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_core_meantb = finaltrack_core_meantb[cloudindexpresent, 0:maxtracklength]
    # finaltrack_corecold_histtb = finaltrack_corecold_histtb[cloudindexpresent, 0:maxtracklength, :]
    finaltrack_corecold_radius = finaltrack_corecold_radius[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_corecoldwarm_radius = finaltrack_corecoldwarm_radius[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_corecold_meanlat = finaltrack_corecold_meanlat[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_corecold_meanlon = finaltrack_corecold_meanlon[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_corecold_maxlon = finaltrack_corecold_maxlon[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_corecold_maxlat = finaltrack_corecold_maxlat[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_corecold_minlon = finaltrack_corecold_minlon[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_corecold_minlat = finaltrack_corecold_minlat[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_ncorecoldpix = finaltrack_ncorecoldpix[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_ncorepix = finaltrack_ncorepix[cloudindexpresent, 0:maxtracklength]
    finaltrack_ncoldpix = finaltrack_ncoldpix[cloudindexpresent, 0:maxtracklength]
    finaltrack_nwarmpix = finaltrack_nwarmpix[cloudindexpresent, 0:maxtracklength]
    finaltrack_corecold_status = finaltrack_corecold_status[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_corecold_trackinterruptions = finaltrack_corecold_trackinterruptions[
        cloudindexpresent
    ]
    finaltrack_corecold_mergenumber = finaltrack_corecold_mergenumber[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_corecold_splitnumber = finaltrack_corecold_splitnumber[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_corecold_cloudnumber = finaltrack_corecold_cloudnumber[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_datetimestring = list(
        finaltrack_datetimestring[i][0:maxtracklength][:] for i in cloudindexpresent
    )
    finaltrack_cloudidfile = finaltrack_cloudidfile[
        cloudindexpresent, 0:maxtracklength, :
    ]
    finaltrack_corecold_majoraxis = finaltrack_corecold_majoraxis[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_corecold_orientation = finaltrack_corecold_orientation[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_corecold_eccentricity = finaltrack_corecold_eccentricity[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_corecold_perimeter = finaltrack_corecold_perimeter[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_corecold_xcenter = finaltrack_corecold_xcenter[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_corecold_ycenter = finaltrack_corecold_ycenter[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_corecold_xweightedcenter = finaltrack_corecold_xweightedcenter[
        cloudindexpresent, 0:maxtracklength
    ]
    finaltrack_corecold_yweightedcenter = finaltrack_corecold_yweightedcenter[
        cloudindexpresent, 0:maxtracklength
    ]

    gc.collect()

    ########################################################
    # Correct merger and split cloud numbers

    # Initialize adjusted matrices
    adjusted_finaltrack_corecold_mergenumber = (
        np.ones(np.shape(finaltrack_corecold_mergenumber)) * -9999
    )
    adjusted_finaltrack_corecold_splitnumber = (
        np.ones(np.shape(finaltrack_corecold_mergenumber)) * -9999
    )
    logger.info(("total tracks: " + str(numtracks)))
    logger.info("Correcting mergers and splits")
    logger.info((time.ctime()))

    # Create adjustor
    indexcloudnumber = np.copy(cloudindexpresent) + 1
    adjustor = np.arange(0, np.max(cloudindexpresent) + 2)
    for it in range(0, numtracks):
        adjustor[indexcloudnumber[it]] = it + 1
    adjustor = np.append(adjustor, -9999)

    # Adjust mergers
    temp_finaltrack_corecold_mergenumber = finaltrack_corecold_mergenumber.astype(
        int
    ).ravel()
    temp_finaltrack_corecold_mergenumber[
        temp_finaltrack_corecold_mergenumber == -9999
    ] = (np.max(cloudindexpresent) + 2)
    adjusted_finaltrack_corecold_mergenumber = adjustor[
        temp_finaltrack_corecold_mergenumber
    ]
    adjusted_finaltrack_corecold_mergenumber = np.reshape(
        adjusted_finaltrack_corecold_mergenumber,
        np.shape(finaltrack_corecold_mergenumber),
    )

    # Adjust splitters
    temp_finaltrack_corecold_splitnumber = finaltrack_corecold_splitnumber.astype(
        int
    ).ravel()
    temp_finaltrack_corecold_splitnumber[
        temp_finaltrack_corecold_splitnumber == -9999
    ] = (np.max(cloudindexpresent) + 2)
    adjusted_finaltrack_corecold_splitnumber = adjustor[
        temp_finaltrack_corecold_splitnumber
    ]
    adjusted_finaltrack_corecold_splitnumber = np.reshape(
        adjusted_finaltrack_corecold_splitnumber,
        np.shape(finaltrack_corecold_splitnumber),
    )

    #########################################################################
    # Record starting and ending status
    logger.info("Determine starting and ending status")
    logger.info((time.ctime()))

    # Starting status
    finaltrack_corecold_startstatus = finaltrack_corecold_status[:, 0]

    # Ending status
    finaltrack_corecold_endstatus = (
        np.ones(len(finaltrack_corecold_startstatus)) * -9999
    )
    for trackstep in range(0, numtracks):
        if finaltrack_tracklength[trackstep] > 0:
            finaltrack_corecold_endstatus[trackstep] = finaltrack_corecold_status[
                trackstep, finaltrack_tracklength[trackstep] - 1
            ]

    #######################################################################
    # Write to netcdf
    logger.info("Writing trackstat netcdf")
    logger.info((time.ctime()))
    logger.info(trackstats_outfile)
    logger.info("")

    # Check if file already exists. If exists, delete
    if os.path.isfile(trackstats_outfile):
        os.remove(trackstats_outfile)

    net.write_trackstats_tb(
        trackstats_outfile,
        numtracks,
        maxtracklength,
        nbintb,
        numcharfilename,
        datasource,
        datadescription,
        startdate,
        enddate,
        track_version,
        tracknumbers_version,
        timegap,
        thresh_core,
        thresh_cold,
        pixel_radius,
        geolimits,
        areathresh,
        mintb_thresh,
        maxtb_thresh,
        basetime_units,  # basetime_units, basetime_calendar, \
        finaltrack_tracklength,
        finaltrack_basetime,
        finaltrack_cloudidfile,
        finaltrack_datetimestring,
        finaltrack_corecold_meanlat,
        finaltrack_corecold_meanlon,
        finaltrack_corecold_minlat,
        finaltrack_corecold_minlon,
        finaltrack_corecold_maxlat,
        finaltrack_corecold_maxlon,
        finaltrack_corecold_radius,
        finaltrack_corecoldwarm_radius,
        finaltrack_ncorecoldpix,
        finaltrack_ncorepix,
        finaltrack_ncoldpix,
        finaltrack_nwarmpix,
        finaltrack_corecold_cloudnumber,
        finaltrack_corecold_status,
        finaltrack_corecold_startstatus,
        finaltrack_corecold_endstatus,
        adjusted_finaltrack_corecold_mergenumber,
        adjusted_finaltrack_corecold_splitnumber,
        finaltrack_corecold_trackinterruptions,
        finaltrack_corecold_boundary,
        finaltrack_corecold_mintb,
        finaltrack_corecold_meantb,
        finaltrack_core_meantb,  # finaltrack_corecold_mintb, finaltrack_corecold_meantb, finaltrack_core_meantb, finaltrack_corecold_histtb, \
        finaltrack_corecold_majoraxis,
        finaltrack_corecold_orientation,
        finaltrack_corecold_eccentricity,
        finaltrack_corecold_perimeter,
        finaltrack_corecold_xcenter,
        finaltrack_corecold_ycenter,
        finaltrack_corecold_xweightedcenter,
        finaltrack_corecold_yweightedcenter,
    )
