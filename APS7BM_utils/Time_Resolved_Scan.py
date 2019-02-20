'''Module to perform time-resolved scans with the SL1000 DAQ unit.

Alan Kastengren, XSD, APS

Started: July 22, 2015
'''
import epics
import time
import SL1000_Commands as sl1000
import numpy as np
import h5py
import matplotlib.pyplot as plt

#Pseudocode to lay out the logic
def fsetup_SL1000():
    '''Connects to SL1000 and checks that connection works.
    '''
    sl1000.connect_to_SL1000()
    fexecute_calibration()
    sl1000.read_acq_time_s()

def fdisconnect_SL1000():
    '''Disconnects the SL1000
    '''
    sl1000.disconnect_SL1000()

def fsetup_SL1000_timing(module=1,meas_group=1,time_duration = 0.1,samp_freq=1e6):
    '''Sets up pertinent parameters for SL1000 DAQ timing.
    Inputs
    module: which module are we setting the timings for, default 1
    meas_group: which measurement group should this module be in, default 1
    time_duration: requested time duration of trace in s, default 0.1
    samp_freq: requested sampling frequency in Hz, default 1e6
    '''
    #Make the module part of the desired measurement group
    sl1000.set_module_meas_group(module,meas_group)
    #Read the sample rate for measurement group 1.  Set to samp_freq if it is 
    #below samp_freq
    if sl1000.read_sample_rate() < samp_freq:
        sl1000.set_sample_rate(samp_freq) 
    time.sleep(0.1)
    #Set the sampling frequency for this measurements group
    sl1000.set_meas_group_sample_rate(meas_group,samp_freq)
    #Set the total time duration
    sl1000.set_acq_time_s(time_duration)
    #Echo back
    sl1000.read_acq_time_s()
    print "Module " + str(module) + " in measurement group " + sl1000.read_module_meas_group(module)
    print "Module " + str(module) + " sample rate = " +sl1000.read_meas_group_sample_rate(meas_group) + " Hz."

def fexecute_calibration():
    sl1000.execute_calibration()
    time.sleep(5)

def fenable_channels(channel_list,max_channels=16):
    '''Enables only the channels listed.  All others are disabled.
    '''
    for i in range(1,max_channels+1):
        if i in channel_list:
            sl1000.enable_channel(i)
        else:
            sl1000.disable_channel(i)

def fsetup_channel_vertical(chan_num = 1,filter_bw = None,coupling_dc=True,volts_range=0.5):
    '''Set up the vertical parameters for the channel.
    '''
    #Enable channel, in case it isn't already.
    sl1000.enable_channel(chan_num)
    #Set the filter bandwidth, unless none is specified.
    if filter_bw:
        sl1000.set_channel_bandwidth(chan_num,filter_bw)
    else:
        sl1000.remove_channel_filter(chan_num)
    #Set the filter coupling
    sl1000.set_channel_coupling(chan_num,coupling_dc)
    #Set the channel v/div
    sl1000.set_channel_v_div(chan_num,volts_range/10.0)
    #So we don't get surprised, set the channel probe to 1
    sl1000.set_channel_probe(chan_num,1)
    #Echo back to make sure everything worked
    print "Channel " + str(chan_num) + " bandwidth (Hz) = " + sl1000.read_channel_bandwidth(chan_num)
    print "Channel " + str(chan_num) + " coupling = " + sl1000.read_channel_coupling(chan_num)
    print "Channel " + str(chan_num) + " V/div = +/-" + sl1000.read_channel_v_div(chan_num)
    print "Voltage range is 10 * the V/div."

