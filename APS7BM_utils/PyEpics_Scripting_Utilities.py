'''Useful functions for PyEPICS scripting.

Alan Kastengren, XSD, APS

Started: February 13, 2015
'''
import epics
import numpy as np
import time
import math
import logging

#Add a comment just for fun
SR_current_PV = epics.PV('S:SRcurrentAI.VAL')
A_shutter_closed_PV = epics.PV('PB:07BM:STA_A_FES_CLSD_PL.VAL')
B_shutter_closed_PV = epics.PV('PB:07BM:STA_B_SBS_CLSD_PL.VAL')
threshold_SR_current=30

def fwait_for_PV_completion(monitored_PV,middle_functions=[],middle_args=[[]],poll_time = 1):
    '''Wait for a PV to signal completion, optionally running functions meanwhile.
    
    Runs an endless loop until the monitored PV completes using put_complete. 
    Optionally, run middle_functions in the middle of the loop.
    Inputs:
    moitored_PV: epics PV object for the PV to be monitored.
    middle_functions: list of functions to be run while waiting.
    middle_args: list of lists of arguments to pass to middle_functions
    poll_time: time between polls to see if monitored_PV has completed.
    '''
    waiting = True
    while waiting:
        if monitored_PV.put_complete:
            break
        time.sleep(poll_time)
        #Run middle functions, in order
        for func,args in zip(middle_functions,middle_args):
            func(args)
        waiting = not monitored_PV.put_complete

def fmonitored_action(action_pv,readback_pv,action_value=1,desired_readback=1,sleep_time=1.0):
    '''Perform an action and wait for it to complete by monitoring another PV.
    
    This is useful for beamline shutters in particular, since a put_complete
    doesn't work to monitor them.
    Inputs:
    action_pv: epics.PV object or string of a PV name that should be activated
    readback_pv: epics.PV object to monitor to see that action is complete
    action_value: value to put to action_pv
    desired_readback: value we desire on the readback
    sleep_time: time to sleep between polls of the readback_pv
    '''
    waiting = 0
    #If this is already a PV object, just put a value to it.
    if isinstance(action_pv,epics.pv.PV):
        action_pv.put(action_value)
    #If it isn't already a PV, assume it's a string and just caput
    else:
        epics.caput(action_pv,action_value)
    while waiting < 30:
        time.sleep(1)
        waiting += 1
        if readback_pv.value == desired_readback:
            logging.info("Action completed in fmonitored_action.")
            return
    else:
        logging.warning("Action timed out in fmonitored_action.")
        return

def fcheck_for_bad_beam():
    '''Checks for storage ring current and shutter status.
    Returns True if the storage ring current is too low or if a shutter is closed.
    '''
    return SR_current_PV.value < threshold_SR_current or A_shutter_closed_PV.value > 0.1 or B_shutter_closed_PV.value > 0.1

def fcheck_for_good_beam(action_PV=None,good_beam_value=0,bad_beam_value=1):
    '''Runs a loop checking the storage ring current and shutters' status.
    If they go bad, wait for the storage ring current to be high enough
    and for the A shutter to be open.  Also,change a PV value based on this.
    For example, one could pause a scan. 
    '''
    #If the action_PV is set already, it must have been set manually.
    manual_pause = False            #Variable to keep track if action_PV was set manually
    if action_PV and action_PV.value == bad_beam_value:
        manual_pause = True
        print "Manual pause"
    
    #If we have bad beam conditions, throw a software pause
    software_pause = False
    if fcheck_for_bad_beam():
        software_pause = True
        print "Software pause"
    
    while software_pause or manual_pause:
        #If this is a manual pause, just wait for 1 s.  Release manual pause if pause button was pressed.  
        if manual_pause: 
            print action_PV.value 
            if action_PV.value == good_beam_value:
                print "Manual pause rescinded."
                manual_pause = False
                continue
            time.sleep(1.0)
        #If not manually paused, check for whether good beam conditions exist.
        elif not fcheck_for_bad_beam():
            print "Resuming operations."
            #Unpause the scan if it is paused
            if action_PV and action_PV.value == bad_beam_value:
                action_PV.value = good_beam_value
            software_pause = False
            return
        else:
            #If the scan isn't paused yet, pause it.
            if action_PV and action_PV.value == good_beam_value:
                action_PV.value = bad_beam_value
            software_pause = True
            print "Software pause initiated"
            #Try to open the shutters
            fopen_shutters()
            #Wait so I don't crash the crate      
            time.sleep(1)

def fsimple_repeated_scan(num_times,scan_name='7bmb1:scan1',wait_time = 1.0):
    '''Simply repeat a scan num_times times.  Check for shutter and stored beam.
    
    Inputs:
    num_times: number of times to repeat the scan.
    scan_name: name of the scan record to activate.
    '''
    scan_busy = epics.PV(scan_name+'.BUSY')
    while num_times:
        print("In the repeat loop")
        #Monitor for good beam
        fcheck_for_good_beam(epics.PV(scan_name+'.scanPause.VAL'),0,1)
        #Start the scan
        epics.caput(scan_name+'.EXSC',1,wait=False)
        time.sleep(1.0)
        #Check if the scan is done
        while scan_busy.value:
            #Sleep a little
            time.sleep(0.5)
        num_times -= 1
        time.sleep(wait_time)

def fautomated_repeated_scan(scan_name='7bmb1:scan1'):
    '''Performs a repeated scan.
    '''
    repeated_scan_busy_PV = epics.PV('7bmb1:busy4')
    scan_busy = epics.PV(scan_name+'.BUSY')
    counter = 0
    while True:
        if repeated_scan_busy_PV.value == 1:
            num_repeats = int(epics.caget('7bmb1:var:int1'))
            sec_between_pts = float(epics.caget('7bmb1:var:float6'))
            while num_repeats:
                print("In the repeat loop")
                #Monitor for good beam
                while epics.caget("S:SRcurrentAI.VAL") < 30.0 or epics.caget('PA:07BM:STA_A_BEAMREADY_PL.VAL') < 0.5:
                    print("Waiting for the beam to come back up.")
                    time.sleep(5.0)
                #Check to make sure we haven't clicked "Done" on repeated_scan_busy to abort this.
                if repeated_scan_busy_PV.value == 0:
                    break
                #Start the scan
                epics.caput(scan_name+'.EXSC',1,wait=False)
                time.sleep(1.0)
                #Check if the scan is done
                while scan_busy.value:
                    #Sleep a little
                    time.sleep(0.5)
                num_repeats -= 1
                time.sleep(sec_between_pts)
            repeated_scan_busy_PV.value = 0
            time.sleep(0.5)
        if counter == 1000:
            print "Looking for repeated scan busy at time " + time.strftime('%H:%M:%S',time.localtime())
            counter = 0
        else:
            counter += 1
        time.sleep(0.01)

