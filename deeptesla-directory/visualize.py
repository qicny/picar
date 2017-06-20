#!/usr/bin/env python
from __future__ import division

import subprocess as sp
import os
import io
import sys
import re
from copy import deepcopy
import psycopg2
import psycopg2.extras
import subprocess
from operator import itemgetter
from collections import OrderedDict, Counter
import cv2
from fractions import Fraction
import csv
import errno
import time
import shutil
import numpy as np
import datetime
import matplotlib.pyplot as plt
import PIL
from pprint import pprint
import multiprocessing
import string
import copy
import json
import random
import params
import Image
import ImageDraw
import ImageFont

import local_common as cm

MAX_ANGLE = params.maxAngle #Value used to adjust steering angles and statistics, they would otherwise be between -1 and 1
HUMAN_MAX_ANGLE = params.maxAngle
CSV_HEADER = 'angle'

if params.givenData: #If using the given deep tesla data
    HUMAN_MAX_ANGLE = 1 #Set max angle to 1, this way the actual angles aren't affected
    CSV_HEADER = 'wheel'

def get_human_steering(epoch_id):
    epoch_dir = params.data_dir
    assert os.path.isdir(epoch_dir)
    if not params.givenData:
        steering_path = "datasets/dataset%i/data.csv" % epoch_id 
    else:
        steering_path = cm.jn(epoch_dir, 'epoch{:0>2}_steering.csv'.format(epoch_id))
    assert os.path.isfile(steering_path)
    
    rows = cm.fetch_csv_data(steering_path)
    human_steering = [row[CSV_HEADER] for row in rows]
    return human_steering

