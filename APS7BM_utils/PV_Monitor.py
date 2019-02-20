#!/usr/bin/env python
'''Module for monitoring PVs and displaying stats to the terminal.

This is based heavily on a script written by Daniel Duke in 2015 for
monitoring PVs during scans for the fuel spray project.
The main changes in this module are making it a module, rather 
than a stand-alone script.

Alan Kastengren, XSD, APS
Started: January 30, 2017
'''
#Imports
import epics
import time
import sys
import termcolor
import colorama

# Reporting interval and poll time in s.
_print_interval = 5    #Time = _print_interval * _poll_time
_poll_time = 1
_header_interval = 5   #Time = _print_interval * _poll_time * _header_interval

#Globals to store names of monitored PVs and limits
stored_PV_names = []
stored_PV_desc = []
stored_PV_obj = []
high_limits = []
low_limits = []

#Globals giving PV to actuate and how to set it
active_PV = None
action_PV = None
pause_value = 1
resume_value = 0

#Initiate colorama
colorama.init()

def add_PV(pv_name,upper_limit,lower_limit):
    '''Add a PV to be monitored.
    
    Inputs:
    pv_name: name of the PV to be added to our monitor list
    upper_limit: value for PV at which alarm will occur
    lower_limit: value for PV at which alarm will occur
    '''
    #Append these data to the existing global lists
    stored_PV_names.append(pv_name)
    high_limits.append(upper_limit)
    low_limits.append(lower_limit)
    #Make PV objects and store them
    stored_PV_obj.append(epics.PV(pv_name+'.VAL'))
    #Try to find a description to add
    desc = epics.caget(pv_name+'.DESC')
    if desc:
        stored_PV_desc.append(desc)
    else:
        stored_PV_desc.append(pv_name)
    return

def start_monitoring():
    #Infinite loop
    try:
        i = 0   #Loop counter
        while True:
            #Set up a flag to see if we alarm on any PVs
            bad_value = False
            #If we aren't active, just bide our time
            if epics.caget(active_PV)==1:
                termcolor.cprint('Scan not running', 'yellow')
            else:
                #Check the values of all of the PVs being monitored
                for current_PV,high_lim,low_lim,current_desc in zip(
                        stored_PV_obj,high_limits,low_limits,stored_PV_desc):
                    #If limits are exceeded, print to terminal and 
                    if current_PV.value >= high_lim:
                        termcolor.cprint( '%s above set limit!' % current_desc , 
                                          'red' , attrs={'bold':True} )
                        bad_value = True
                    elif current_PV.value <= low_lim:
                        termcolor.cprint( '%s below set limit!' % current_desc , 
                                          'blue' , attrs={'bold':True} )
                        bad_value = True
                #Either pause or resume based on these results
                if bad_value:
                    epics.caput(action_PV,pause_value,wait=True)
                    termcolor.cprint("Scan paused!",'yellow')
                    sys.stdout.write('\a')
                else:
                    if epics.caget(action_PV) == pause_value:
                        epics.caput(action_PV,resume_value,wait=True)
                        termcolor.cprint("Scan resumed!",'green')
                        i == 0
   
            #Are we ready to print out the header info
            if not i % (_print_interval * _header_interval):
                print(80*'#')
                print("")
                header_line = '{:12s}'.format('Time')
                for desc in stored_PV_desc:
                    header_line += '{:16s}'.format(desc)
                termcolor.cprint(header_line,'grey')
            if not i % _print_interval:
                print_line = '{:12s}'.format(time.strftime("%H:%M:%S",time.localtime()))
                for current_PV in stored_PV_obj:
                    if abs(current_PV.value) > 1000 or abs(current_PV.value) < 0.01:
                        print_line += '{:<16.3e}'.format(current_PV.value)
                    else:
                        print_line += '{:<16.3f}'.format(current_PV.value)
                termcolor.cprint(print_line,'green')
            #Increment counter and sleep for _poll_interval seconds.
            i += 1
            time.sleep(_poll_time)
    except KeyboardInterrupt():
        print("Interrupted by keyboard")
        return
 