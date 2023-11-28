
import pandas as pd
import numpy as np
import panel as pn

import dask.dataframe as dd
import hvplot.xarray  # noqa: API import
import hvplot.dask  # noqa: API import
import hvplot.pandas
import deimos
import logging
import colorcet as cc
import datashader as ds
from holoviews.operation.datashader import aggregate, datashade, rasterize
import os
from pathlib import Path

def exception_handler(ex):
    logging.error("Error", exc_info=ex)
    pn.state.notifications.error('Error: %s: see command line for more information' % str(ex), duration=0)

pn.extension(exception_handler=exception_handler, notifications=True)

def load_mz_h5(file_name_initial, key, columns, rt_name=None, dt_name=None, new_name = None):
        '''
        load either mz, h5 or csv file

        Parameters:
                file_name_initial (path): file path to data
                key (str): key for uploaded data, such as ms1 or ms2
                columns (list): list of the feature names to return from file
                rt_name (list): name retention time accession if using mzML file
                dt_name (list): name drift time accession if using mzML file
        Returns:
                pd DataFrame with data 
        '''
        extension = Path(file_name_initial).suffix
        if extension == ".mzML" or extension == ".gz":
                 if os.path.exists(new_name):
                        pn.state.notifications.info("Using existing h5 file: " + new_name )
                        pn.state.notifications.info("If you wish to create a new file, rename or delete " + new_name )
                        return deimos.load(new_name, key=key, columns=columns)
                 else:
                        rt_name_value = deimos.get_accessions(file_name_initial)[rt_name]
                        dt_name_value = deimos.get_accessions(file_name_initial)[dt_name]
                        pn.state.notifications.clear()
                        pn.state.notifications.info("load deimos mz using " + str({rt_name: rt_name_value, dt_name: dt_name_value}), duration=0)
                        pn.state.notifications.info("loading an mz file will take a while, will see 'done loading' when finished", duration=0)
                        pn.state.notifications.info("See https://deimos.readthedocs.io/en/latest/user_guide/loading_saving.html to convert with DEIMoS directly", duration=0)
                        load_file = deimos.load(file_name_initial, accession={'retention_time': rt_name_value, 'drift_time': dt_name_value})
                        
                        # Save ms1 to new file, use x so don't overwrite existing file
                        deimos.save(new_name, load_file['ms1'], key='ms1', mode='w')

                        # Save ms2 to same file
                        deimos.save(new_name, load_file['ms2'], key='ms2', mode='a')
                        pn.state.notifications.info("saving as h5 file in " + str(new_name))
                        pn.state.notifications.info("done loading", duration=0)
                        return load_file[key]
        elif extension ==".h5":
                return deimos.load(file_name_initial, key=key, columns=columns)
        elif extension ==".csv":
                return pd.read_csv(file_name_initial)
        else:
             if extension == "":
                     extension = "Folder"
             raise Exception(extension + " used. Please only use h5, mzML, or mzML.gz files")
           
def load_initial_deimos_data(file_name_initial, feature_dt, feature_rt, feature_mz, feature_intensity, rt_name, dt_name,  new_name = None,  key= 'ms1'):
        '''
        full function to return dataframe with load_mz_h5

        Parameters:
                file_name_initial (path): file path to data
                feature_dt (str): drift time name
                feature_rt (str): retention time name
                feature_mz (str): mz name
                feature_intensity (str): intensity name
                key (str): key for uploaded data, such as ms1 or ms2
                rt_name (list): name retention time accession if using mzML file
                dt_name (list): name drift time accession if using mzML file
        Returns:
                pd DataFrame with data 
        '''
        if file_name_initial == 'data/placeholder.csv' or file_name_initial == 'data/created_data/placeholder.csv' :     
                raise Exception("Select files and adjust parameters before clicking 'Rerun'")
        full_data_1 = load_mz_h5(file_name_initial, key=key, columns=[feature_mz, feature_dt, feature_rt, feature_intensity], rt_name = rt_name, dt_name = dt_name, new_name = new_name)
        full_data_1 = full_data_1[[feature_dt, feature_rt, feature_mz, feature_intensity]]
        full_data_1.reset_index(drop = True, inplace=True)
        return full_data_1

        