def fsetup_SL1000_triggering(source='EXT',rising_slope=True,trig_level=1.0,horz_position=0,
                            delay_s=0,trig_mode='SINGLE'):
    '''Sets up the triggering for the SL1000.
    '''
    #Set the trigger mode to either EXT, LINE, or a channel number
    if str(source).upper() == 'EXT':
        sl1000.set_trigger_source_ext()
    elif str(source).upper() == 'LINE':
        sl1000.set_trigger_source_line()
    else:
        #Conversion to an int for channel number may not work.
        try:
            i = int(source)
            sl1000.set_trigger_source_channel(i)
        except:
            print "Improper input for trigger source."
    #Set the slope
    sl1000.set_trigger_slope(rising_slope)
    #Set the trigger level
    sl1000.set_trigger_level(trig_level)
    #Set the horizontal position
    if 0 <= horz_position <= 100:    
        sl1000.set_trigger_position(horz_position)
    else:
        print "Improper input for trigger position, must be [0,100]."
    #Set trigger delay
    sl1000.set_trigger_delay(delay_s)
    #Set the trigger mode
    if str(trig_mode).upper() == 'SINGLE':
        sl1000.set_trigger_mode_single()
    elif str(trig_mode).upper() == 'NORMAL':
        sl1000.set_trigger_mode_normal()
    else:
        print "Unsupported trigger mode.  Mode not changed."
    #Echo parameters back to make sure they all were accepted
    print "Trigger source = " + sl1000.read_trigger_source()
    #Slope doesn't work for LINE, level doesn't work for EXT or LINE
    if sl1000.read_trigger_source() != 'LINE':
        print "Trigger slope = " + sl1000.read_trigger_slope()
        if sl1000.read_trigger_source() != 'EXT':
            print "Trigger level (V) = " + sl1000.read_trigger_level()
    print "Trigger position (%) = " + sl1000.read_trigger_position()
    print "Trigger delay (s) = " + sl1000.read_trigger_delay()
    print "Trigger mode = " + sl1000.read_trigger_mode()
    
def facquire_trace_single_trigger(channel_list):
    '''Sets the SL1000 for a single trigger, then
    returns a list of numpy objects with voltage
    values.
    '''
    #Enable channels
    fenable_channels(channel_list)
    #Trigger the SL1000
    facquire_single_trigger()
    #Read out the channels
    output_list = []
    for channel in channel_list:
        output_list.append(sl1000.read_waveform_data(channel))
        plt.plot(sl1000.read_waveform_data(channel))
    plt.show()
    return output_list

def facquire_single_trigger():
    '''Causes a single trigger to occur, 
    waiting for acquisition to finish.
    '''
    sl1000.SL1000.write(":STAT:FILT FALL")
    sl1000.SL1000.ask(":STAT:EESR?")
    sl1000.set_trigger_mode_single()
    sl1000.start_acquisition()
    sl1000.SL1000.write(":COMM:WAIT 1")
    sl1000.stop_acquisition()

def fautorange_channel(chan_num):
    '''Automatically autoranges the vertical scale of the channel.
    '''
        
    acceptable_v_range = [0.001,0.002,0.05,0.1,0.2,0.5,1.0,2.0,5.0]
    #Start looping, starting with largest range
    for v_range in acceptable_v_range:
        #Set the voltage range to the desired value
        fsetup_channel_vertical(chan_num,volts_range=v_range)
        #Take a trace in single-shot mode
        output_list = facquire_trace_single_trigger([chan_num])
        #See if max is > range.  If so, continue
        if np.max(output_list[0]) > v_range:
            print "Maximum voltage exceeded at voltage range " + str(v_range)
            continue
        #If min is < -v_range, continue.
        if np.min(output_list[0]) < -v_range:
            print "Minimum voltage exceeded at voltage range " + str(v_range)
            print np.min(output_list[0])
            continue
        #If we get here, the trace must have been good.
        print "Suitable voltage range reached: " + str(v_range)
        break

def finitialize_hdf5_file(prefix='Scan_',file_path='/home/SprayData/',num_pv = '7bmb1:saveData_scanNumber',digits=4):
    '''Initilizes an hdf5 file for saving scan data.
    '''
    #Figure out the scan number
    scan_num = epics.caget(num_pv) - 1
    #Make the number of digits at least equal to the length of scan_num
    digit_str = str(digits)
    if len(str(scan_num)) > digits:
        digit_str = str(len(str(scan_num)))
    #Format the filename
    file_name = prefix + ('{:0' + digit_str + 'd}').format(scan_num) + '.hdf5'
    return h5py.File(file_path+file_name,'w')

