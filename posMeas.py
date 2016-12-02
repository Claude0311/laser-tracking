#!/usr/bin/python3

import io
import time
import picamera
import numpy as np
import cv2
import socket, struct
import click
import re
import sys
import hooppos
import math

try:
    from config import config
except ImportError:
    print("No default config found")
    conifg = None
    
from imutils.video import FPS

# TODO
# Order of addding color components

# Global variables
params = {}
fps = None
# Create a pool of image processors
done = False
ACCEPTED_STREAM_MODES = {'t', 'g', 'd', None}
udp_sock = None

def findTheBall(image, denoise = True, kernel = None, iterations = 2):
    im = np.clip(image[:,:,0]*params["color_coefs"][0] + image[:,:,1]*params["color_coefs"][1] + image[:,:,2]*params["color_coefs"][2], 0, 255).astype(np.uint8) 
    #im = cv2.addWeighted(b, params["color_coefs"][2], g, -0.25, params["color_coefs"][1])
    #im = cv2.addWeighted(im, 1, r, params["color_coefs"][0], 0)

    im_thrs = cv2.inRange(im, params["threshold"],250)
    if denoise:
        # im_denoised = cv2.dilate(im_thrs, kernel, iterations)
        # im_denoised = cv2.erode(im_denoised, kernel, iterations)
        im_denoised = cv2.morphologyEx(im_thrs, cv2.MORPH_OPEN, None)      
    else:
        im_denoised = im_thrs

    # cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)
    # ((x, y), radius) = cv2.minEnclosingCircle(c)

    M = cv2.moments(im_denoised)
    if params["minballmass"] < M['m00'] < params["maxballmass"]:
        center = ( (int(M['m10'] / M['m00']), int(M['m01'] / M['m00'])) )
    else:
        print('Ball mass out of ranges ({0[minballmass]} < {1} < {0[maxballmass]})'.format(params, M['m00']))
        center = None

    return center, im_thrs, im_denoised

