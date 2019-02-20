'''Module to make Python handles to SL1000 VXI11 commands.

Alan Kastengren, XSD, APS

Started: March 29, 2015
'''
import time
import vxi11
import numpy as np

SL1000 = None
IP_string = '164.54.107.82'

def connect_to_SL1000():
    '''Connects to SL1000 and sets up communication.
    '''
    global SL1000
    #Connect to the SL1000
    SL1000 = vxi11.Instrument(IP_string)
    #Set communication so command isn't echoed
    SL1000.write(":COMM:HEAD OFF")

def disconnect_SL1000():
    '''Disconnects the link to the SL1000.
    '''
    SL1000.close()

def execute_calibration():
    '''Command the instrument to perform a calibration.
    '''
    SL1000.write(":CAL:EXEC")

def set_acq_time_s(acq_time):
    '''Sets the acquisition time of the SL1000.
    '''
    acq_time_string = ""
    #Make the string that gets sent to the SL1000
    if acq_time >= 1.0:
        acq_time_string = "0,0,0," + str(int(acq_time)) + ",0,0"
    elif acq_time >= 1e-3:
        acq_time_string = "0,0,0,0," + str(int(acq_time * 1e3)) + ",0"
    else:
        acq_time_string = "0,0,0,0,0," + str(int(acq_time * 1e6))
    #Send the string
    SL1000.write(":ACQ:TIME " + acq_time_string)

def read_acq_time_s():
    '''Reads the acquisition time and parses the output to be readable.
    '''
    acq_time_string = SL1000.ask(":ACQ:TIME?")
    acq_time_split = acq_time_string.split(",")
    acq_seconds = 86400. * int(acq_time_split[0]) + 3600. * int(acq_time_split[1])
    acq_seconds += 60. * int(acq_time_split[2]) + int(acq_time_split[3]) 
    acq_seconds += 1e-3 * int(acq_time_split[4]) + 1e-6 * int(acq_time_split[5])
    print "Acquisition time = " + str(acq_seconds) + " s."

def start_acquisition():
    '''Starts an acquisition.  This must be stopped to read waveform data.
    '''
    SL1000.write(":STAR")

def stop_acquisition():
    '''Stops acquisition.  After this, data can be read.
    '''
    SL1000.write(":STOP")

def manual_trigger():
    '''Applies a manual trigger.
    '''
    SL1000.write(":MTR")

def start_single_trigger(delay = None):
    '''Starts acquisition in single trigger mode.  
    Delay of delay seconds will be used to wait for completion.
    '''
    if delay:
        SL1000.write(":SSTAR? " + str(int(delay*10)))
    else:
        SL1000.write(":SSTAR")

################  Sample rate settings  ##################################

def read_sample_rate():
    '''Reads the sample rate for measurement group 1.
    '''
    return SL1000.ask(":TIM:SRAT?")

def set_sample_rate(requested_rate):
    '''Set the sample rate for measurement group 1 to the requested number in Hz.
    '''
    integer_rate = int(requested_rate)
    SL1000.write(":TIM:SRAT " + str(integer_rate))

def read_module_meas_group(mod_number):
    '''Reads the measurement group to which a module belongs.
    '''
    if _check_chan_num(mod_number):
        return SL1000.ask(":TIM:MODU" + str(int(mod_number)) + ":GROU?")

def set_module_meas_group(mod_number,group_number):
    if _check_chan_num(mod_number) and _check_chan_num(group_number,4):
        SL1000.write(":TIM:MODU" + str(int(mod_number)) + ":GROU " + str(int(group_number)))

def read_meas_group_sample_rate(group_number):
    '''Read the sample rate for a measurement group.
	Have to treat group 1 differently.
    '''
    if _check_chan_num(group_number,4):
        if group_number == 1:
            return read_sample_rate()
        else:
            return SL1000.ask(":TIM:GROU" + str(int(group_number)) + ":SRAT?")