def finitialize_hdf5_dataset_scalar(hdf_file,pv_name,hdf5_alias=None,scan_name='7bmb1:scan1'):
    '''Initializes an HDF5 dataset for a PV giving a scalar value at every point.
    '''
    #If we haven't given an alias for the PV in the HDF5 file, use the PV name
    if hdf5_alias==None:
        hdf5_alias = pv_name
    #Figure out how many points there are in the scan
    num_points = epics.caget(scan_name+'.NPTS')
    #If the dataset name already exists, delete it
    if hdf_file.get(hdf5_alias):
        del(hdf_file[hdf5_alias])
    #Make a numpy array the right length with the right type
    dummy_array = np.zeros(num_points)
    #Add the dataset, with the appropriate length
    hdf_file.create_dataset(hdf5_alias,data=dummy_array)
        
def fupdate_hdf5_dataset_scalar(hdf_file,pv_name,hdf5_alias=None,scan_name='7bmb1:scan1',current_pt=None):
    '''Adds a point to a scalar dataset.
    '''
    #If we haven't given an alias for the PV in the HDF5 file, use the PV name
    if hdf5_alias == None:
        hdf5_alias = pv_name
    #Figure out which point we are currently on
    if current_pt == None:
        current_pt = epics.caget(scan_name + '.CPT')
    #Get the current PV value
    current_value = epics.caget(pv_name)
    #Update the value of this point
    hdf_file[hdf5_alias][current_pt] = current_value

def finitialize_hdf5_dataset_waveform(hdf_file,channel_num,hdf5_alias=None,scan_name='7bmb1:scan1'):
    '''Initialize an HDF5 dataset for waveform data captured from the SL1000.
    '''
    print "Channel # " + str(channel_num)
    #If we haven't given an alias for the PV in the HDF5 file, use the PV name
    if hdf5_alias==None:
        hdf5_alias = "SL1000_Channel_" + str(channel_num)
    #Figure out how many points there are in the scan
    num_points = epics.caget(scan_name+'.NPTS')
    #If the dataset name already exists, delete it
    if hdf_file.get(hdf5_alias):
        del(hdf_file[hdf5_alias])
    #Figure out how big the trace is
    sl1000.set_waveform_channel(channel_num)
    waveform_length = sl1000.read_waveform_length()
    #Make a numpy array the right length with 32 bit floats
    dummy_array = np.zeros((num_points,waveform_length),dtype='f4')
    #Add the dataset, with the appropriate length
    hdf_file.create_dataset(hdf5_alias,data=dummy_array)

def fupdate_hdf5_dataset_waveform(hdf_file,channel_num,hdf5_alias=None,scan_name='7bmb1:scan1',current_pt=None):
    '''Adds a point to a waveform dataset.
    '''
    #If we haven't given an alias for the PV in the HDF5 file, use the PV name
    if hdf5_alias == None:
        hdf5_alias = "SL1000_Channel_" + str(channel_num)
    #Figure out which point we are currently on
    if current_pt == None:
        current_pt = epics.caget(scan_name + '.CPT')
    #Retrieve the waveform and write to hdf5 file
    hdf_file[hdf5_alias][current_pt,:] = sl1000.read_waveform_data(channel_num)

def frespond_to_next_point(hdf_file,scalar_pv_dict,channel_num_dict,scan_name='7bmb1:scan1'):
    '''Respond to a signal showing that we've reached the next point.
    Inputs
    scalar_pv_dict: dictionary where key:value = pv_name:alias
    channel_num_dict: dictionary where key:value = channel_num:alias
    scan_name: name of controlling scan
    '''
    #Trigger SL1000 acquisition
    facquire_single_trigger()
    #Figure out the current point
    current_pt = epics.caget(scan_name + '.CPT')
    #Loop through scalar PVs, saving their values
    for pv_name,alias in scalar_pv_dict.items():
        fupdate_hdf5_dataset_scalar(hdf_file,pv_name,alias,scan_name,current_pt)
    #Update waveform PVs
    for channel_num,alias in channel_num_dict.items():
        fupdate_hdf5_dataset_waveform(hdf_file,channel_num,alias,scan_name,current_pt)
    #Flush the HDF5 buffers
    hdf_file.flush()