def processImage(frame_number, image):
    global done, fps, udp_sock

    try:
        # Downsample the image
        # e1 = cv2.getTickCount()
        img_dwnsample = image[::params['downsample'], ::params['downsample'], :]
        
        # center, im_thrs, im_denoised = findTheBall(img_dwnsample, iterations = 1, kernel = np.ones((2,2),np.uint8))
        center, im_thrs, im_denoised = findTheBall(img_dwnsample, denoise = False)
        if center is not None:
            center = (params['downsample']*center[0], params['downsample']*center[1])   

        # Save the the region of interest image if the debug option is chosen, or ball not found
        if params['debug'] > 1 or (center is None and params["debug"]):
            # if center is not None:
                # cv2.circle(img_dwnsample, center, 5, (0, 0, 255), -1)
            cv2.imwrite("{}im_dwn_denoised{}.png".format(params['img_path'], frame_number), im_denoised)
            cv2.imwrite("{}im_dwn{}.png".format(params['img_path'], frame_number), img_dwnsample)       
            cv2.imwrite("{}im_thrs{}.png".format(params['img_path'], frame_number), im_thrs)         

        # e2 = cv2.getTickCount()
        # elapsed_time = (e2 - e1)/ cv2.getTickFrequency()
        # print(elapsed_time)

        # print(center)

        if center is None:
            print('The ball was not found in the whole image!')
            center_inROI = None
        else:
            # Find the ball in smaller image
            ROI_xtop = max((center[1]-params["tracking_window_halfsize"]), 0)
            ROI_xbottom = min((center[1]+params["tracking_window_halfsize"]), params["resolution"][1])
            ROI_yleft = max((center[0]-params["tracking_window_halfsize"]), 0)
            ROI_yright = min((center[0]+params["tracking_window_halfsize"]), params["resolution"][0])
            imageROI = image[ ROI_xtop:ROI_xbottom,  ROI_yleft:ROI_yright, :]

            # Find the ball in the region of interest
            center_inROI, im_thrs, im_denoised = findTheBall(imageROI, denoise=False)

            # If the ball is not found, raise an exception
            if center_inROI is None:
                print('The ball was not found in the ROI!')
            else:
                # transform the measured position from ROI to full image coordinates
                center = (ROI_yleft + center_inROI[0], ROI_xtop + center_inROI[1])

        # Save the the region of interest image if the debug option is chosen
        if params['debug']:
            # cv2.imwrite("{}im_thrs%d.png".format(params['img_path'], frame_number), im_thrs)

            if center_inROI is not None:
                cv2.circle(imageROI, center_inROI, 5, (0, 0, 255), -1)
                cv2.imwrite("{}im_roi{}.png".format(params['img_path'], frame_number), imageROI) 
                cv2.imwrite("{}im_denoised{}.png".format(params['img_path'], frame_number), im_denoised)         

        # Write the measured position to the shred memory
        if center is not None:
            hooppos.measpos_write(center[0], center[1])
        else:
            hooppos.measpos_write(params["resolution"][0]+1, params["resolution"][1]+1)

        # If the ip ip option is chosen, send the identified position via a UDP packet
        if params['ip'] is not None:
            # If the ball was found, send the identified position, if not, send the size of the image +1 as the identified position
            if center is not None:
                udp_sock.sendto(struct.pack('II', center[0], center[1]), (params['ip'], params['port']))

                if (params['stream'] is not None):
                    if params['stream'] == 't':                                
                        # Send thresholded red channel

                        # If the ball is found, mark it in the ROI image
                        if center is not None:
                            cv2.circle(im_thrs, center_inROI, 5, 255, -1)

                        # Send the position
                        udp_sock.sendto(im_thrs.tostring(), (params['ip'], params['port']+1))

                    elif params['stream'] == 'g':     
                        # Send grayscale image
                        imageROI_gray = cv2.cvtColor(imageROI, cv2.COLOR_BGR2GRAY)

                        # If the ball is found, mark it in the ROI image
                        if center is not None:
                            cv2.circle(imageROI_gray, center_inROI, 5, 255, -1)

                        # Send the position
                        udp_sock.sendto(imageROI_gray.tostring(), (params['ip'], params['port']+1))
                    elif params['stream'] == 'd':
                        # Send denoised image (image after dilation and erosion)

                        # If the ball is found, mark it in the ROI image
                        if center is not None:
                            cv2.circle(im_denoised, center_inROI, 5, 128, -1)

                        # Send the position                                
                        udp_sock.sendto(im_denoised.tostring(), (params['ip'], params['port']+1))                
            else:
                udp_sock.sendto(struct.pack('II', params["resolution"][0]+1, params["resolution"][1]+1), (params['ip'], params['port']))

                if (params['stream'] is not None):
                    # Send an empty image
                    udp_sock.sendto(np.empty((params["tracking_window_halfsize"]*2, params["tracking_window_halfsize"]*2), dtype=np.uint8), (params['ip'], params['port']+1))

    finally:
        # Set done to True if you want the script to terminate
        # at some point
        frame_number += 1
        if frame_number >= params["num_frames"]:
            done=True

        fps.update()

    return center

class ImageProcessor(io.BytesIO):
    def __init__(self):
        super().__init__()
        self.frame_number = 0;

    def write(self, b):

        if params["verbose"] > 0:
            e1 = cv2.getTickCount()

        data = np.fromstring(b, dtype=np.uint8)
        image = np.resize(data,(params["resolution"][1], params["resolution"][0], 3))

        center = processImage(self.frame_number, image)
        
        if params['verbose']:
            e2 = cv2.getTickCount()
            elapsed_time = (e2 - e1)/ cv2.getTickFrequency()
            if center is not None:
                center_to_print = center
            else:
                center_to_print = ('-', '-')

            print('Frame: {}, center ({},{}), elapsed time: {}'.format(self.frame_number, center_to_print[0], center_to_print[1], elapsed_time))
        self.frame_number += 1        


def streams():
    processor = ImageProcessor()

    while not done:
        #e1 = cv2.getTickCount()

        yield processor
        #e2 = cv2.getTickCount()
        #elapsed_time = (e2 - e1)/ cv2.getTickFrequency()
        #print('Freq : {}'.format(round(1/elapsed_time)))