def visualize(epoch_id, machine_steering, out_dir, timeArr, perform_smoothing=False,
              verbose=False, verbose_progress_step = 100, frame_count_limit = None):
    epoch_dir = params.data_dir
    human_steering = get_human_steering(epoch_id)
    assert len(human_steering) == len(machine_steering)

    # testing: artificially magnify steering to test steering wheel visualization
    # human_steering = list(np.array(human_steering) * 10)
    # machine_steering = list(np.array(machine_steering) * 10)

    # testing: artificially alter machine steering to test that the disagreement coloring is working
    # delta = 0
    # for i in xrange(len(machine_steering)):
    #     delta += random.uniform(-1, 1)
    #     machine_steering[i] += delta
    
    if perform_smoothing:
        machine_steering = list(cm.smooth(np.array(machine_steering)))
        #human_steering = list(cm.smooth(np.array(human_steering)))

    steering_min = min(np.min(human_steering) * HUMAN_MAX_ANGLE, np.min(machine_steering) * MAX_ANGLE)
    steering_max = max(np.max(human_steering) * HUMAN_MAX_ANGLE, np.max(machine_steering) * MAX_ANGLE)

    assert os.path.isdir(epoch_dir)

    if not params.givenData:
        front_vid_path = "datasets/dataset{0}/out-mencoder2.avi".format(epoch_id)
    else:
        front_vid_path = cm.jn(epoch_dir, 'epoch{:0>2}_front.mkv'.format(epoch_id))
    assert os.path.isfile(front_vid_path)
    
    dash_vid_path = cm.jn(epoch_dir, 'epoch{:0>2}_dash.mkv'.format(epoch_id))
    dash_exists = os.path.isfile(dash_vid_path)

    front_cap = cv2.VideoCapture(front_vid_path)
    dash_cap = cv2.VideoCapture(dash_vid_path) if dash_exists else None
    
    assert os.path.isdir(out_dir)
    vid_size = cm.video_resolution_to_size('720p', width_first=True)
    out_path = cm.jn(out_dir, 'epoch{:0>2}_human_machine.mkv'.format(epoch_id))
    vw = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*'X264' ), 30, vid_size)
    w, h = vid_size

    totalError = 0 #Holds the sum of all errors, used tocalculate the average error for each frame
    errorArr = [] #Holds the individual errors, used to calculate standard deviation for each frame

    for f_cur in xrange(len(machine_steering)):
        if (f_cur != 0) and (f_cur % verbose_progress_step == 0):
            print 'completed {} of {} frames'.format(f_cur, len(machine_steering))

        if (frame_count_limit is not None) and (f_cur >= frame_count_limit):
            break
            
        rret, rimg = front_cap.read()
        assert rret

        if dash_exists:
            dret, dimg = dash_cap.read()
            assert dret
        else:
            dimg = rimg.copy()
            dimg[:] = (0, 0, 0)
        
        ry0, rh = 80, 500
        dimg = dimg[100:, :930]
        dimg = cm.cv2_resize_by_height(dimg, h-rh)

        fimg = rimg.copy()
        fimg[:] = (0, 0, 0)
        fimg[:rh] = rimg[ry0:ry0+rh]
        dh, dw = dimg.shape[:2]
        fimg[rh:,:dw] = dimg[:]
        
        ########################## plot ##########################
        plot_size = (500, dh)
        win_before, win_after = 150, 150

        xx, hh, mm = [], [], []
        for f_rel in xrange(-win_before, win_after+1):
            f_abs = f_cur + f_rel
            if f_abs < 0 or f_abs >= len(machine_steering):
                continue
            xx.append(f_rel/30)
            hh.append(human_steering[f_abs] * HUMAN_MAX_ANGLE)
            mm.append(machine_steering[f_abs] * MAX_ANGLE)

        fig = plt.figure()
        axis = fig.add_subplot(1, 1, 1)

        steering_range = max(abs(steering_min), abs(steering_max))
        #ylim = [steering_min, steering_max]
        ylim = [-steering_range, steering_range]
        # ylim[0] = min(np.min(hh), np.min(mm))
        # ylim[1] = max(np.max(hh), np.max(mm))
        
        axis.set_xlabel('Current Time (secs)')
        axis.set_ylabel('Steering Angle')
        axis.axvline(x=0, color='k', ls='dashed')
        axis.plot(xx, hh)
        axis.plot(xx, mm)
        axis.set_xlim([-win_before/30, win_after/30])
        axis.set_ylim(ylim)
        #axis.set_ylabel(y_label, fontsize=18)
        axis.label_outer()
        #axes.append(axis)

        buf = io.BytesIO()
        # http://stackoverflow.com/a/4306340/627517
        sx, sy = plot_size
        sx, sy = round(sx / 100, 1), round(sy / 100, 1)

        fig.set_size_inches(sx, sy)
        fig.tight_layout()
        fig.savefig(buf, format="png", dpi=100)
        buf.seek(0)
        buf_img = PIL.Image.open(buf)
        pimg = np.asarray(buf_img)
        plt.close(fig)

        pimg = cv2.resize(pimg, plot_size)
        pimg = pimg[:,:,:3]

        ph, pw = pimg.shape[:2]
        pimg = 255 - pimg
        
        fimg[rh:,-pw:] = pimg[:]

        ####################### human steering wheels ######################
        wimg = cm.imread(os.path.abspath("images/wheel-tesla-image-150.png"), cv2.IMREAD_UNCHANGED)

        human_wimg = cm.rotate_image(wimg, (human_steering[f_cur] * HUMAN_MAX_ANGLE))
        wh, ww = human_wimg.shape[:2]
        fimg = cm.overlay_image(fimg, human_wimg, y_offset = rh+50, x_offset = dw+60)

        ####################### machine steering wheels ######################
        disagreement = abs((machine_steering[f_cur] * MAX_ANGLE) - (human_steering[f_cur] * HUMAN_MAX_ANGLE))
        machine_wimg = cm.rotate_image(wimg, (machine_steering[f_cur] * MAX_ANGLE))
        red_machine_wimg = machine_wimg.copy()
        green_machine_wimg = machine_wimg.copy()
        red_machine_wimg[:,:,2] = 255
        green_machine_wimg[:,:,1] = 255
        #r = disagreement / (steering_max - steering_min)
        max_disagreement = 10
        r = min(1., disagreement / max_disagreement)
        g = 1 - r
        assert r >= 0
        assert g <= 1
        machine_wimg = cv2.addWeighted(red_machine_wimg, r, green_machine_wimg, g, 0)
        wh, ww = machine_wimg.shape[:2]
        fimg = cm.overlay_image(fimg, machine_wimg, y_offset = rh+50, x_offset = dw+260)
        
        ####################### text ######################
        timg_green_agree = cm.imread(os.path.abspath("images/text-green-agree.png"), cv2.IMREAD_UNCHANGED)
        timg_ground_truth = cm.imread(os.path.abspath("images/text-ground-truth.png"), cv2.IMREAD_UNCHANGED)
        timg_learned_control = cm.imread(os.path.abspath("images/text-learned-control.png"), cv2.IMREAD_UNCHANGED)
        timg_red_disagree = cm.imread(os.path.abspath("images/text-red-disagree.png"), cv2.IMREAD_UNCHANGED)
        timg_tesla_control_autopilot = cm.imread(os.path.abspath("images/text-tesla-control-autopilot.png"), cv2.IMREAD_UNCHANGED)
        timg_tesla_control_human = cm.imread(os.path.abspath("images/text-tesla-control-human.png"), cv2.IMREAD_UNCHANGED)

        textColor = (255,255,255) #Declare the color for the new image background
        bgColor = (0,0,0) #Declare the color for the new image text
        newImage = Image.new('RGBA', (300, 200), bgColor) #Create blank canvas for metrics
        drawer = ImageDraw.Draw(newImage) #Create ImageDraw for drawing the metrics

        error = abs((human_steering[f_cur]*HUMAN_MAX_ANGLE) - (machine_steering[f_cur]*MAX_ANGLE)) #calculate the error for the current frame
        totalError += error #Add the current error to the total error
        errorArr.append(error) #Add the current error to the error array

        stdDev = np.std(errorArr) #Calculate the standard deviation as of the current frame
        avgError = totalError / (f_cur + 1) #Calculate the average error as of the current frame
        

        # % (timeArr[f_cur] * 1000)

        drawer.text((10, 10), "Frame #%i" % f_cur, fill=textColor) #Print the frame number
        drawer.text((150, 10), "Time to get angle: %i ms" % (timeArr[f_cur] * 1000), fill=textColor) #Print the forward pass in milliseconds
        drawer.text((10,30), "Angles:", fill=textColor) #Print the steering angles
        drawer.text((10,40), "Acutal: %.3f" % (human_steering[f_cur] * HUMAN_MAX_ANGLE), fill = textColor) #Print the actual steering angle
        drawer.text((150,40), "Predicted: %.3f" % (machine_steering[f_cur]* MAX_ANGLE), fill = textColor) #Print the predicted steering angle
        drawer.text((10,60), "Error: %.3f" % (error), fill=textColor) #Print the error for the current frame
        drawer.text((150,60), "Average error: %.3f" % (avgError), fill=textColor) #Print the average error as of the current frame
        drawer.text((10,70), "Standard Deviation: %.3f" % (stdDev), fill=textColor) #Print the standard deviation as of the current frame

        # timg_ = cm.imread(os.path.abspath("images/text-.png"), cv2.IMREAD_UNCHANGED)

        #timg_test2 = cm.imread(timg_test, cv2.IMREAD_UNCHANGED)
        newImage.save("images/stats.png")
        timg_stats = cm.imread(os.path.abspath("images/stats.png"), cv2.IMREAD_UNCHANGED)

        fimg = cm.overlay_image(fimg, timg_tesla_control_autopilot, y_offset = rh+8, x_offset = dw+83)
        fimg = cm.overlay_image(fimg, timg_learned_control, y_offset = rh+8, x_offset = dw+256)
        fimg = cm.overlay_image(fimg, timg_ground_truth, y_offset = rh+205, x_offset = dw+90)
        fimg = cm.overlay_image(fimg, timg_red_disagree, y_offset = rh+205, x_offset = dw+230)
        fimg = cm.overlay_image(fimg, timg_green_agree, y_offset = rh+205, x_offset = dw+345)
        fimg = cm.overlay_image(fimg, timg_stats, y_offset = rh, x_offset=0) #Draw the metrics to the screen
        #fimg = cm.overlay_image(fimg, timg_work, y_offset = 0, x_offset = 0)

        if (frame_count_limit is not None) and (frame_count_limit == 1):
            cv2.imwrite(out_path.replace('mkv', 'jpg'), fimg)
            sys.exit()

        vw.write(fimg)

    front_cap.release()
    if dash_exists:
        dash_cap.release()
    vw.release()

    cm.mkv_to_mp4(out_path, remove_mkv=True)
    

        
if __name__ == '__main__':
    epoch_id = 1
    machine_steering = get_human_steering(epoch_id)

    # frame_count_limit = None
    # frame_count_limit = 30 * 5
    # frame_count_limit = 1
    visualize(epoch_id, machine_steering, params.out_dir,
              verbose=True, frame_count_limit=150)

    