def create_smooth(file_name_initial, feature_mz, feature_dt, feature_rt, feature_intensity,smooth_radius, smooth_iterations, new_smooth_name, rt_name, dt_name):
                '''
                get the smooth data

                Parameters:
                        file_name_initial (path): file path to data
                        feature_dt (str): drift time name
                        feature_rt (str): retention time name
                        feature_mz (str): mz name
                        feature_intensity (str): intensity name
                        radius (float or list): Radius of the sparse filter in each dimension. Values less than
                                zero indicate no connectivity in that dimension.
                        iterations (int): Maximum number of smoothing iterations to perform.
                        new_smooth_name (str): name of new smooth data
                        rt_name (list): name retention time accession if using mzML file
                        dt_name (list): name drift time accession if using mzML file
                Returns:
                        pd DataFrame with data 
                '''
                if os.path.exists(new_smooth_name):
                        raise Exception(new_smooth_name + " already exists. Please rename before continuing")
           
                else:
                        ms1 = load_mz_h5(file_name_initial, key='ms1', columns=[feature_mz, feature_dt, feature_rt, feature_intensity], rt_name = rt_name, dt_name = dt_name)
                        ms2 = load_mz_h5(file_name_initial, key='ms2', columns=[feature_mz, feature_dt, feature_rt, feature_intensity], rt_name = rt_name, dt_name = dt_name)

                        factors = deimos.build_factors(ms1, dims='detect')
                                
                        # Nominal threshold
                        ms1 = deimos.threshold(ms1, threshold=128)
                        # Build index
                        index_ms1_peaks = deimos.build_index(ms1, factors)
                        # Smooth data
                        smooth_radius= [int(i) for i in list(smooth_radius.split('-'))]
                        iterations = int(smooth_iterations)
                        pn.state.notifications.info('Smooth MS1 data', duration=3000)
                        ms1_smooth = deimos.filters.smooth(ms1, index=index_ms1_peaks, dims=[feature_mz, feature_dt, feature_rt],
                                                radius=smooth_radius, iterations=iterations)
                        
                        ## save with date and time because user won't reuse. 
                        deimos.save(new_smooth_name, ms1_smooth, key='ms1', mode='w')

                                # append peak ms2
                        factors = deimos.build_factors(ms2, dims='detect')
                        
                        pn.state.notifications.info('Smooth MS2 data', duration=3000)
                        # Nominal threshold
                        ms2 = deimos.threshold(ms2, threshold=128)
                        # Build index
                        index_ms2_peaks = deimos.build_index(ms2, factors)

                        # Smooth data
                        iterations = int(smooth_iterations)
                        # Smooth data
                        ms2_smooth = deimos.filters.smooth(ms2, index=index_ms2_peaks, dims=[feature_mz, feature_dt, feature_rt],
                                                radius=smooth_radius, iterations=iterations)
                        ## save with date and time because user won't reuse. 
                        deimos.save(new_smooth_name, ms2_smooth, key='ms2', mode='a')
                        return ms1_smooth, index_ms1_peaks, index_ms2_peaks

def create_peak(file_name_smooth, feature_mz, feature_dt, feature_rt, feature_intensity,  threshold_slider,  peak_radius, index_ms1_peaks, index_ms2_peaks, new_peak_name, rt_name = None, dt_name = None ):
                '''
                get the smooth data

                Parameters:
                        file_name_smooth (path): file path to data
                        feature_dt (str): drift time name
                        feature_rt (str): retention time name
                        feature_mz (str): mz name
                        feature_intensity (str): intensity name
                        threshold_slider (int): threshold data with this value
                        index_ms1_peaks (dict) Index of features in original data array.
                        index_ms2_peaks (dict) Index of features in original data array.
                        peak_radius (float, list, or None) If specified, radius of the sparse weighted mean filter in each dimension.
                        Values less than one indicate no connectivity in that dimension.
                        new_peak_name (str): name of new peak data
                        rt_name (list): name retention time accession if using mzML file
                        dt_name (list): name drift time accession if using mzML file
                Returns:
                        pd DataFrame with data 
                '''
                if os.path.exists(new_peak_name):
                        raise Exception(new_peak_name + " already exists. Please rename before continuing or use the existing file name in the smooth file name")
                      
                else:
                        ms1_smooth = load_mz_h5(file_name_smooth, key='ms1', columns=[feature_mz, feature_dt, feature_rt, feature_intensity], rt_name = rt_name, dt_name = dt_name)
                        ms2_smooth = load_mz_h5(file_name_smooth, key='ms2', columns=[feature_mz, feature_dt, feature_rt, feature_intensity], rt_name = rt_name, dt_name = dt_name)


                        peak_radius= [int(i) for i in list(peak_radius.split('-'))]

                        # Perform peak detection
                        ms1_peaks = deimos.peakpick.persistent_homology(deimos.threshold(ms1_smooth,  threshold = 128),  index=index_ms1_peaks,
                                                                        dims=[feature_mz, feature_dt, feature_rt],
                                                                        radius=peak_radius)
                        # Sort by persistence
                        ms1_peaks = ms1_peaks.sort_values(by='persistence', ascending=False).reset_index(drop=True)
                        # Save ms1 to new file
                        ms1_peaks = deimos.threshold(ms1_peaks, by='persistence', threshold=int(threshold_slider))
                        ms1_peaks = deimos.threshold(ms1_peaks, by='intensity', threshold=int(threshold_slider))
                        deimos.save(new_peak_name, ms1_peaks, key='ms1', mode='w')


                        # Perform peak detection
                        ms2_peaks = deimos.peakpick.persistent_homology(deimos.threshold(ms2_smooth,  threshold = 128), index=index_ms2_peaks,
                                                                        dims=[feature_mz, feature_dt, feature_rt],
                                                                        radius=peak_radius)
                        
                        ms2_peaks = deimos.threshold(ms2_peaks, by='persistence', threshold=int(threshold_slider))
                        ms2_peaks = deimos.threshold(ms2_peaks, by='intensity', threshold=int(threshold_slider))
                        # Sort by persistence
                        ms2_peaks = ms2_peaks.sort_values(by='persistence', ascending=False).reset_index(drop=True)
                        # update list of options in file selections
                        
                        # Save ms2 to new file with _new_peak_data.h5 suffix
                        deimos.save(new_peak_name, ms2_peaks, key='ms2', mode='a')
                        return ms1_peaks