def fautomated_repeated_scan_busy(busy_name='7bmb1:busy5'):
    '''Performs a repeated scan.
    '''
    repeated_scan_busy_PV = epics.PV('7bmb1:busy4')
    counter = 0
    try:
        while True:
            if repeated_scan_busy_PV.value == 1:
                num_repeats = int(epics.caget('7bmb1:var:int1'))
                sec_between_pts = float(epics.caget('7bmb1:var:float6'))
                for i in range(num_repeats):
                    if repeated_scan_busy_PV.value == 0:
                        break
                    print("In the repeat loop on scan #{:3d}".format(i))
                    #Monitor for good beam
                    while epics.caget("S:SRcurrentAI.VAL") < 30.0 or epics.caget('PA:07BM:STA_A_BEAMREADY_PL.VAL') < 0.5:
                        print("Waiting for the beam to come back up.")
                        time.sleep(5.0)
                    fopen_A_shutter()
                    #Start the scan
                    epics.caput(busy_name,'Busy')
                    time.sleep(1.0)
                    for __ in range(int(sec_between_pts)):
                        #Check to make sure we haven't clicked "Done" on repeated_scan_busy to abort this.
                        print("Waiting for the next scan.")                        
                        if repeated_scan_busy_PV.value == 0:
                            print("Scan aborted!")
                            break
                        time.sleep(1.0)
                repeated_scan_busy_PV.value = 0
                time.sleep(0.5)
            if counter == 100:
                print "Looking for repeated scan busy at time " + time.strftime('%H:%M:%S',time.localtime())
                counter = 0
            else:
                counter += 1
            time.sleep(0.01)
    finally:
        print("Problem in repeated scan loop.")
        fclose_A_shutter()

def fscan_2D_separate_files(scan_motor,motor_points,scan_button,scan_pause_button):
    '''Perform a scan through a list of motor positions, running a scan at each
    motor position.  I will also pause the scan if stored beam is lost or 
    a shutter is opened.
    '''
    fopen_shutters()
    for pos in motor_points:
        scan_motor.move(pos,wait=True)
        fcheck_for_good_beam()
        scan_button.put(1,use_complete=True)
        fwait_for_PV_completion(scan_button,[fcheck_for_good_beam],middle_args=[scan_pause_button])

def fopen_shutters():
    '''Opens the A and B shutters.
    '''
    fopen_A_shutter()
    fopen_B_shutter()
    return

def fclose_shutters():
    '''Closes the A and B shutters.
    '''
    fclose_A_shutter()
    fclose_B_shutter()
    return

def fopen_A_shutter():
    '''Opens the A shutter if it isn't already open.
    '''
    if A_shutter_closed_PV.value == 1:
        fmonitored_action('7bma1:rShtrA:Open',A_shutter_closed_PV,desired_readback=0)
    
def fclose_A_shutter():
    '''Closes the A shutter if it isn't already closed.
    '''
    if A_shutter_closed_PV.value == 0:
        fmonitored_action('7bma1:rShtrA:Close',A_shutter_closed_PV,desired_readback=1)

def fopen_B_shutter():
    '''Opens the B shutter if it isn't already open.
    '''
    if B_shutter_closed_PV.value == 1:
        fmonitored_action('7bma1:rShtrB:Open',B_shutter_closed_PV,desired_readback=0)
    
def fclose_B_shutter():
    '''Closes the B shutter if it isn't already closed.
    '''
    if B_shutter_closed_PV.value == 0:
        fmonitored_action('7bma1:rShtrB:Close',B_shutter_closed_PV,desired_readback=1)

def fautorange_femto_ADC(ADC_board='7bm_dau1:dau:',channel=1,wait_time=2.0,
                        threshold_high = 0.8,threshold_low = 0.07,
                        amp_name='7bmb1:femto2'):
    '''Scales Femto amp to give the best gain setting.
    '''
    #Form a PV object (since we'll be accessing it a lot)
    femto_gain = epics.PV(amp_name + ':GainIndex')
    print("Current Femto gain index = " + str(femto_gain.value))
    #Set the Femto amp to lowest gain
    femto_gain.value = 0
    #Set up the count time on the scaler board and the relevant PVs from scaler
    amp_output = epics.PV(ADC_board + '{:03d}'.format(channel) + ':ADC')
    #Start a loop
    optimum_gain = False
    while not optimum_gain:
        #Wait for a moment
        time.sleep(wait_time)
        #Compute the voltage
        print "Femto Gain Index = " + str(femto_gain.value)
        print "Amp voltage = " + str(amp_output.value) + " V"
        if amp_output.value > threshold_high:
            if femto_gain.value == 0:
                print "Already at lowest gain.  Leaving it here."
                optimum_gain = True
            else:
                femto_gain.value = femto_gain.value - 1
                continue
        elif amp_output.value < threshold_low:
            if femto_gain.value == 5:
                print "Already at highest gain.  Leaving it here."
                optimum_gain = True
            else:
                femto_gain.value = femto_gain.value + 1
                continue
        #If we get here, the gain is optimal
        print "Gain optimal."
        optimum_gain = True

def fautorange_BIM_ADC():
    fautorange_femto_ADC(channel=7,amp_name='7bmb1:femto2')

def fautorange_PIN_ADC():
    fautorange_femto_ADC(channel=8,amp_name='7bmb1:femto1')

def AutorangeAllADC():
    fautorange_BIM_ADC()
    fautorange_PIN_ADC()

