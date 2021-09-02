#!/usr/bin/env python3
# from numba import jit
from ctypes import byref
from ransac_detector.ransac_detector_ctypes import Ball_t
import lamp
import processor
import math
import numpy as np
import matplotlib.pyplot as plt
import struct
import logging
import subprocess
#import cv2
from detector import Detector, RansacDetector
from threading import Lock, Thread
from flask import Flask, render_template, send_from_directory, make_response, Response, abort, jsonify, request
from flask_bootstrap import Bootstrap
from flask_colorpicker import colorpicker
import colorsys
from PIL import Image
from io import BytesIO
import re
import time
#import find_object_colors
import inspect
import matplotlib
import warnings
matplotlib.use('Agg')


NaN = float('NaN')

app = Flask(__name__)
Bootstrap(app)
colorpicker(app)
app.processor = None
app.config['SECRET_KEY'] = 'secret!'

app.config['TEMPLATES_AUTO_RELOAD'] = True

app.thread = None

plot_lock = Lock()


def getImage(object=None, type=None):
    if app.processor is None:
        print("App not ready yet")
        return None

    if object is None or object == "processor":
        object = app.processor
    else:
        object = app.processor.getDetector(object)
    return object.getImage(type)


def responseImage(image):
    response = make_response(image)
    response.headers['Content-Type'] = 'image/png'
    return response