def set_meas_group_sample_rate(group_number,sample_rate=100):
    '''Set the sample rate of measurement group group_number to sample_rate Hz.
    '''
    if _check_chan_num(group_number,4):
        if group_number == 1:
            set_sample_rate(sample_rate)
        else:
            SL1000.write(":TIM:GROU" + str(int(group_number)) + ":SRAT " + str(sample_rate))

########## Channel vertical scale settings  #########################

def _check_chan_num(chan_num,max_num=16):
    '''Checks if the specified channel number makes sense.
    '''
    if int(chan_num) < 1 or int(chan_num) > max_num:
        print "Improper channel number.  Try again."
        return False
    else:
        return True

def enable_channel(chan_num):
    '''Enables a channel specified by chan_num.
    '''
    if _check_chan_num(chan_num):
        SL1000.write(":CHAN"+str(int(chan_num)) + ":DISP ON")

def disable_channel(chan_num):
    '''Enables a channel specified by chan_num.
    '''
    if _check_chan_num(chan_num):
        SL1000.write(":CHAN"+str(int(chan_num)) + ":DISP OFF")

def read_channel_enabled(chan_num):
    '''Read if a channel is already enabled.
    '''
    if _check_chan_num(chan_num):
        return SL1000.ask(":CHAN"+str(int(chan_num)) + ":DISP?")

def read_channel_bandwidth(chan_num):
    '''Reads the bandwidth applied to this channel.
    '''
    if _check_chan_num(chan_num):
        return SL1000.ask(":CHAN"+str(int(chan_num)) + ":VOLT:BWID?")

def set_channel_bandwidth(chan_num,bandwidth_Hz):
    '''Sets the bandwidth of the analog filter on a channel.
    '''
    if _check_chan_num(chan_num):
        SL1000.write(":CHAN"+str(int(chan_num)) + ":VOLT:BWID " + str(int(bandwidth_Hz)))

def remove_channel_filter(chan_num):
    '''Removes the filtering on a channel.
    '''
    if _check_chan_num(chan_num):
        SL1000.write(":CHAN"+str(int(chan_num)) + ":VOLT:BWID FULL")

def read_channel_coupling(chan_num):
    '''Read whether coupling is AC or DC on channel chan_num.  
    '''
    if _check_chan_num(chan_num):
        return SL1000.ask(":CHAN"+str(int(chan_num)) + ":VOLT:COUP?")

def set_channel_coupling(chan_num, dc=True):
    '''Set the coupling of channel chan_num.  DC if dc = True, AC otherwise.
    '''
    input_string = "DC" if dc else "AC"
    if _check_chan_num(chan_num):
        SL1000.write(":CHAN"+str(int(chan_num)) + ":VOLT:COUP " + input_string)

def read_channel_units(chan_num):
    '''Read the units of channel chan_num.
    '''
    if _check_chan_num(chan_num):
        return SL1000.ask(":CHAN"+str(int(chan_num)) + ":UNIT?")

def read_channel_v_div(chan_num):
    '''Read the volts/division for channel chan_num.
    '''
    if _check_chan_num(chan_num):
        return SL1000.ask(":CHAN"+str(int(chan_num)) + ":VOLT:VDIV?")

def set_channel_v_div(chan_num,volts_per_div):
    '''Sets the volts/division of channel chan_num to volts_per_div.
    '''
    if _check_chan_num(chan_num):
        #Enable channel first, otherwise this doesn't work
        enable_channel(chan_num)
        SL1000.write(":CHAN"+str(int(chan_num)) + ":VOLT:VDIV " + str(volts_per_div))

def read_channel_module(chan_num):
    '''Reads the module cooresponding to the channel chan_num.
    '''
    if _check_chan_num(chan_num):
        return SL1000.ask(":CHAN"+str(int(chan_num)) + ":MODU?")[1:]