def CavitationPSOFly(motor='7bmb1:aero:m1',mcs='7bmb1:3820',scan='7bmb1:scan1',speed=1,delta=.1, start=0,end=1,asynRec='7bmb1:PSOFly1:cmdWriteRead', axis='Z', PSOInput=3,encoder_multiply=1e5):
    '''Performs fly scan for cavitation measurements 2015-2.
    Based on Tim Mooney's code, but does calculations in user coordinates
    and sets up the MCS and scan as well.
    '''
    #Make sure the PSO control is off
    epics.caput(asynRec+'.BOUT', 'PSOCONTROL %s RESET' % axis, wait=True, timeout=300.0)
    time.sleep(0.01)
    # Encoder direction compared to dial coordinates.  Hard code this; could ask controller
    encoderDir = -1
    #Get motor direction (dial vs. user) and acceleration time
    motor_dir = epics.caget(motor+'.DIR')    #0 = positive, 1 = neg
    motor_accl = epics.caget(motor+'.ACCL')    #Acceleration time in s
    if motor_dir:
        motor_dir = -1
    else:
        motor_dir = 1
    #Figure out whether motion is in positive or negative direction in user coordinates
    user_direction = 1 if end > start else -1
    #Figure out overall sense: +1 if motion in + encoder direction, -1 otherwise
    overall_sense = user_direction * motor_dir * encoderDir
    print "Overall sense = " + str(overall_sense)
    #Get the distance needed for acceleration = 1/2 a t^2 = 1/2 * v * t
    accelDist = motor_accl*speed/2                    
    #Make taxi distance an integral number of measurement deltas >= accel distance
    #Add 1/2 of a delta, since we want integration centered on start and end.
    taxiDist = math.ceil(accelDist/delta)*delta
    taxiPos = start-(taxiDist+0.5*delta)*user_direction
    motorEnd = end+accelDist*user_direction
    #Increase range very slightly to avoid roundoff issues
    num_points = math.floor(math.fabs(start-end)*1.0001/delta)+1
    print taxiPos,motorEnd
    
    # taxi
    epics.caput(motor+'.VAL', taxiPos, wait=True, timeout=300.0)
    time.sleep(0.1)

    ## initPSO: commands to the Ensemble to control PSO output.
    # Everything but arming and setting the positions for which pulses will occur.
    epics.caput(asynRec+'.BOUT', 'PSOOUTPUT %s CONTROL 1' % axis, wait=True, timeout=300.0)
    time.sleep(0.01)
    epics.caput(asynRec+'.BOUT', 'PSOPULSE %s TIME 20,10' % axis, wait=True, timeout=300.0)
    time.sleep(0.01)
    epics.caput(asynRec+'.BOUT', 'PSOOUTPUT %s PULSE WINDOW MASK' % axis, wait=True, timeout=300.0)
    time.sleep(0.01)
    epics.caput(asynRec+'.BOUT', 'PSOTRACK %s INPUT %d' % (axis, PSOInput), wait=True, timeout=300.0)
    time.sleep(0.01)
    epics.caput(asynRec+'.BOUT', 'PSODISTANCE %s FIXED %f UNITS' % (axis,delta), wait=True, timeout=300.0)
    time.sleep(0.01)
    epics.caput(asynRec+'.BOUT', 'PSOWINDOW %s 1 INPUT %d' % (axis,PSOInput), wait=True, timeout=300.0)
    time.sleep(0.01)

    #We want pulses to start at start - delta/2.  
    range_start = taxiDist * overall_sense
    #range_start = (start - delta/2.0 * user_direction) * overall_sense
    range_length = (math.fabs(start-end) + delta) * overall_sense
    #The start of the PSO window must be < end.  Handle this.
    if overall_sense > 0:
        window_start = int(range_start * encoder_multiply)
        window_end = window_start + int(range_length * encoder_multiply)
    else:
        window_end = int(range_start * encoder_multiply)
        window_start = window_end + int(range_length * encoder_multiply)
    #Remember, the window settings must be in encoder counts
    epics.caput(asynRec+'.BOUT', 'PSOWINDOW %s 1 RANGE %.6f,%.6f' % (axis,window_start-5,window_end+5), wait=True, timeout=300.0)
    print 'PSOWINDOW %s 1 RANGE %.6f,%.6f' % (axis,window_start-5,window_end+5)
    #Arm the PSO
    time.sleep(0.01)
    epics.caput(asynRec+'.BOUT', 'PSOCONTROL %s ARM' % axis, wait=True, timeout=300.0)
    
    #Set up the scan record parameters
    epics.caput(scan+'.P1SP',taxiPos, wait=True, timeout=300.0)
    epics.caput(scan+'.P1EP',motorEnd, wait=True, timeout=300.0)
    epics.caput(scan+'.NPTS',num_points, wait=True, timeout=300.0)
    epics.caput(scan+'.P1SM', 2, wait=True, timeout=300.0)
    epics.caput(scan+'.T1PV',mcs+':EraseStart', wait=True, timeout=300.0)
    for i in [2,3,4]:
        epics.caput(scan+'.T'+str(i)+'PV',"", wait=True, timeout=300.0)
    epics.caput(scan+'.ACQT',1, wait=True, timeout=300.0)
    epics.caput(scan+'.D01PV',mcs+':mca1.VAL', wait=True, timeout=300.0)
    epics.caput(scan+'.D02PV',mcs+':mca2.VAL', wait=True, timeout=300.0)
    epics.caput(scan+'.D03PV',mcs+':mca3.VAL', wait=True, timeout=300.0)
    epics.caput(scan+'.D04PV','7bmb1:userArrayCalc1.AVAL', wait=True, timeout=300.0)    
    epics.caput(scan+'.D05PV','S:SRcurrentAI.VAL', wait=True, timeout=300.0)
    #ACCUMULATOR MW100 PVS
    #for i in range(1,8):
    #    epics.caput(scan+'.D%02iPV' % (i+5),'7bm_dau3:dau:A%03i:Math' % i, wait=True, timeout=300.0)
    #AMBIENT CONDITIONS
    #epics.caput(scan+'.D13PV','APS:BarometricPressure:MBR', wait=True, timeout=300.0)
    #epics.caput(scan+'.D14PV','G:DIWP:OutAirTempAi', wait=True, timeout=300.0)
    #epics.caput(scan+'.D15PV','7bm_dau1:dau:009:ADC', wait=True, timeout=300.0)
    # MASS FLOW CTRLR
    #epics.caput(scan+'.D16PV','7bmb1:st1:Flow', wait=True, timeout=300.0)
    #ADD MORE DETECTORS HERE.  MAKE SURE THE NEXT LINE DOESN'T WIPE ANY OUT    
    for i in range(6,71):
        epics.caput(scan+'.D'+'{:02d}'.format(i)+'PV','', wait=True, timeout=300.0)

    #Set up the MCS
    epics.caput(mcs+':NuseAll',num_points, wait=True, timeout=300.0)
    
    #Set up an array calc for the positions
    epics.caput('7bmb1:userArrayCalc1.A',delta, wait=True, timeout=300.0)
    epics.caput('7bmb1:userArrayCalc1.B',start, wait=True, timeout=300.0)
    epics.caput('7bmb1:userArrayCalc1.NUSE',num_points, wait=True, timeout=300.0)
    epics.caput('7bmb1:userArrayCalc1.CALC','IX*A+B',wait=True,timeout=300.0)
    epics.caput('7bmb1:userArrayCalc1.PROC',1, wait=True, timeout=300.0)
    
    # fly
    # Start counting on the MCS
    #epics.caput(mcs+':EraseStart',1,wait=False)
    #Get the old motor speed
    oldVelo = epics.caget(motor+'.VELO')
    #Set motor speed
    epics.caput(motor+'.VELO', speed, wait=True, timeout=300.0)
    epics.caput(scan+'.EXSC',1,wait=True,timeout=300.0)
    print "Motion Done"
    #Turn PSO off and put the motor speed back to its old value.
    epics.caput(asynRec+'.BOUT', 'PSOWINDOW %s OFF' % axis, wait=True, timeout=300.0)
    epics.caput(asynRec+'.BOUT', 'PSOCONTROL %s OFF' % axis, wait=True, timeout=300.0)
    epics.caput(motor+'.VELO', oldVelo, wait=True, timeout=300.0)