@app.after_request
def add_header(r):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also not to cache the rendered page.
    """
    r.headers["Cache-Control"] = "public, max-age=0, no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    return r


@app.route('/')
@app.route('/detector/<detector>')
def index(detector=None):
    if app.processor is None:
        print("App not ready yet, please retry")
        return 'App not ready yet, please <a href="./">retry</a>'
    if detector is None:
        detectors = app.processor.detectors
    else:
        detectors = filter(lambda d: d.name == detector,
                           app.processor.detectors)
    return render_template("index.html", camera=app.camera, processor=app.processor, params=app.params, detectors=detectors)


@app.route('/centers')
def centers():
    # print(app.processor.centers)
    # data = [None if math.isnan(x) else [None if math.isnan(
    #    y) else y for y in x] for x in app.processor.centers]
    try:
        data = [None if x is None else [None if math.isnan(
            y) else y for y in x] for x in app.processor.centers]
    except:
        data = []
    return jsonify(data)


@app.route('/restart')
def restart():
    app.processor.restart()
    return 'OK <a href="/">Back</a>'


@app.route('/lamp/on')
def lamp_on():
    lamp.on()
    return 'OK <a href="/">Back</a>'


@app.route('/lamp/off')
def lamp_off():
    lamp.off()
    return 'OK <a href="/">Back</a>'


@app.route('/config')
def config():
    return jsonify(dict(app.params))


@app.route('/config', methods=('POST',))
def config_post():
    data = request.get_json()
    print(data)
    app.params.update(data)
    app.processor.restart()
    return jsonify(dict(app.params))


@app.route('/config/loadfile', methods=('POST',))
def config_loadfile():
    filename = request.data
    app.params.load(filename)
    app.processor.restart()
    return jsonify(dict(app.params))


@app.route('/detector/<detector>/threshold/<int:threshold>')
def set_threshold(detector, threshold):
    detectors = filter(lambda d: d.name == detector, app.processor.detectors)

    try:
        next(iter(detectors)).threshold = threshold
    except StopIteration:
        abort(404)

    return "Ok"

@app.route('/camera')
def takephoto(object=None, type=None):
    tmpIso = app.camera.iso
    app.camera.iso = 1000
    time.sleep(1)
    image = getImage(object, type)
    if image is None:
        abort(404)
        return "Not loaded yet"
    if len(image.shape) == 3:
        # image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        # _, buffer = cv2.imencode('.png', image)
        pil_image = Image.fromarray(image)
        byteIO = BytesIO()
        pil_image.save(byteIO, format='PNG')
    app.camera.iso = tmpIso
    return responseImage(byteIO.getvalue())
    # my_stream = BytesIO()
    # tmpIso = app.camera.iso
    # app.camera.iso = 1000
    # # time.sleep(2)
    # # app.camera.capture(my_stream, 'png')
    # app.camera.capture(my_stream,format='png')
    # # print('cap done',tmpIso)
    # # print(my_stream)
    # app.camera.iso = tmpIso

    # # my_stream.seek(0)
    # return responseImage(my_stream.getvalue())


@app.route('/image')
@app.route('/image/<object>')
@app.route('/image/<object>/<type>')
def image(object=None, type=None):
    image = getImage(object, type)
    print(app.camera.iso)
    if image is None:
        abort(404)
        return "Not loaded yet"
    if len(image.shape) == 3:
        # image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        # _, buffer = cv2.imencode('.png', image)
        pil_image = Image.fromarray(image)
        byteIO = BytesIO()
        pil_image.save(byteIO, format='PNG')
    return responseImage(byteIO.getvalue())


@app.route('/imagesc')
@app.route('/imagesc/<object>')
@app.route('/imagesc/<object>/<type>')
def imagesc(object=None, type=None):
    image = getImage(object, type)
    if image is None:
        abort(404)
        return "Not loaded yet"
    buffer = BytesIO()
    with plot_lock:
        if len(image.shape) == 3:
            plt.imshow(image)
        else:
            plt.imshow(image, cmap='Greys',  interpolation='nearest')
            plt.colorbar()
        plt.savefig(buffer)
        plt.close()
    return responseImage(buffer.getvalue())


@app.route('/wb')
@app.route('/wb/<int:step>')
def wb(step=0):
    return render_template("wb.html", camera=app.camera, processor=app.processor, params=app.params, step=step)


@app.route('/wb/value')
def wb_value():
    image = getImage()
    # print(image[:,:,0].shape)
    if image is None:
        abort(404)
        return "Not loaded yet"
    image = np.array(image)
    pt1 = tuple(int(v/2-50) for v in app.params["resolution"])
    pt2 = tuple(int(v/2+50) for v in app.params["resolution"])
    [b, g, r] = np.dsplit(image, image.shape[-1])
    # print(b.shape)
    #jsonify(cv2.mean(image[pt1[0]:pt2[0], pt1[1]:pt2[1], :]))
    # print((list(map(float(np.mean([image[:][:][i] for i in range(3)], axis=0))))))
    return jsonify([np.mean(b), np.mean(g), np.mean(r)])

from vision import change_wb
@app.route('/wb/value/<int:a>,<int:b>')
@app.route('/wb/value/<float:a>,<int:b>')
@app.route('/wb/value/<int:a>,<float:b>')
@app.route('/wb/value/<float:a>,<float:b>')
def wb_set(a, b):
    print(a, b)
    # image_wb()
    change_wb((a,b),app.camera)
    return "OK"


@app.route('/image/wb')
def image_wb():
    #     image = getImage("processor", "centers")

    pt1 = tuple(int(v/2-50) for v in app.params["resolution"])
    pt2 = tuple(int(v/2+50) for v in app.params["resolution"])

    im = getImage()
    if im is None:
        abort(404)
    pil_image = Image.fromarray(im)
    byteIO = BytesIO()
    pil_image.save(byteIO, format='PNG')
    return responseImage(byteIO.getvalue())


def get_hsv_detector():
    if app.processor is None:
        return "App processor hasn't loaded yet!"
    if len(app.processor.detectors) < 0:
        return "No detector registered!"
    for used_detector in app.processor.detectors:
        # type didn't work for some reason...
        used_str = str(used_detector)
        if used_str == "MultiColorDetector" or used_str == 'RansacDetector':
            return app.processor.getDetector(used_detector.name)
    return "This webpage only works if you're using the MultiDetector..."

# main ball_colors UI webpage, computes some statistics, prepares files for other functions and creates the website itself


@app.route('/ball_colors')
def ball_colors():
    # check if everything has been loaded
    im = getImage()

    if im is None:
        return "Program hasn't properly started yet - try it again in a few seconds. :-)"

    MultiDetector = get_hsv_detector()
    if not isinstance(MultiDetector, Detector):
        return MultiDetector

    # get samples
    centers = []
    # print("1")

    frame_number = app.processor.frame_number
    test_iterations = request.args.get("i")
    if test_iterations is None:
        test_iterations = 5
    else:
        try:
            test_iterations = int(test_iterations)
            if test_iterations < 1:
                test_iterations = 1
        except:
            print("Test iteration must be integer! Setting default value...")
            test_iterations = 5
    for i in range(test_iterations):
        centers.append(app.processor.centers)
        while app.processor.frame_number == frame_number:  # wait for next frame
            continue
        frame_number = app.processor.frame_number

    balls = [[x[i] for x in centers]
             for i in range(len(centers[0]))]  # change data structure
    x_coordinates = [[]for i in range(len(balls))]
    y_coordinates = [[]for i in range(len(balls))]
    thetas = [[]for i in range(len(balls))]
    ball_centers_found = []

    # compute statistics
    for ball_index, ball in enumerate(balls):
        current_centers_found = 0
        for sample in ball:
            if sample is not None and sample[0] is not None:
                current_centers_found += 1
                x_coordinates[ball_index].append(sample[0])
                y_coordinates[ball_index].append(sample[1])
            if sample is not None and sample[2] is not None:
                thetas[ball_index].append(sample[2])
        ball_centers_found.append(current_centers_found)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        ball_center_means = [(np.mean(x_coordinates[i]), np.mean(
            y_coordinates[i]), np.mean(thetas[i])) for i in range(len(balls))]
        ball_center_stds = [(np.std(x_coordinates[i]), np.std(
            y_coordinates[i]), np.std(thetas[i])) for i in range(len(balls))]
        percentages = [100*ball_centers_found[i] /
                       test_iterations for i in range(len(balls))]

    # save images for website
    pil_image = Image.fromarray(im)
    pil_image.save('static/image.png')
    hsv_image = pil_image.convert('HSV') # 3x8 bit [0,255]
    np.save('static/image_hsv', np.array(hsv_image))

    return render_template('ball_colors.html', balls=MultiDetector.balls, found=ball_centers_found, 
            test_iterations=test_iterations, means=ball_center_means, percentages=percentages, 
            stds=ball_center_stds, int=int, len=len)

# receives x,y coordinates and responds with picture color in RGB at that position
@app.route('/ball_colors/color')
def color():
    try:
        x = int(request.args.get('x'))
        y = int(request.args.get('y'))
        #print(x, y)
    except:
        print("Error: X,Y not int!")
        x = 0
        y = 0
    if(x < 0 or x > 480):
        print("Error: x out of bounds!")
        x = 0
    if(y < 0 or y > 480):
        print("Error: y out of bounds")
        y = 0
    im = np.load('static/image_hsv.npy')
    pixel = im[y, x]
    r, g, b = colorsys.hsv_to_rgb(float(pixel[0])/256, 0.3, 0.3)

    #print("R: {}, G: {}, B: {}".format(int(r*256), int(g*256), int(b*256)))
    return jsonify(r=int(r*256), g=int(g*256), b=int(b*256))


'''
Used to change ball colors. However, this does not apply the changes - merely set them. 
It is still necessary to reinit the table in C, preferably using '/ball_colors/set_colors'
'''

# @jit(nopython=True, cache=True)


def compute_mask(im, detector, ball_t):
    mask = np.zeros(shape=tuple(im.shape[:2]), dtype=np.uint8)
    # print(mask.shape)
    if isinstance(detector, RansacDetector):
        detector.c_funcs.get_segmentation_mask(
            im, *im.shape[:2], mask, byref(ball_t))
    else:
        print("This detector does not support segmentation mask in browser, sorry!")
    return mask


@app.route('/ball_colors/limits')
def limits():
    try:
        formatted = (request.args.get('formatted'))
        tolerance = float(request.args.get('tolerance'))/500 # as int in [0,100]
        index = int(request.args.get('index'))
        m = re.match(r'HSV\((.*),(.*),(.*)\)', formatted)
        h = float(m.group(1)) # supplied as float in [0,1]
        s = int(m.group(2))  # supplied as int in [0,255]
        v = int(m.group(3))  # supplied as int in [0,255]
    except:
        print("Error formatting at /limits, received: formatted: {}, tolerance: {}, index: {}".format(
              formatted, request.args.get('tolerance'), request.args.get('index')))
        return "ERROR"
    # TODO: check if hues overlap
    print(f"Webpage: {h}, {tolerance} {s}, {v}")

    MultiDetector = get_hsv_detector()
    if not isinstance(MultiDetector, Detector):
        return MultiDetector
    MultiDetector.balls[index].set_new_values_tolerance(
        h, tolerance, s, v, htype="float", svtypes="256")

    im = np.load('static/image_hsv.npy')

    mask = compute_mask(im, MultiDetector, MultiDetector.balls[index].ball_t)

    image = Image.fromarray(mask)
    image.save("static/im_thrs-{}.png".format(index))
    return "OK"


@app.route('/colorpicker-master/<path:path>')
def colorpicker_plugin(path):
    return send_from_directory('colorpicker-master', path)

# used to save new settings


@app.route('/ball_colors/set_colors')
def set_colors():
    MultiDetector = get_hsv_detector()
    if not isinstance(MultiDetector, Detector):
        return MultiDetector
    MultiDetector.init_table()
    MultiDetector.save_settings()
    return "OK"

def generate_images(detector):
    if not isinstance(detector, RansacDetector):
        return "This page only works with RansacDetector"
    images = []
    nrs_found = []
    nrs_modeled = []
    for i, center in enumerate(detector.centers):
        image = getImage()
        if center is None:
            images.append([np.zeros_like(image) for i in range(10)])
            nrs_found.append(0)
            nrs_modeled.append(0)
        else:
            offset = detector.ball_radius*2
            w_low = max(0, int(center[0]-offset))
            w_high = min(image.shape[0], int(center[0]+offset))

            h_low = max(0, int(center[1]-offset))
            h_high = min(image.shape[1], int(center[1]+offset))
            image_crop = image[h_low:h_high, w_low:w_high, :]
            nr_found, nr_modeled, gen_ims = detector.processImageOverlay(
                image_crop, [offset, offset], detector.ball_colors[i])
            nrs_modeled.append(nr_modeled)
            nrs_found.append(nr_found)
            images.append([image_crop, *gen_ims])
    return nrs_found, nrs_modeled, images


def save_images(images, index):
    filenames = ["image_crop", "seg_background", "seg_ball", "seg_border", "ransac_contour",
                 "ransac_tolerance_contour", "lsq_modeled_contour", "lsq_border_contour"]
    for image, filename in zip(images, filenames):
        try:
            image = Image.fromarray(image)
            image.save(f"static/{filename}-{index}.png")
        except:
            print(f"failed with image {image}")
    return filenames


@app.route('/ransac')
def ransac_settings():
    detector = get_hsv_detector()
    if getImage() is None:
        return "Program hasn't properly started yet - try it again in a few seconds. :-)"
    nr_found, nr_modeled, images = generate_images(detector)
    for i, image_set in enumerate(images):
        if image_set is not None:
            filenames = save_images(image_set, i)
    checkbox_labels = ["", "Background mask", "Ball mask", "Border mask", "Ransac fit",
                       "Ransac tolerance (\"modeled\" pixels)", "LSQ (fit to RANSAC)", "LSQ (fit to all border)"]
    ids = ["ids", "ball_radius", "max_iterations",
           "confidence_threshold", "downsample", "tol_min", "tol_max", "ball_color_amounts", "max_dx"]
    ball_amounts = [detector.ball_colors.count(
        i) for i in range(len(detector.balls))]
    values = [ids, detector.ball_radius, detector.max_iterations, detector.confidence_threshold,
              detector.downsample, detector.min_dist/detector.ball_radius, detector.max_dist/detector.ball_radius, ball_amounts,detector.max_dx]

    settings = dict(zip(ids, values))
    return render_template('ransac.html', ball_nr=detector.number_of_objects, color_nr=len(detector.balls), 
    images_n_labels=list(zip(filenames, checkbox_labels)), settings=settings, nr_modeled=nr_modeled, 
    nr_found=nr_found, colors=[ball.get_color_hexa() for ball in detector.balls])


@app.route('/ransac/change')
def change_value():
    detector = detector = get_hsv_detector()
    id = request.args.get('id')
    value = request.args.get('value')
    # print(f"received {value}")
    nrs_modeled = []
    # try:
    if '.' in value:
        value = float(value)
    else:
        value = int(value)
    if id == 'tol_min':
        id = 'min_dist'
        value *= detector.ball_radius
    elif id == 'tol_max':
        id = 'max_dist'
        value *= detector.ball_radius
    elif id == 'ball_radius':
        # print(f"min dist {detector.min_dist}, br {detector.ball_radius}")
        detector.min_dist = detector.min_dist/detector.ball_radius*value
        detector.max_dist = detector.max_dist/detector.ball_radius*value
    # print(f"setting value {value}")
    detector.__setattr__(id, value)
    detector.save_settings()
    # detector.min_dist=1
    nrs_found, nrs_modeled, images = generate_images(detector)
    for i, image_set in enumerate(images):
        save_images(image_set, i)
    # except Exception as e:
    #     print("Couldn't change settings: ")
    #     print(e)
    # print(nrs_found, nrs_modeled)
    return jsonify(nr_modeled=nrs_modeled, nr_found=nrs_found)
    # return jsonify(nr_modeled=[0 for _ in detector.number_of_objects])

import json
@app.route('/ransac/change_amounts')
def change_amounts():
    detector = detector = get_hsv_detector()
    amounts = json.loads(request.args.get('amounts'))
    print(amounts)
    try:
        amounts = [int(amount) for amount in amounts]
        detector.change_ball_colors(amounts)
        return jsonify(response=0)
    except Exception as e:
        print(e)
        return jsonify(response=-1)


def rotate(origin, point, angle):
    """
    Rotate a point counterclockwise by a given angle around a given origin.

    The angle should be given in radians.
    """
    ox, oy = origin
    px, py = point

    qx = ox + math.cos(angle) * (px - ox) - math.sin(angle) * (py - oy)
    qy = oy + math.sin(angle) * (px - ox) + math.cos(angle) * (py - oy)

    return qx, qy


def trapez(y, y0, w):
    return np.clip(np.minimum(y+1+w/2-y0, -y+1+w/2+y0), 0, 1)


def weighted_line(r0, c0, r1, c1, w=2, rmin=0, rmax=np.inf):
    # The algorithm below works fine if c1 >= c0 and c1-c0 >= abs(r1-r0).
    # If either of these cases are violated, do some switches.
    r0 = int(r0)
    c0 = int(c0)
    r1 = int(r1)
    c1 = int(c1)
    if abs(c1-c0) < abs(r1-r0):
        # Switch x and y, and switch again when returning.
        xx, yy, val = weighted_line(c0, r0, c1, r1, w, rmin=rmin, rmax=rmax)
        return (yy, xx, val)

    # At this point we know that the distance in columns (x) is greater
    # than that in rows (y). Possibly one more switch if c0 > c1.
    if c0 > c1:
        return weighted_line(r1, c1, r0, c0, w, rmin=rmin, rmax=rmax)

    # The following is now always < 1 in abs
    slope = (r1-r0) / (c1-c0)

    # Adjust weight by the slope
    w *= np.sqrt(1+np.abs(slope)) / 2

    # We write y as a function of x, because the slope is always <= 1
    # (in absolute value)
    x = np.arange(c0, c1+1, dtype=float)
    y = x * slope + (c1*r0-c0*r1) / (c1-c0)

    # Now instead of 2 values for y, we have 2*np.ceil(w/2).
    # All values are 1 except the upmost and bottommost.
    thickness = np.ceil(w/2)
    yy = (np.floor(y).reshape(-1, 1) +
          np.arange(-thickness-1, thickness+2).reshape(1, -1))
    xx = np.repeat(x, yy.shape[1])
    vals = trapez(yy, y.reshape(-1, 1), w).flatten()

    yy = yy.flatten()

    # Exclude useless parts and those outside of the interval
    # to avoid parts outside of the picture
    mask = np.logical_and.reduce((yy >= rmin, yy < rmax, vals > 0))

    return (yy[mask].astype(int), xx[mask].astype(int), vals[mask])


def paint_triangle(im, top_left_coords, bottom_left_coords, bottom_right_coords):
    if top_left_coords is not None and bottom_right_coords is not None:
        theta = np.arctan2(top_left_coords[1]-bottom_right_coords[1],
                           top_left_coords[0]-bottom_right_coords[0])+np.pi/4
        center_of_mass = [(top_left_coords[0]+bottom_right_coords[0]+bottom_left_coords[0])/3,
                          (top_left_coords[1]+bottom_right_coords[1]+bottom_left_coords[1])/3]
        print(center_of_mass)
        for i in range(-4, 4+1):
            im[int(center_of_mass[1])+i, int(center_of_mass[0]), 1] = 0xff
            im[int(center_of_mass[1]), int(center_of_mass[0])+i, 1] = 0xff

        # paint the triangle
        side_length_pixel = 122

        bl_corner = [center_of_mass[0]-side_length_pixel//3,
                     center_of_mass[1]-side_length_pixel//3]  # BL - bottom-left
        br_corner = [bl_corner[0]+side_length_pixel,
                     bl_corner[1]]  # BR - bottom-right
        tl_corner = [bl_corner[0], bl_corner[1] +
                     side_length_pixel]  # TL - top-left

        bl_corner = rotate(center_of_mass, bl_corner, theta)
        br_corner = rotate(center_of_mass, br_corner, theta)
        tl_corner = rotate(center_of_mass, tl_corner, theta)

        lines = [weighted_line(bl_corner[0], bl_corner[1], br_corner[0], br_corner[1]),
                 weighted_line(tl_corner[0], tl_corner[1],
                               br_corner[0], br_corner[1]),
                 weighted_line(bl_corner[0], bl_corner[1], tl_corner[0], tl_corner[1])]
        for line in lines:
            for i in range(len(line[0])):
                im[line[1][i], line[0][i]] = [
                    0xff, 0x33, 0xda]  # int(150*line[2][i])
        return im


@app.route('/triangle')
def triangle():
    # check if everything has been loaded
    im = getImage()
    if im is None:
        return "Program hasn't properly started yet - try it again in a few seconds. :-)"
    print(app.processor.centers)
    centers = app.processor.centers
    red = centers[0]
    blue = centers[1]
    green = centers[2]
    pink = centers[3]
    yellow = centers[4]
    orange = centers[5]

    # paint centers
    for center in centers:
        if center is not None:
            for i in range(-16, 16):
                if center[0]+i < 0 or center[0]+i > im.shape[0] or center[1]+i < 0 or center[1]+i > im.shape[1]:
                    continue
                im[int(center[1])+i, int(center[0]), :] = 0xff
                im[int(center[1]), int(center[0])+i, :] = 0xff

    # paint triangles
    paint_triangle(im, blue, yellow, red)
    paint_triangle(im, pink, orange, green)

    # return the data as a png
    image = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
    _, buffer = cv2.imencode('.png', image)
    return responseImage(buffer.tobytes())


def start():
    if not app.thread:
        app.thread = Thread(target=app.run, daemon=True, kwargs={
                            "host": "0.0.0.0", "port": 5001, "debug": True, "use_reloader": False})
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        app.thread.start()


app.start = start

if __name__ == '__main__':
    start()