def finitial_setup(scalar_pv_dict,channel_num_dict,prefix='Scan_',file_path='/home/SprayData/',num_pv = '7bmb1:saveData_scanNumber',digits=4,
                    scan_name='7bmb1:scan1'):
    '''Performs all of the setup tasks at the beginning of a scan.
    '''
    #Enable channels on the SL1000
    fenable_channels(channel_num_dict.keys())
    #Perform a trigger to update the SL1000
    facquire_single_trigger()
    #Set up the HDF5 file
    hdf_file = finitialize_hdf5_file(prefix,file_path,num_pv,digits)
    #Initialize the scalar pvs
    for pv_name,alias in scalar_pv_dict.items():
        finitialize_hdf5_dataset_scalar(hdf_file,pv_name,alias,scan_name)
    #Initialize the waveform datasets
    for channel_num,alias in channel_num_dict.items():
        finitialize_hdf5_dataset_waveform(hdf_file,int(channel_num),alias,scan_name)
    #Flush the HDF5 buffers
    hdf_file.flush()
    return hdf_file

def finitialize_scalars_from_scan_record(scalar_pv_dict,scan_name='7bmb1:scan1'):
    '''Adds the detectors and positioners 

def ffinal_cleanup(hdf_file):
    '''Cleans up at the end of a scan.
    '''
    hdf_file.close()

def fcontrol_scan(prefix='Scan_',file_path='/home/SprayData/Cycle_2015_2/',num_pv = '7bma1:saveData_scanNumber',
                    digits=4,scalar_pv_dict={'7bmb1:m28.VAL':'X','7bmb1:IP330_3.VAL':'Gas_Flowrate'},
                    channel_num_dict={'1':None,'2':'Dummy'},scan_name='7bma1:scan1',
                    initial_busy='7bmb1:busy8',point_busy='7bmb1:busy9',cleanup_busy='7bmb1:busy10'):
    '''Controls an entire scan.
    '''
    #Set up PV objects for the busy records
    initial_pv = epics.PV(initial_busy)
    point_pv = epics.PV(point_busy)
    cleanup_pv = epics.PV(cleanup_busy)
    #Run in a continuous loop
    hdf_file=None
    while True:
        #If the initial PV is 1, we need to set up an HDF5 file.
        if initial_pv.value == 1:
            hdf_file = finitial_setup(scalar_pv_dict,channel_num_dict,prefix,file_path,num_pv,digits,scan_name)
            initial_pv.value=0
            time.sleep(0.02)
        if point_pv.value == 1:
            print "Gone to a new point."
            frespond_to_next_point(hdf_file,scalar_pv_dict,channel_num_dict,scan_name)
            point_pv.value=0
            time.sleep(0.02)
        if cleanup_pv.value == 1:  
            print "Received signal to clean up."
            ffinal_cleanup(hdf_file)
            hdf_file=None
            cleanup_pv.value=0
            return
        time.sleep(0.01)

#Overall logic
'''
1.  Set up SL1000 comm
2.  Set important state information on the SL1000
    a.  Voltage and filtering
    b.  Time duration and sampling frequency
    c.  Triggering information
3.  Autorange the voltage to make sure the range is correct.  Maybe combine with autorange of Femto.
4.  Set up an HDF5 file to hold data.  This probably should occur when a scan starts, so number of points is set.
    *  Listen for the change in a busy record, probably from a before scan PV trigger in the scan record.
    a.  Set up 2D datasets for the scope variables.
    b.  Set up 1D datasets for the scalar values recorded from EPICS.
5.  At every point during a scan:
    *  Listen for the change to a busy record, much like DataGrabber.
    a.  Trigger SL1000
    b.  Once data have been acquired, pull the data off of the scope
    c.  Save to the appropriate database.
6.  At the end of the scan.
    *  Again, listen for a busy record, probably triggered from the after scan PV.
    a.  Write the scan record detectors to the HDF5 file.
    b.  Move to a "clear air" area and trigger the SL1000.  Record these data as a separate dataset.
    c.  Close the shutter.  Trigger the SL1000, average the values, and save as a one point dataset.
7.  Close the HDF file
'''