def PSO_SetupAerotech(motor='7bmb1:aero:m1',speed=1,delta=.1,start=0,end=1,asynRec='7bmb1:PSOFly1:cmdWriteRead', axis='Z', PSOInput=3,encoder_multiply=1e5):
    '''Script to set up the Ensemble for PSO output.
    '''
    #Make sure the PSO control is off
    epics.caput(asynRec+'.BOUT', 'PSOCONTROL %s RESET' % axis, wait=True, timeout=300.0)
    time.sleep(0.05)
    # Encoder direction compared to dial coordinates.  Hard code this; could ask controller
    encoderDir = -1
    #Get motor direction (dial vs. user) and acceleration time
    motor_dir = epics.caget(motor+'.DIR')    #0 = positive, 1 = neg
    motor_accl = epics.caget(motor+'.ACCL')    #Acceleration time in s
    if motor_dir:
        motor_dir = -1
    else:
        motor_dir = 1
    #Figure out whether motion is in positive or negative direction in user coordinates
    user_direction = 1 if end > start else -1
    #Figure out overall sense: +1 if motion in + encoder direction, -1 otherwise
    overall_sense = user_direction * motor_dir * encoderDir
    print "Overall sense = " + str(overall_sense)
    #Get the distance needed for acceleration = 1/2 a t^2 = 1/2 * v * t
    accelDist = motor_accl*speed/2                    
    #Make taxi distance an integral number of measurement deltas >= accel distance
    #Add 1/2 of a delta, since we want integration centered on start and end.
    taxiDist = math.ceil(accelDist/delta)*delta
    taxiPos = start-(taxiDist+0.5*delta)*user_direction
    motorEnd = end+accelDist*user_direction
    #Increase range very slightly to avoid roundoff issues
    num_points = math.floor(math.fabs(start-end)*1.0001/delta)+1
    print taxiPos,motorEnd
    
    # taxi
    epics.caput(motor+'.VAL', taxiPos, wait=True, timeout=300.0)
    time.sleep(0.1)

    ## initPSO: commands to the Ensemble to control PSO output.
    # Everything but arming and setting the positions for which pulses will occur.
    #Set the output to occur from the I/O terminal on the controller
    epics.caput(asynRec+'.BOUT', 'PSOOUTPUT %s CONTROL 1' % axis, wait=True, timeout=300.0)
    time.sleep(0.05)
    #Set a pulse 10 us long, 20 us total duration, so 10 us on, 10 us off
    epics.caput(asynRec+'.BOUT', 'PSOPULSE %s TIME 20,10' % axis, wait=True, timeout=300.0)
    time.sleep(0.05)
    #Set the pulses to only occur in a specific window
    epics.caput(asynRec+'.BOUT', 'PSOOUTPUT %s PULSE WINDOW MASK' % axis, wait=True, timeout=300.0)
    time.sleep(0.05)
    #Set which encoder we will use.  3 = the MXH (encoder multiplier) input, which is what we generally want
    epics.caput(asynRec+'.BOUT', 'PSOTRACK %s INPUT %d' % (axis, PSOInput), wait=True, timeout=300.0)
    time.sleep(0.05)
    #Set the distance between pulses.  Manual says this should be in counts, but units seems to work
    epics.caput(asynRec+'.BOUT', 'PSODISTANCE %s FIXED %f UNITS' % (axis,delta), wait=True, timeout=300.0)
    time.sleep(0.05)
    #Which encoder is being used to calculate whether we are in the window.  1 for single axis
    epics.caput(asynRec+'.BOUT', 'PSOWINDOW %s 1 INPUT %d' % (axis,PSOInput), wait=True, timeout=300.0)
    time.sleep(0.05)

    #Calculate window function parameters.  Must be in encoder counts, and is 
    #referenced from the stage location when we enabled the PSO (i.e., the
    #taxi position). 
    #We want pulses to start at start - delta/2.  
    range_start = taxiDist * overall_sense
    range_length = (math.fabs(start-end) + delta) * overall_sense
    #The start of the PSO window must be < end.  Handle this.
    if overall_sense > 0:
        window_start = int(range_start * encoder_multiply)
        window_end = window_start + int(range_length * encoder_multiply)
    else:
        window_end = int(range_start * encoder_multiply)
        window_start = window_end + int(range_length * encoder_multiply)
    #Remember, the window settings must be in encoder counts
    epics.caput(asynRec+'.BOUT', 'PSOWINDOW %s 1 RANGE %.6f,%.6f' % (axis,window_start-5,window_end+5), wait=True, timeout=300.0)
    print 'PSOWINDOW %s 1 RANGE %.6f,%.6f' % (axis,window_start,window_end)
    #Arm the PSO
    time.sleep(0.05)
    epics.caput(asynRec+'.BOUT', 'PSOCONTROL %s ARM' % axis, wait=True, timeout=300.0)
    #Set motor speed
    epics.caput(motor+'.VELO', speed, wait=True, timeout=300.0)

def PSO_SetupScan(motor='7bmb1:aero:m1',mcs='7bmb1:3820',scan='7bmb1:scan1',speed=1,delta=.1, start=0,end=1):
    '''Script to set up the scan for Ensemble PSO fly scans.
    '''
    #Get motor accel time in s
    motor_accl = epics.caget(motor+'.ACCL')
    #Figure out whether motion is in positive or negative direction in user coordinates
    user_direction = 1 if end > start else -1
    #Get the distance needed for acceleration = 1/2 a t^2 = 1/2 * v * a
    accelDist = motor_accl*speed/2                    
    #Make taxi distance an integral number of measurement deltas >= accel distance
    #Add 1/2 of a delta, since we want integration centered on start and end.
    taxiDist = math.ceil(accelDist/delta)*delta
    taxiPos = start-(taxiDist+0.5*delta)*user_direction
    motorEnd = end+accelDist*user_direction
    #Increase range very slightly to avoid roundoff issues
    num_points = math.floor(math.fabs(start-end)*1.0001/delta)+1
    print taxiPos,motorEnd,num_points
    
    #Set up the scan record parameters
    epics.caput(scan+'.P1SP',taxiPos, wait=True, timeout=300.0)
    epics.caput(scan+'.P1EP',motorEnd, wait=True, timeout=300.0)
    epics.caput(scan+'.NPTS',num_points, wait=True, timeout=300.0)
    epics.caput(scan+'.P1SM', 2, wait=True, timeout=300.0)
    epics.caput(scan+'.T1PV',mcs+':EraseStart', wait=True, timeout=300.0)
    for i in [2,3,4]:
        epics.caput(scan+'.T'+str(i)+'PV',"", wait=True, timeout=300.0)
    epics.caput(scan+'.ACQT',1, wait=True, timeout=300.0)

    #Set up the MCS
    epics.caput(mcs+':NuseAll',num_points, wait=True, timeout=300.0)
    
    #Set up an array calc for the positions
    epics.caput('7bmb1:userArrayCalc1.A',delta, wait=True, timeout=300.0)
    epics.caput('7bmb1:userArrayCalc1.B',start, wait=True, timeout=300.0)
    epics.caput('7bmb1:userArrayCalc1.NUSE',num_points, wait=True, timeout=300.0)
    epics.caput('7bmb1:userArrayCalc1.CALC','IX*A+B',wait=True,timeout=300.0)
    epics.caput('7bmb1:userArrayCalc1.PROC',1, wait=True, timeout=300.0)