def read_channel_module_verbose(chan_num):
    '''Reads the module cooresponding to the channel chan_num.
    Gives more extensive information.
    '''
    module_number = read_channel_module(chan_num)
    if module_number == "720210":
        return 'Module 720210, 100 MS/s, 12-bit, Isolated Inputs.'
    elif module_number == '701251':
        return 'Module 701251, 1 MS/s, 16-bit, Isolated Inputs.'
    elif module_number == '701250':
        return 'Module 701250, 10 MS/s, 12-bit, Isolated Inputs.'
    elif module_number == '701255':
        return 'Module 701255, 10 MS/s, 12-bit, Non-isolated Inputs.'
    else:
        return module_number

def read_channel_probe(chan_num):
    '''Read the probe setting applied to the channel chan_num.
    '''
    if _check_chan_num(chan_num):
        return SL1000.ask(":CHAN"+str(int(chan_num)) + ":VOLT:PROB?")

def set_channel_probe(chan_num,probe):
    '''Sets the probe setting of the channel chan_num.
    '''
    if _check_chan_num(chan_num):
        SL1000.write(":CHAN"+str(int(chan_num)) + ":VOLT:PROB " + str(probe))

##########################  Trigger settings  ####################################
def read_trigger_source():
    '''Read the source of the trigger.
    '''
    return SL1000.ask(":TRIG:SIMP:SOUR?")

def set_trigger_source_channel(chan_num):
    '''Set the trigger source to channel chan_num.
    '''
    if _check_chan_num(chan_num):
        SL1000.write(":TRIG:SIMP:SOUR " + str(chan_num))

def set_trigger_source_ext():
    '''Set the trigger source to EXT.
    '''
    SL1000.write(":TRIG:SIMP:SOUR EXT")

def set_trigger_source_line():
    '''Set the trigger source to the line.
    '''
    SL1000.write(":TRIG:SIMP:SOUR LINE")

def read_trigger_slope():
    '''Read the slope of the trigger.
    '''
    return SL1000.ask(":TRIG:SLOP?")

def set_trigger_slope(rising=True):
    '''Set the trigger slope to rising if rising=True, falling if False.
    '''
    if rising:
        SL1000.write(":TRIG:SLOP RISE")
    else:
        SL1000.write(":TRIG:SLOP FALL")

def read_trigger_level():
    '''Read the trigger level.
    '''
    return SL1000.ask(":TRIG:LEV?")

def set_trigger_level(trig_level):
    '''Set the trigger level.
    '''
    print ":TRIG:LEV " + str(trig_level)
    SL1000.write(":TRIG:LEV " + str(trig_level))

def read_trigger_position():
    '''Read the trigger position in %.
    '''
    return SL1000.ask(":TRIG:POS?")

def set_trigger_position(trig_position):
    '''Set the trigger position in %.
    '''
    SL1000.write(":TRIG:POS " + str(trig_position))

def read_trigger_delay():
    '''Read the trigger delay.
    '''
    return SL1000.ask(":TRIG:DEL?")

def set_trigger_delay(trig_delay):
    '''Set the trigger level.
    '''
    if float(trig_delay) >= 1e-8:
        SL1000.write(":TRIG:DEL " + str(trig_delay))
    else:
        print "Invalid delay setting."

def read_trigger_mode():
    '''Read the measurement mode.  Either normal, nsingle, or single.
    '''
    return SL1000.ask(":TRIG:MMOD?")

def set_trigger_mode_single():
    '''Set the measurement mode to single trigger.
    '''
    SL1000.write(":TRIG:MMOD SINGLE")

def set_trigger_mode_normal():
    '''Set the measurement mode to normal trigger.
    '''
    SL1000.write(":TRIG:MMOD NORMAL")

###############  Waveform commands  #####################################

def read_waveform_bits():
    '''Read the bits per point in the waveform data.
    '''
    return SL1000.ask(":WAV:BITS?")

def read_waveform_division():
    '''Read the value to use to divide waveform values
    to get physical units.
    '''
    return SL1000.ask(":WAV:DIV?")

def read_waveform_length():
    '''Read the length of the waveform.
    '''
    return int(SL1000.ask(":WAV:LENG?"))

def read_waveform_sample_rate():
    '''Read the sample rate of the waveform.
    '''
    return SL1000.ask(":WAV:SRAT?")

