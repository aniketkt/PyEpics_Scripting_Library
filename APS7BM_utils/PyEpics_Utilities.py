'''Useful functions for PyEPICS scripting.

Alan Kastengren, XSD, APS

Started: February 13, 2015
'''
import epics
import numpy as np
import time
import math
import logging

#Global variables
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
    while not monitored_PV.put_complete:
        time.sleep(poll_time)
        #Run middle functions, in order
        for func,args in zip(middle_functions,middle_args):
            func(args)

def fmonitored_action(action_pv,readback_pv,action_value=1,desired_readback=1,
                      sleep_time=1.0,wait_time=30.):
    '''Perform an action and wait for it to complete by monitoring another PV.
    This is useful for beamline shutters in particular, since a put_complete
    doesn't work to monitor them.
    Inputs:
    action_pv: epics.PV object or string of a PV name that should be activated
    readback_pv: epics.PV object to monitor to see that action is complete
    action_value: value to put to action_pv
    desired_readback: value we desire on the readback
    sleep_time: time to sleep between polls of the readback_pv
    wait_time: time to wait until giving up
    '''
    #If this is already a PV object, just put a value to it.
    if isinstance(action_pv,epics.pv.PV):
        action_pv.put(action_value)
    #If it isn't already a PV, assume it's a string and just caput
    else:
        epics.caput(action_pv,action_value)
    while wait_time > 0:
        time.sleep(sleep_time)
        wait_time -= sleep_time
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
    manual_pause = action_PV and action_PV.value == bad_beam_value
    
    while fcheck_for_bad_beam() or manual_pause:
        #If we had a manual pause and the action_PV is at the good beam value,
        #the pause must have been rescinded.
        if action_PV.value == good_beam_value and manual_pause:
            print("Manual pause rescinded.")
            manual_pause = False
            time.sleep(1.0)
            continue
        #If not manually paused, check for whether good beam conditions exist.
        if not fcheck_for_bad_beam() and not manual_pause:
            print("Resuming operations.")
            #Unpause the scan if it is paused
            if action_PV and action_PV.value == bad_beam_value:
                action_PV.value = good_beam_value
            time.sleep(1.0)
            return
        else:
            #If the scan isn't paused yet, pause it.
            if action_PV and action_PV.value == good_beam_value:
                action_PV.value = bad_beam_value
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
                    print("Waiting for beam to come back at time " 
                          + time.strftime('%H:%M:%S',time.localtime()))
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
            print("Looking for repeated scan busy at time " + time.strftime('%H:%M:%S',time.localtime()))
            counter = 0
        else:
            counter += 1
        time.sleep(0.01)

def fautomated_repeated_scan_busy(trigger_busy='7bmb1:busy4',
                                  action_name='7bmb1:busy5',
                                  action_value='Busy',
                                  shutter='A'):
    '''Performs a repeated scan.
    '''
    repeated_scan_busy_PV = epics.PV(trigger_busy)
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
                        print("Waiting for beam to come back at time " 
                              + time.strftime('%H:%M:%S',time.localtime()))
                        time.sleep(5.0)
                    if shutter == 'A':
                        fopen_A_shutter()
                    else:
                        fopen_shutters()
                    #Start the scan
                    epics.caput(action_name,action_value)
                    time.sleep(1.0)
                    for t in range(int(sec_between_pts),0,-1):
                        #Check to make sure we haven't clicked "Done" on repeated_scan_busy to abort this.
                        print("Waiting for the next scan, {0:d} s left.".format(t))                        
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
        if shutter == 'A':
            fclose_A_shutter()
        else:
            fclose_B_shutter()

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

def finit_motor(motor_num,prefix='7bmb1:m',new_value=0,use_dial=True):
    '''Use to set the dial coordinate of a motor to zero.
    Specifically, do this without changing the user/dial offset, so this
    is suitable for using a limit switch as a home.
    Suitable for stepper motor stages.
    Inputs:
    motor_num: the number of the motor
    prefix: everything before the motor number to make a valid PV (default: 7bmb1:m)
    new_value: new value of the dial coordinate (default: 0)
    use_dial: do this in dial (default, True) or user coordinates
    '''
    motor_obj = epics.Motor(prefix+str(motor_num))
    #Freeze the offset
    motor_obj.freeze_offset = 1
    time.sleep(0.2)
    #Go into set mode
    motor_obj.set_position(new_value,dial=use_dial)
    time.sleep(0.2)
    #Unfreeze the offset
    motor_obj.freeze_offset = 0
    time.sleep(0.2)
    
def finit_slits(top=57,bottom=58,inside=59,outside=60,prefix='7bmb1:m',size=14):
    '''Initializes a set of slits that have been powered off.
    Sets all slit blades to their - limit, zeros the dial, and
    opens the slits fully.
    Inputs:
    top,bottom,inside,outside: numbers of appropriate motors
    prefix: PV prefix for the motors.
    size: fully open size on each side of zero.
    '''
    for motor_number in [top,bottom,inside,outside]:
        #Move the motor to a very negative position
        motor_obj = epics.Motor(prefix+str(motor_number))
        motor_obj.move(-size*3,wait=True)
        #Move + 1 mm, then back in small steps to more accurately hit limit
        motor_obj.move(1.0,relative=True,wait=True)
        hit_limit = 0
        while not hit_limit:
            hit_limit = motor_obj.move(-0.1,relative=True,wait=True)
        #Init motor
        finit_motor(motor_number,prefix=prefix)
        time.sleep(0.5)
        #Move the top and inside blades to open the slits
        if motor_number == top or motor_number == outside:
            motor_obj.move(0,wait=True)
            motor_obj.move(size,wait=True)

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