@click.command()
@click.option('--num-frames', '-n', default=1, help='Total number of frames to process')
@click.option('--frame-rate', '-f', default=10, help='Number of frames per second to process')
@click.option('--exposition-time', '-e', default=10, help='Exposition time (shutter speed) in milliseconds.')
@click.option('--verbose', '-v', is_flag=True, default=False, help='Display time needed for processing of each frame and the measured position.')
@click.option('--stream', '-s', default=None, type=str, help='Stream the images with the measured position. In the defualt settings, no image is streamed. \n\t t - the thresholded image I = R-G-B \n\t g - the grayscale image \n\t d - the denoised image')
@click.option('--debug', '-d', count=True, default=False, help='Save masks and ROIs together with the identified position of the ball.')
@click.option('--ip-port', '-i', type=(str, int), default=(None, 0), help='Specify the ip address and port of the host the measured position will be sending to.')
@click.option('--downsample', '-dw', type=int, default=6, help='Specify the down-sample ration for the initial ball localization routine.')
@click.option('--color_coefs', '-c', default=(-0.5, -0.25, 1), help='Specify coeficients for color parts adding')
@click.option('--threshold', '-t', default=90, help='Threshold for color clasifiing')
@click.option('--resolution', '-r', type=(int, int), default=(640,480), help='Image resolution')
@click.option('--tracking-window-halfsize', '-w', type=int, default=48, help='Size of window for tracking')
@click.option('--preview', '-p', is_flag=True, default=False, help="Show preview on HDMI or display")
@click.option('--video-record', is_flag=True, default=False, help="Record video")
@click.option('--img-path', type=str, default='./img/', help='Path to store images, ideally ramdisk')
@click.option('--ball-size', type=(int, int), default=(0, 60), help="Min and max ball diameter in pixels")
def main(**kwargs):
    global params, fps, udp_sock

    camera = None
    try:
        params = kwargs
        params['ip'] = params['ip_port'][0]
        params['port'] = params['ip_port'][1]

        # Ball mass - ball is approximately 40 px in diameter in the image hence the mass should be somewhere around pi*20^2=1256.
        # The values are multiplied by 255 because the the pixels in the binary image have values 0 and 255 (weird, isn't it?).
        params['minballmass'] = (params["ball_size"][0]/2)**2 * math.pi * 255
        params['maxballmass'] = (params["ball_size"][1]/2)**2 * math.pi * 255
        print("Ball mass must be between {0[minballmass]} and {0[maxballmass]}".format(params))

        # Check whether the value of the streaming option
        if params['stream'] not in ACCEPTED_STREAM_MODES:
            print('Invalid option for streaming settings. Images will not be streamed.')
            params['stream'] = None 

        click.echo('Number of frames: %d' % params['num_frames'])
        click.echo('FPS: %d' % params['frame_rate'])

        if params['ip'] is not None:
            aa = re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", params['ip'])
            if aa is not None:
                params['ip'] = aa.group()
                click.echo('IP: %s, port: %d' % (params['ip'], params['port']))
                udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
            else:
                params['ip'] = None

        if params['verbose']:
            click.echo('Verbose')
        if params['debug']:
            click.echo('Debug {}'.format(params["debug"]))

        with picamera.PiCamera() as camera:
            camera.resolution = params["resolution"]
            # Set the framerate appropriately; too fast and the image processors
            # will stall the image pipeline and crash the script
            camera.framerate = params['frame_rate']        
            camera.shutter_speed = params['exposition_time']*1000
            camera.iso = 200

            if params['preview']:
                camera.start_preview()

            # Let the camera warm up
            time.sleep(2)

            print("Exposition time: {}".format(camera.exposure_speed/1000))
            print("camera.awb_gains: {}".format(camera.awb_gains))
            print("camera.iso: {}".format(camera.iso))

            # Now fix the values
            camera.exposure_mode = 'off'
            g = camera.awb_gains
            camera.awb_mode = 'off'
            camera.awb_gains = g
            if params["video_record"]:
                camera.start_recording('{}video.h264'.format(params['img_path']), splitter_port=2, resize=params["resolution"])

            fps = FPS().start()
            
            camera.capture_sequence(streams(), use_video_port=True, format="rgb")

            if params["video_record"]:
                camera.stop_recording(splitter_port=2)

            fps.stop()
            print("[INFO] elasped time: {:.2f}".format(fps.elapsed()))
            print("[INFO] approx. FPS: {:.2f}".format(fps.fps()))

            if params["preview"]:
                camera.stop_preview()

    except (KeyboardInterrupt, SystemExit):
        print('Yes, hold on; I am trying to kill myself!')

    finally:
        # Shut down the processors in an orderly fashion
        if camera is not None:
            camera.close()

if __name__=='__main__':
    main(default_map=config)