def PSO_SetupScan_Imaging(motor='7bmb1:aero:m1',trig_root='7bmPG1:cam1',scan='7bmb1:scan1',speed=1,delta=.1, start=0,end=1):
    '''Script to set up the scan for Ensemble PSO fly scans.
    '''
    #Get motor accel time in s
    motor_accl = epics.caget(motor+'.ACCL')
    #Figure out whether motion is in positive or negative direction in user coordinates
    user_direction = 1 if end > start else -1
    #Get the distance needed for acceleration = 1/2 a t^2 = 1/2 * v * a
    accelDist = motor_accl*speed/2                    
    #Make taxi distance an integral number of measurement deltas >= accel distance
    #Add 1/2 of a delta, since we want integration centered on start and end.
    taxiDist = math.ceil(accelDist/delta)*delta
    taxiPos = start-(taxiDist+0.5*delta)*user_direction
    motorEnd = end+accelDist*user_direction
    #Increase range very slightly to avoid roundoff issues
    num_points = math.floor(math.fabs(start-end)*1.0001/delta)+1
    print taxiPos,motorEnd,num_points
    
    #Set up the scan record parameters
    epics.caput(scan+'.P1SP',taxiPos, wait=True, timeout=300.0)
    epics.caput(scan+'.P1EP',motorEnd, wait=True, timeout=300.0)
    epics.caput(scan+'.NPTS',num_points, wait=True, timeout=300.0)
    epics.caput(scan+'.P1SM', 2, wait=True, timeout=300.0)
    epics.caput(scan+'.T1PV',trig_root+':Acquire', wait=True, timeout=300.0)
    for i in [2,3,4]:
        epics.caput(scan+'.T'+str(i)+'PV',"", wait=True, timeout=300.0)
    epics.caput(scan+'.ACQT',1, wait=True, timeout=300.0)

    #Set up areaDetector to have the right number of images
    epics.caput(trig_root+':NumImages',num_points, wait=True, timeout=300.0)
    epics.caput(trig_root+':ImageMode',1, wait=True, timeout=300.0)
    return

def PSO_Initial_Setup(motor='7bmb1:aero:m2',mcs='7bmb1:3820',scan='7bmb1:scan1',speed=1,delta=.1,start=0,end=1,asynRec='7bmb1:PSOFly2:cmdWriteRead', axis='X', PSOInput=3,encoder_multiply=1e5):
    '''Performs setup on controller and the scan record.
    '''
    PSO_SetupAerotech(motor,speed,delta,start,end,asynRec,axis,PSOInput,encoder_multiply)
    PSO_SetupScan(motor,mcs,scan,speed,delta,start,end)

def PSO_Initial_Setup_X(scan='7bmb1:scan1',speed=1,delta=.1,start=0,end=1):
    '''Performs initial setup of controller and scan record for horizontal fly scans.
    '''
    PSO_Initial_Setup('7bmb1:aero:m2','7bmb1:3820',scan,speed,delta,start,end,'7bmb1:PSOFly2:cmdWriteRead', axis='X', PSOInput=3,encoder_multiply=1e5)

def PSO_Initial_Setup_Y(scan='7bmb1:scan1',speed=1,delta=.1,start=0,end=1):
    '''Performs initial setup of controller and scan record for vertical fly scans.
    '''
    PSO_Initial_Setup('7bmb1:aero:m1','7bmb1:3820',scan,speed,delta,start,end,'7bmb1:PSOFly1:cmdWriteRead', axis='Z', PSOInput=3,encoder_multiply=1e5)

def PSO_Initial_Setup_Theta(scan='7bmb1:scan1',speed=1,delta=.1,start=0,end=1):
    '''Performs initial setup of controller and scan record for vertical fly scans.
    '''
    PSO_Initial_Setup('7bmb1:aero:m3','7bmb1:3820',scan,speed,delta,start,end,'7bmb1:PSOFly3:cmdWriteRead', axis='A', PSOInput=3,encoder_multiply=float(2**15)/0.36)

def PSO_Cleanup(motor='7bmb1:aero:m1',asynRec='7bmb1:PSOFly1:cmdWriteRead', 
                            axis='Z', oldVelo=5):
    '''Perform actions after the fly motion is done to prepare to move back.
    '''
    print "Motion Done"
    #Turn PSO off and put the motor speed back to its old value.
    epics.caput(asynRec+'.BOUT', 'PSOWINDOW %s OFF' % axis, wait=True, timeout=300.0)
    epics.caput(asynRec+'.BOUT', 'PSOCONTROL %s OFF' % axis, wait=True, timeout=300.0)
    epics.caput(motor+'.VELO', oldVelo, wait=True, timeout=300.0)

def PSO_Monitor_Daemon(setup_busy='7bmb1:busy1',cleanup_busy='7bmb1:busy2',scan_setup_busy='7bmb1:busy3',
                                motor='7bmb1:aero:m2',mcs='7bmb1:3820',scan='7bmb1:scan1',
                                asynRec='7bmb1:PSOFly2:cmdWriteRead',axis='X', PSOInput=3,encoder_multiply=1e5):
    '''Code the looks for changes in the busy records to control PSO fly scanning.
        Uses the user variables to control speed, start, end, delta, and the retrace speed.
    '''
    PSO_setup_busy_PV = epics.PV(setup_busy)
    cleanup_busy_PV = epics.PV(cleanup_busy)
    scan_setup_busy_PV = epics.PV(scan_setup_busy)
    speed_PV = epics.PV('7bmb1:var:float1')
    delta_PV = epics.PV('7bmb1:var:float2')
    start_PV = epics.PV('7bmb1:var:float3')
    end_PV = epics.PV('7bmb1:var:float4')
    retrace_PV = epics.PV('7bmb1:var:float5')
    counter = 0
    while True:
        if PSO_setup_busy_PV.value == 1:
            #Do this twice, because for whatever reason it sometimes doesn't work the first time
            PSO_SetupAerotech(motor,speed_PV.value,delta_PV.value,
                                start_PV.value,end_PV.value,asynRec,axis,PSOInput,encoder_multiply)
            PSO_SetupAerotech(motor,speed_PV.value,delta_PV.value,
                                start_PV.value,end_PV.value,asynRec,axis,PSOInput,encoder_multiply)
            PSO_setup_busy_PV.value = 0
            time.sleep(0.05)
        elif cleanup_busy_PV.value == 1:
            PSO_Cleanup(motor,asynRec,axis,retrace_PV.value)
            cleanup_busy_PV.value = 0
            time.sleep(0.05)
        if scan_setup_busy_PV.value == 1:
            PSO_SetupScan(motor,mcs,scan,speed_PV.value,delta_PV.value,
                                start_PV.value,end_PV.value)
            scan_setup_busy_PV.value = 0
        if counter == 10000:
            print "Looking for busys at time " + time.strftime('%H:%M:%S',time.localtime())
            counter = 0
        else:
            counter += 1
        time.sleep(0.001)

def PSO_Monitor_Daemon_Y(setup_busy='7bmb1:busy1',cleanup_busy='7bmb1:busy2',scan_setup_busy='7bmb1:busy3',
                                motor='7bmb1:aero:m1',mcs='7bmb1:3820',scan='7bmb1:scan1',
                                asynRec='7bmb1:PSOFly1:cmdWriteRead',axis='Z', PSOInput=3,encoder_multiply=1e5):
    PSO_Monitor_Daemon(setup_busy,cleanup_busy,scan_setup_busy,
                                motor,mcs,scan,
                                asynRec,axis, PSOInput,encoder_multiply)
    