def align_peak_create(full_ref, theshold_presistence, feature_mz, feature_dt, feature_rt, feature_intensity):
        '''
                get the smooth data

                Parameters:
                        full_ref (path): file path to data
                        threshold_presistence (int): initial threshold presistence
                        feature_dt (str): drift time name
                        feature_rt (str): retention time name
                        feature_mz (str): mz name
                        feature_intensity (str): intensity name
                Returns:
                        pd DataFrame with data 
        '''
        peak_ref  = deimos.peakpick.persistent_homology(deimos.threshold(full_ref,  threshold = 128),
                                                dims=[feature_mz, feature_dt, feature_rt])
        peak_ref = deimos.threshold(peak_ref, by='persistence', threshold=1000)
        peak_ref = deimos.threshold(peak_ref, by='intensity', threshold=1000)
        return peak_ref

def offset_correction_model(dt_ms2, mz_ms2, mz_ms1, ce=0,
                            params=[1.02067031, -0.02062323,  0.00176694]):
    '''function to correct '''
    # Cast params as array
    params = np.array(params).reshape(-1, 1)
    
    # Convert collision energy to array
    ce = np.ones_like(dt_ms2) * np.log(ce)
    
    # Create constant vector
    const = np.ones_like(dt_ms2)
    
    # Sqrt
    mu_ms1 = np.sqrt(mz_ms1)
    mu_ms2 = np.sqrt(mz_ms2)
    
    # Ratio
    mu_ratio = mu_ms2 / mu_ms1
    
    # Create dependent array
    x = np.stack((const, mu_ratio, ce), axis=1)
    
    # Predict
    y = np.dot(x, params).flatten() * dt_ms2
    
    return y

# function that adjusts the x_range and y_range with either x y stream or user input
# this work-arround is necessary due to the x_range and y_range streams being set to none with new data
# if not set to none, old data ranges from previous data are still used
# when range is set to none, need to explicitely set the x and y range of the of the rasterization level and plot limits, else it will rasterize over whole image: 
# trying to avoid this bug https://github.com/holoviz/holoviews/issues/4396
# keep an eye on this, as likely will fix in datashader, which would make this work around unnecessary

def rasterize_plot(
element,
feature_intensity,
x_filter=None,
y_filter=None,
x_spacing=0,
y_spacing=0,
):
        '''
                get the smooth data

                Parameters:
                        element: graph object
                        feature_intensity (str): intensity value
                        x_filter (tuple): x range
                        y_filter (tuple): y range
                        x_spacing (flt): min size of grids
                        y_spacing (flt): min size of grids
                Returns:
                        pd DataFrame with data 
        '''
        # dynmaic false to allow the x_range and y_range to be adjusted by either
        #xy stream or manual filter rather than automaically
        rasterize_plot = rasterize(
                element,
                width=800,
                height=600,
                # summing here by intensity, rather than using the deimos.collapse and summing by intensity 
                # per feature_dt & feature_rt group, and interpolating into a heatmap
                aggregator=ds.sum(feature_intensity),
                x_sampling=x_spacing,
                y_sampling=y_spacing,
                x_range=x_filter,
                y_range=y_filter,
                dynamic=False,
        )
        ropts = dict(
                tools=["hover"],
                default_tools=[],
                colorbar=True,
                colorbar_position="bottom",
                cmap=cc.blues,
                cnorm='eq_hist')
        # actually changes the x and y limits seen, not just the rasterization levels
        if y_filter != None and x_filter != None:
                rasterize_plot.apply.opts(
                xlim=x_filter, ylim=y_filter, framewise=True, **ropts
                )
        else:
                rasterize_plot.apply.opts(framewise=True, **ropts)
        return rasterize_plot

def new_name_if_mz(mz_file_name):
        extension = Path(mz_file_name).suffix
        if extension == ".mzML" or extension == ".gz":
                new_name = os.path.join("created_data",  Path(mz_file_name).stem + '.h5')
        else:
                new_name = None
        return new_name