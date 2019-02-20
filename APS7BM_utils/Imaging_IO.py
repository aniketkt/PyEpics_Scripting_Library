#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct  9 13:12:38 2018
@author: atekawade
"""

import glob
import os
import sys
import pandas as pd
import re
import time

loop_wait = 1.00


def get_NextImDir(Stacks_Dir, first_dir = "NozzleTomoG16_S0001", SeqNum_pos = -1, prefix = 'S', prev_dir = ''):
    
    df_ImDir = get_DatedImDirList(Stacks_Dir)

    if len(df_ImDir['Path']) == 0:
        NextImDir = os.path.join(Stacks_Dir,first_dir)

    else:
        prev_dir = df_ImDir.iloc[-1]['Path'] if prev_dir == '' else prev_dir
        SeqNum = re.findall(r'\d+',prev_dir.split('_')[SeqNum_pos])
        SeqNum = str(int(SeqNum[0]) + 1).zfill(len(SeqNum[0]))
        
        next_dir = prev_dir.split('_')
        next_dir[SeqNum_pos] = prefix + SeqNum
        
        NextImDir = '_'.join(next_dir)
    
    print("\nNext image directory name will be:\n%s"%(os.path.basename(os.path.normpath(NextImDir))))
    return NextImDir

def get_NextImg(Img_Dir, SeqNum_pos = -1, first_img = '', prefix = 'S'):
    
    df_ImList = get_ImList(Img_Dir)
    if len(df_ImList['Path']) == 0:
        NextImg = os.path.join(Img_Dir,first_img)

    else:
        LastImg = df_ImList.iloc[-1]['Path'].split('.')[0]
        SeqNum = re.findall(r'\d+',LastImg.split('_')[SeqNum_pos])
        SeqNum = str(int(SeqNum[0]) + 1).zfill(len(SeqNum[0]))
        
        new_name = LastImg.split('_')
        new_name[SeqNum_pos] = prefix + SeqNum
        
        NextImg = '_'.join(new_name)
    
    print("\nNext image: %s,"%(os.path.basename(os.path.normpath(NextImg)))),
    return NextImg


def get_ImList(Img_Dir):
    ImgFileList = sorted(glob.glob(Img_Dir+'/*.tif'))
    ImgNames = [os.path.basename(os.path.normpath(Img)) for Img in ImgFileList]
    DateModified = [os.path.getmtime(Img) for Img in ImgFileList]
    df = pd.DataFrame(columns = ['Path', 'Date Modified'], index = ImgNames)
    df['Path'] = ImgFileList
    df['Date Modified'] = DateModified
    df = df.sort_values(by = 'Date Modified')
    return df   


def get_ImDirList(Stacks_Dir):

    Stacks_Dir = Stacks_Dir + '/*/'
    ImDirList = glob.glob(Stacks_Dir)

    ImDirNames = [os.path.basename(os.path.normpath(ImDir)) for ImDir in ImDirList]
    
    ImDirList = pd.Series(data = ImDirList, index = ImDirNames)
    
    return ImDirList


def get_DatedImDirList(Stacks_Dir):

    Stacks_Dir = Stacks_Dir + '/*/'
    ImDirList = glob.glob(Stacks_Dir)

    ImDirNames = [os.path.basename(os.path.normpath(ImDir)) for ImDir in ImDirList]
    DateModified = [os.path.getmtime(ImDir) for ImDir in ImDirList]
    
    df_ImDir = pd.DataFrame(columns = ['Path', 'Date Modified'], index = ImDirNames)
    df_ImDir['Path'] = ImDirList
    df_ImDir['Date Modified'] = DateModified
    df_ImDir = df_ImDir.sort_values(by = 'Date Modified')

    return df_ImDir




def is_AllFilesSaved(ImDirPath, nFrames):

    ImDirName = os.path.basename(os.path.normpath(ImDirPath))
    LastFileName = os.path.join(ImDirPath, ImDirName) + str(nFrames).zfill(len(str(nFrames))) + '.tif'
    n_TIF = len(glob.glob(os.path.join(ImDirPath, '*.tif')))
    return os.path.exists(LastFileName) and (n_TIF == nFrames)





def is_NextImDirCreated(NextImDir, timeout = 60000000.0):

    t0 = time.time()
    timeout_flag = False
    while not os.path.exists(NextImDir):
        time.sleep(loop_wait)
        if time.time() - t0 > timeout:
            timeout_flag = True
            break
        pass

    if timeout_flag:
        return False

    else:
        return True

def wait_forSaveComplete(NextImDir = '', nFrames = 0, timeout = 600000000.0):

    t0 = time.time()
    timeout_flag = False
    while not is_AllFilesSaved(NextImDir, nFrames):        
        time.sleep(loop_wait)
        if time.time() - t0 > timeout:
            timeout_flag = True
            break
        pass

    if timeout_flag:
        return False

    else:
        return True

def write_toLog(message, LogFileName = ""):
    
    if LogFileName != "":
        if os.path.exists(LogFileName):
            with open(LogFileName, "a") as LogFile:
                LogFile.write(message)
        else:
            with open(LogFileName, "w") as LogFile:
                LogFile.write(message)
        return True
    
    else:
        print("ERROR: Log file name not entered!")
        return False
    