def PSO_Monitor_Daemon_Tomo(setup_busy='7bmb1:busy1',cleanup_busy='7bmb1:busy2',scan_setup_busy='7bmb1:busy3',
                                motor='7bmb1:aero:m3',trig_root = '7bm_pg1:cam1',scan='7bmb1:scan1',
                                asynRec='7bmb1:PSOFly3:cmdWriteRead',axis='A', PSOInput=3,encoder_multiply=float(2**15)/0.36):
    '''Does PSO_Monitor_Daemon for tomography fly scans.
    '''
    PSO_setup_busy_PV = epics.PV(setup_busy)
    cleanup_busy_PV = epics.PV(cleanup_busy)
    scan_setup_busy_PV = epics.PV(scan_setup_busy)
    speed_PV = epics.PV('7bmb1:var:float1')
    delta_PV = epics.PV('7bmb1:var:float2')
    start_PV = epics.PV('7bmb1:var:float3')
    end_PV = epics.PV('7bmb1:var:float4')
    retrace_PV = epics.PV('7bmb1:var:float5')
    counter = 0
    while True:
        if PSO_setup_busy_PV.value == 1:
            #Do this twice, because for whatever reason it sometimes doesn't work the first time
            PSO_SetupAerotech(motor,speed_PV.value,delta_PV.value,
                                start_PV.value,end_PV.value,asynRec,axis,PSOInput,encoder_multiply)
            PSO_SetupAerotech(motor,speed_PV.value,delta_PV.value,
                                start_PV.value,end_PV.value,asynRec,axis,PSOInput,encoder_multiply)
            fopen_A_shutter()
            PSO_setup_busy_PV.value = 0
            time.sleep(0.05)
        elif cleanup_busy_PV.value == 1:
            PSO_Cleanup(motor,asynRec,axis,retrace_PV.value)
            fclose_A_shutter()
            cleanup_busy_PV.value = 0
            time.sleep(0.05)
        if scan_setup_busy_PV.value == 1:
            PSO_SetupScan_Imaging(motor,trig_root,scan,speed_PV.value,delta_PV.value,
                                start_PV.value,end_PV.value)
            scan_setup_busy_PV.value = 0
        if counter == 10000:
            print "Looking for busys at time " + time.strftime('%H:%M:%S',time.localtime())
            counter = 0
        else:
            counter += 1
        time.sleep(0.001)

def PSO_Monitor_Daemon_Tomo_Fly(setup_busy='7bmb1:busy1',cleanup_busy='7bmb1:busy2',scan_setup_busy='7bmb1:busy3',
                                motor='7bmb1:aero:m3',trig_root = '7bm_pg1:',scan='7bmb1:scan1',
                                asynRec='7bmb1:PSOFly3:cmdWriteRead',axis='A', PSOInput=3,encoder_multiply=float(2**15)/0.36):
    '''Does PSO_Monitor_Daemon for tomography fly scans.
    '''
    PSO_setup_busy_PV = epics.PV(setup_busy)
    cleanup_busy_PV = epics.PV(cleanup_busy)
    scan_setup_busy_PV = epics.PV(scan_setup_busy)
    speed_PV = epics.PV('7bmb1:var:float1')
    delta_PV = epics.PV('7bmb1:var:float2')
    start_PV = epics.PV('7bmb1:var:float3')
    end_PV = epics.PV('7bmb1:var:float4')
    retrace_PV = epics.PV('7bmb1:var:float5')
    HDF_capture_PV = epics.PV(trig_root+'HDF1:Capture')
    counter = 0
    while True:
        if PSO_setup_busy_PV.value == 1:        #Set up Aerotech
            #Check if the HDF writer is in capture mode.
            if HDF_capture_PV.get() == 1:
                #Stop the capture.  If we don't here, we will crash the camera soft IOC.
                HDF_capture_PV.put(0,wait=True)
            #Check if we have any array data.  If not, get it.
            if int(epics.caget(trig_root + 'HDF1:ArraySize0_RBV')) == 0:
                #Set outselves to internal trigger, single trigger.
                epics.caput(trig_root + 'cam1:TriggerMode',0,wait=True)
                epics.caput(trig_root + 'cam1:ImageMode',0,wait=True)
                epics.caput(trig_root + 'cam1:Acquire',1,wait=True)

            #Do this twice, because for whatever reason it sometimes doesn't work the first time
            PSO_SetupAerotech(motor,speed_PV.value,delta_PV.value,
                                start_PV.value,end_PV.value,asynRec,axis,PSOInput,encoder_multiply)
            PSO_SetupAerotech(motor,speed_PV.value,delta_PV.value,
                                start_PV.value,end_PV.value,asynRec,axis,PSOInput,encoder_multiply)
            fopen_A_shutter()
            time.sleep(0.5)
            #Set up the HDF plugin to stream images to HDF5.
            epics.caput(trig_root+'HDF1:FileWriteMode',2,wait=True)
            epics.caput(trig_root+'HDF1:AutoSave',1,wait=True)
            num_images = int(epics.caget(trig_root+'cam1:NumImages'))
            epics.caput(trig_root+'HDF1:NumCapture',num_images,wait=True)
            epics.caput(trig_root+'HDF1:ExtraDimSizeN',num_images,wait=True)

            #Make sure camera is on external trigger mode and started.
            epics.caput(trig_root+'cam1:ImageMode',1,wait=True)
            epics.caput(trig_root+'cam1:TriggerMode',3,wait=True)
            time.sleep(0.2)
            epics.caput(trig_root+'HDF1:Capture',1,wait=False)
            PSO_setup_busy_PV.value = 0
            time.sleep(0.2)
        elif cleanup_busy_PV.value == 1:
            PSO_Cleanup(motor,asynRec,axis,retrace_PV.value)
            fclose_A_shutter()
            epics.caput('7bmb1:aero:m3.VAL',0)
            cleanup_busy_PV.value = 0
            time.sleep(0.05)
        if scan_setup_busy_PV.value == 1:
            PSO_SetupScan_Imaging(motor,trig_root+'cam1',scan,speed_PV.value,delta_PV.value,
                                start_PV.value,end_PV.value)
            scan_setup_busy_PV.value = 0
            time.sleep(0.05)
        if counter == 10000:
            print "Looking for busys at time " + time.strftime('%H:%M:%S',time.localtime())
            counter = 0
        else:
            counter += 1
        time.sleep(0.001)