def read_waveform_channel():
    '''Read which channel we are currently looking at.
    '''
    return SL1000.ask(":WAV:TRAC?")

def set_waveform_channel(chan_num):
    '''Set which channel is being manipulated with waveform commands.
    '''
    if _check_chan_num(chan_num):
        SL1000.write(":WAV:TRAC " + str(int(chan_num)))

def read_waveform_record_number():
    '''Read which record in the history is being manipulated with waveform commands.
    '''
    return SL1000.ask(":WAV:REC?")

def set_waveform_record_number(record_num):
    '''Set which record in the history is being manipulated with waveform commands.
    '''
    if int(record_num) < 1 and int(record_num) > -5000:
        SL1000.write(":WAV:REC " + str(int(record_num)))
    else:
        print "Improper record number.  Must be [-4999,0]."

def read_waveform_start_point():
    '''Read the point of the data record that will be the first one retrieved
    when the waveform is retrieved.
    '''
    return SL1000.ask(":WAV:STAR?")

def set_waveform_start_point(start_point):
    '''Read the point of the data record that will be the first one retrieved
    when the waveform is retrieved.
    '''
    if int(start_point) >= 0 and int(start_point) <= read_waveform_length():
        SL1000.write(":WAV:STAR " + str(int(start_point)))
    else:
        print "Improper setting for start point of the waveform record."

def read_waveform_end_point():
    '''Read the point of the data record that will be the last one retrieved
    when the waveform is retrieved.
    '''
    return SL1000.ask(":WAV:END?")

def set_waveform_end_point(end_point):
    '''Read the point of the data record that will be the last one retrieved
    when the waveform is retrieved.
    '''
    if int(end_point) >= 0 and int(end_point) <= read_waveform_length():
        SL1000.write(":WAV:END " + str(int(end_point)))
    else:
        print "Improper setting for start point of the waveform record."

def read_waveform_data(chan_num = 1):
    '''Read the waveform data and return as a numpy array.
    '''
    #Set the proper channel number
    if not _check_chan_num(chan_num):
        return
    set_waveform_channel(chan_num)
    #Read the number of bits in the waveform record
    num_bytes = int(read_waveform_bits())/8
    #Read the length of the waveform record
    wave_length = int(read_waveform_length())
    print num_bytes,wave_length
    #Set up the points to be retrieved
    set_waveform_start_point(0)
    set_waveform_end_point(int(read_waveform_length())-1)
    gain_value = float(SL1000.ask(":WAV:GAIN?"))
    #Return the actual array
    if num_bytes == 1:
        return np.fromstring(SL1000.ask_raw(":WAV:SEND?")[-num_bytes*wave_length-1:-1],dtype='<i1') * gain_value
    else:
        return np.fromstring(SL1000.ask_raw(":WAV:SEND?")[-num_bytes*wave_length-1:-1],dtype='<i2') * gain_value

def read_single_trigger_with_wait():
    '''Reads waveform if we are waiting for single trigger to complete.
    '''
    SL1000.write(":STAT:FILT FALL")
    SL1000.ask(":STAT:EESR?")
    set_trigger_mode_single()
    start_acquisition()
    SL1000.write(":COMM:WAIT 1")
    stop_acquisition()
    return read_waveform_data()

def test_single_trigger_with_wait():
    set_trigger_source_channel(1)
    set_trigger_level(0.5)
    return read_single_trigger_with_wait()

def test_single_trigger_blocking():
    set_trigger_source_channel(1)
    set_trigger_level(0.5)
    return read_single_trigger_blocking()

def read_single_trigger_blocking():
    stop_acquisition()
    start_single_trigger()
    time.sleep(0.01)
    mask = 0x05
    while True:
        if mask & int(SL1000.ask(":STAT:COND?")):
            print SL1000.ask(":STAT:COND?")
            time.sleep(0.01)
        else:
            print int(SL1000.ask(":STAT:COND?"))
            stop_acquisition()
            break
    return read_waveform_data()


    