def Fly_Scan_Script(trigger_busy = '7bmb1:busy5',setup_busy='7bmb1:busy1',cleanup_busy='7bmb1:busy2',scan_setup_busy='7bmb1:busy3',
                    trigger_PVs={'7bm_pg1:cam1:Acquire':1},motor='7bmb1:aero:m3',scan='7bmb1:scan1',cam_root = '7bm_pg1:'):
    '''Script to replicate the action of the scan record for fly tomo scans.
    '''
    #Important variables
    trigger_busy_PV = epics.PV(trigger_busy)
    PSO_setup_busy_PV = epics.PV(setup_busy)
    cleanup_busy_PV = epics.PV(cleanup_busy)
    scan_setup_busy_PV = epics.PV(scan_setup_busy)
    speed_PV = epics.PV('7bmb1:var:float1')
    delta_PV = epics.PV('7bmb1:var:float2')
    start_PV = epics.PV('7bmb1:var:float3')
    end_PV = epics.PV('7bmb1:var:float4')
    #Make PV objects from the trigger PVs
    trig_pv_dict = {}
    for key in trigger_PVs.keys():
        trig_pv_dict[key] = epics.PV(key)
    counter = 0
    try:
        #Loop to check for starting a scan.
        while True:
            #If we are starting a scan ...
            if trigger_busy_PV.value == 1:
                #Trigger the scan setup routine
                scan_setup_busy_PV.put(1,wait=True)
                #Compute how long this should take
                total_time = (end_PV.value - start_PV.value) / speed_PV.value
                print("Scan should take {:5.2f} s.".format(total_time))
                #Trigger the PSO_setup_busy button
                PSO_setup_busy_PV.put(1,wait=True)
                #Trigger the PVs we want to trigger
                for key,value in trigger_PVs.items():
                    trig_pv_dict[key].put(value)
                #Trigger the stage to move
                final_motor_position = epics.caget(scan+'.P1EP')
                epics.caput(motor+'.VAL',final_motor_position)
                start_time = time.time()
                #Now, start looking at whether we've finished or have aborted.
                counter = 0
                time.sleep(1.0)
                while (time.time() - start_time) < total_time * 1.5 + 3.0:
                    counter += 1                
                    if trigger_busy_PV.value == 0:
                        print("Aborting scan.")
                        #Stop the image acquisition
                        epics.caput(cam_root + 'cam1:Acquire',0,wait=True)
                        epics.caput(cam_root + 'HDF1:Capture',0,wait=True)
                        #Stop the motor
                        epics.caput(motor + '.SPMG',0,wait=True)
                        time.sleep(0.2)
                        epics.caput(motor + '.SPMG',3,wait=True)
                        #Break so we can clean up
                        break
                    trigger_pv_value_sum = 0
                    for key in trigger_PVs.keys():
                        trigger_pv_value_sum += trig_pv_dict[key].value
                    if not trigger_pv_value_sum:
                        print("Finished all triggers.")
                        break
                    else:
                        if counter % 5 == 0:
                            print("Elapsed time = {:5.2f} s.".format(time.time() - start_time))   
                        time.sleep(1.0)
                else:
                    print("Never finished images in time.  Error!")
                    #Stop the image acquisition
                    epics.caput(cam_root + 'cam1:Acquire',0,wait=True)
                    epics.caput(cam_root + 'HDF1:Capture',0,wait=True)
                #Trigger the cleanup 
                print("Cleaning up the scan.")
                cleanup_busy_PV.put(1,wait=True)
                time.sleep(0.5)
                print(trigger_busy_PV.value)
                trigger_busy_PV.put('Done',wait=True)
                time.sleep(0.5)
                print(trigger_busy_PV.value)
            time.sleep(0.05)
    finally:
        fclose_A_shutter()
            
            
    
def Pilatus_Monitor_Daemon(setup_busy='7bmb1:busy1'):
    '''Does PSO_Monitor_Daemon for tomography fly scans.
    '''
    setup_busy_PV = epics.PV(setup_busy)
    counter = 0
    while True:
        if setup_busy_PV.value == 1:
            #Set the correct file name
            file_num = int(epics.caget('7bmb1:saveData_scanNumber')) - 1
            epics.caput('s7_pilatus:cam1:FileName','Scan_{0:04d}'.format(file_num),wait=True)
            #Set us back to image # 0
            epics.caput('s7_pilatus:cam1:FileNumber',0,wait=True)
            #Sync the exposure time of the Pilatus to the count time of the scaler board.
            exposure_time = float(epics.caget('s7_pilatus:cam1:AcquireTime'))
            epics.caput('7bmb1:3820:scaler1.TP',exposure_time,wait=True)
        
            
            time.sleep(0.2)
            setup_busy_PV.value = 0
            counter = 0
            time.sleep(0.2)
        if counter == 1000:
            print "Looking for busys at time " + time.strftime('%H:%M:%S',time.localtime())
            counter = 0
        else:
            counter += 1
        time.sleep(0.01)
            

def fnorm_v_mirror_translation(new_value=0):
    for i in [41,44]:
        prefix = '7bmb1:m' + str(i)
        epics.caput(prefix + '.FOFF',0,wait=True,timeout=10.0)
        time.sleep(0.05)
        epics.caput(prefix + '.SET',1,wait=True,timeout=10.0)
        time.sleep(0.05)
        epics.caput(prefix + '.VAL',new_value,wait=True,timeout=10.0)
        time.sleep(0.05)
        epics.caput(prefix + '.SET',0,wait=True,timeout=10.0)
        time.sleep(0.05)
        epics.caput(prefix + '.FOFF',1,wait=True,timeout=10.0)
        time.sleep(0.05)

def fnorm_h_mirror_translation(new_value=0):
    for i in [45,48]:
        prefix = '7bmb1:m' + str(i)
        epics.caput(prefix + '.FOFF',0,wait=True,timeout=10.0)
        time.sleep(0.05)
        epics.caput(prefix + '.SET',1,wait=True,timeout=10.0)
        time.sleep(0.05)
        epics.caput(prefix + '.VAL',new_value,wait=True,timeout=10.0)
        time.sleep(0.05)
        epics.caput(prefix + '.SET',0,wait=True,timeout=10.0)
        time.sleep(0.05)
        epics.caput(prefix + '.FOFF',1,wait=True,timeout=10.0)
        time.sleep(0.05)

def fnorm_slits(existing_center=True,blades=[61,62]):
    '''Calibrates the vertical slit opening for JJ slits.
    
    Sets both blades to the same value.
    Maintains dial value, so use of dial coordinates for an absolute
    reference isn't messed up.
    
    Inputs:
    existing_center: if True, set .VAL to average of existing values.
                    If False, set to 0.
    blades: numbers of slit blade motors.
    '''
    #Make list of epics.Motor objects of the two blades
    blade_motors = [epics.Motor('7bmb1:m'+str(x)) for x in blades]
    #Get current positions and figure out final positions.
    current_positions = [x.get_position() for x in blade_motors]
    final_position = 0.0
    if existing_center:
        final_position = sum(current_positions) / float(len(blade_motors))
    #For each motor, change the user drive field without changing dial 
    for mot in blade_motors:
        #Make the offset between user and dial variable
        if mot.FOFF:
            mot.FOFF = 0
        mot.SET = 1
        mot.drive = final_position
        mot.SET = 0
    logging.info("Slit blades normalized.")

def fnorm_slits_v(existing_center=True):
    fnorm_slits(existing_center,[61,62])
    epics.caput('7bmb1:Slit4Vsync.PROC',1)
    
def fnorm_slits_h(existing_center=True):
    fnorm_slits(existing_center,[63,64])
    epics.caput('7bmb1:Slit4Hsync.PROC',1)

def fnorm_detector():
    '''Sets the detector x and y stages to 0 in user coordinates.
    '''
    fnorm_slits(False,[5,6])

def fmove_to_imaging():
    detector_x = epics.Motor('7bmb1:m5')
    detector_y = epics.Motor('7bmb1:m6')
    detector_x.move(49,relative=True)
    detector_y.move(-2.7,relative=True)
    
def fmove_to_PIN():
    detector_x = epics.Motor('7bmb1:m5')
    detector_y = epics.Motor('7bmb1:m6')
    detector_x.move(-49,relative=True)
    detector_y.move(2.7,relative=True)

def fadjust_mirror_table():
    '''Adjusts for the tilt of the doubly reflected beam from the mono.
    
    Baseline for zero position is both crystals at the same angle at 
    25 mm vertical offset.
    '''
    propagation_dist = 5.75     #m
    #Find mono crystal angles in degrees
    theta_1 = np.radians(epics.caget('7bma1:m4.VAL'))
    theta_2 = np.radians(epics.caget('7bma1:m12.VAL'))
    #Compute the angle of the beam and the shift caused by it
    beam_angle = 2 * (theta_2 - theta_1)
    print("Beam angle = " + str(beam_angle * 1000.0) + " mrad." )
    print("Beam angle = " + str(np.rad2deg(beam_angle)) + " deg." )
    vert_shift_angle = np.tan(beam_angle) * propagation_dist * 1000.0
    print("Vertical shift due to angle is " + str(vert_shift_angle) + " mm.")
    #Find the vertical shift caused by changing the crystal offset.
    #Compute vertical offset of the crystals.
    y_offset = epics.caget('7bma1:m8.VAL') - epics.caget('7bma1:m2.VAL')
    #Find the z offset in mm
    z_offset = epics.caget('7bma1:m9.VAL')
    #Find the y offset: solving system of two equations in (z,y) for y
    x_shift = (1.0 /(np.tan(2*theta_1) - np.tan(theta_2))
                    * (y_offset - np.tan(theta_2) * z_offset))
    print(x_shift)
    y_beam_crystal2 = (np.tan(2*theta_1)/(np.tan(2*theta_1) - np.tan(theta_2))
                       *(y_offset - np.tan(theta_2) * z_offset))
    print("Y position of beam on crystal 2 = " + str(y_beam_crystal2) + " mm.")
    vert_shift_pos = y_beam_crystal2 - 25.0
    print("The vertical shift due to reflection position = " + str(vert_shift_pos) + " mm.")
    total_vert_shift = vert_shift_angle + vert_shift_pos + 25.0
    print("The desired table vertical position  = " + str(total_vert_shift) + " mm.")
    
def fprep_for_alignment():
    '''Prepares several motors for alignment.
    '''
    #Make sure all flags are out of the beam.
    epics.caput('7bma1:m13.VAL',55.0)
    epics.caput('7bma1:m14.VAL',50.0)
    #Remove all WB filters.
    epics.caput('7bma1:m15.VAL',0.7)
    epics.caput('7bma1:m16.VAL',0.7)
    #Move the alignment PIN into position.
    epics.caput('7bmb1:m7.VAL',0.0,wait=True)
    #Move the table to the right y.
    fadjust_mirror_table()
    #Open the slits in the y direction.
    epics.caput('7bmb1:Slit4Vsize.VAL',15.0,wait=True)
    #Are we already at zero angle, or nearly so
    #If so, we are probably already out of the beam.
    offset_v_pos = 0.0
    if abs(epics.caget('7bmb1:m41.VAL') 
            - epics.caget('7bmb1:m44.VAL')) > 0.2:
        offset_v_pos = 1.0
    offset_h_pos = 0.0
    if abs(epics.caget('7bmb1:m45.VAL') 
            - epics.caget('7bmb1:m48.VAL')) > 0.2:
        offset_h_pos = 1.0
    
    #Flatten the mirrors and make the angles zero, move out of beam.
    v_mirror_average = (epics.caget('7bmb1:m41.VAL') 
                        + epics.caget('7bmb1:m44.VAL')) / 2.0
    h_mirror_average = (epics.caget('7bmb1:m45.VAL') 
                        + epics.caget('7bmb1:m48.VAL')) / 2.0
    epics.caput('7bmb1:m41.VAL',v_mirror_average - offset_v_pos)
    epics.caput('7bmb1:m44.VAL',v_mirror_average - offset_v_pos)
    epics.caput('7bmb1:m45.VAL',h_mirror_average - offset_h_pos)
    epics.caput('7bmb1:m48.VAL',h_mirror_average - offset_h_pos)
    for i in [42,43,46,47]:
        epics.caput('7bmb1:m'+str(i)+'.VAL',0.0)

def fcompute_Compton_energy(incident_keV,angle=90):
    '''Computes the energy of the Compton scattering.

    Inputs:
    incident_keV: incident photon energy in keV
    angle: observation angle in degrees
    '''
    Compton_wavelength = 2.43e-2 #angstroms, from Wikipedia
    E_to_angstroms = 12.398 #angstrom-keV
    return E_to_angstroms / (E_to_angstroms / incident_keV 
                            + Compton_wavelength * (1 - np.cos(np.radians(angle))))

def fcompute_energy_Si220(input_angle_deg,order=1):
    '''Computes the diffraction energy for Si(220) given angle in deg.
    
    Inputs:
    input_angle_deg: angle of crystal to beam in degrees
    order: order of diffraction
    Output:
    Energy of x-ray beam in keV.
    '''
    return fcompute_energy_Bragg(input_angle_deg,order,3.8403)

def fcompute_energy_Bragg(input_angle_deg,order,crystal_2d):
    '''Computes the diffraction energy for a crystal given angle in deg.
    
    Inputs:
    input_angle_deg: angle of crystal to beam in degrees
    order: order of diffraction
    crystal_2d: crystal 2d spacing.
    Output:
    Energy of x-ray beam in keV.
    '''
    return 12.398 * order / crystal_2d / np.sin(np.radians(input_angle_deg))

def fprep_for_tomo_alignment():
    '''Prepares the data acquisition to look at sample.
    '''
    #Turn off image saving
    epics.caput('7bmPG1:HDF1:Capture',0,wait=True)
    time.sleep(0.1)
    epics.caput('7bmPG1:HDF1:AutoSave',0,wait=True)
    time.sleep(0.1)
    #Set the camera to internal trigger, Continuous trigger mode
    epics.caput('7bmPG1:cam1:TriggerMode',0,wait=True)
    time.sleep(0.1)
    epics.caput('7bmPG1:cam1:ImageMode',2,wait=True)
    time.sleep(0.1)
    #Start taking images
    epics.caput('7bmPG1:cam1:Acquire',1, wait=False)
        
if __name__ == '__main__':
    bob = epics.PV('S:SRcurrentAI.VAL')
    print(bob.value)
    print(A_shutter_closed_PV.value)

