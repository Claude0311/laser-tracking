#!/usr/bin/env python3

import struct
import logging
import subprocess
import cv2
from threading import Lock, Thread
from flask import Flask, render_template, make_response, Response, abort, jsonify
from io import BytesIO

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

plot_lock = Lock()

def getImage(object=None, type=None):
    if object is None or object == "processor":
        object = app.processor
    else:
        object = app.processor.getDetector(object)
    return object.getImage(type)

def repsonseImage(image):
    response =  make_response(image)
    response.headers['Content-Type'] = 'image/png'
    return response

@app.after_request
def add_header(r):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 10 minutes.
    """
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    r.headers['Cache-Control'] = 'public, max-age=0'
    return r

@app.route('/')
def index():
    return render_template("index.html", camera=app.camera, processor=app.processor, params=app.params)

@app.route('/image')
@app.route('/image/<object>')
@app.route('/image/<object>/<type>')
def image(object=None, type=None):
    image = getImage(object, type)
    if image is None:
        abort(404);
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    _, buffer = cv2.imencode('.png', image)
    return repsonseImage(buffer.tobytes())


@app.route('/imagesc')
@app.route('/imagesc/<object>')
@app.route('/imagesc/<object>/<type>')
def imagesc(object=None, type=None):
    image = getImage(object, type)
    if image is None:
        abort(404);
    buffer = BytesIO()
    with plot_lock:
        if len(image.shape) == 3:
            plt.imshow(image)
        else:
            plt.imshow(image, cmap='Greys',  interpolation='nearest')
            plt.colorbar()
        plt.savefig(buffer)
        plt.close()
    return repsonseImage(buffer.getvalue())

@app.route('/wb')
@app.route('/wb/<int:step>')
def wb(step=0):
    return render_template("wb.html", camera=app.camera, processor=app.processor, params=app.params, step=step)

@app.route('/wb/value')
def wb_value():
    image = getImage()
    if image is None:
        abort(404);
    pt1 = tuple(int(v/2-50) for v in app.params["resolution"])
    pt2 = tuple(int(v/2+50) for v in app.params["resolution"])
    return jsonify(cv2.mean(image[pt1[0]:pt2[0], pt1[1]:pt2[1], :]))

@app.route('/wb/value/<int:a>,<int:b>')
@app.route('/wb/value/<float:a>,<int:b>')
@app.route('/wb/value/<int:a>,<float:b>')
@app.route('/wb/value/<float:a>,<float:b>')
def wb_set(a,b):
    app.camera.awb_gains = (a,b)
    return "OK"

@app.route('/image/wb')
def image_wb():
    image = getImage()
    if image is None:
        abort(404);

    pt1 = tuple(int(v/2-50) for v in app.params["resolution"])
    pt2 = tuple(int(v/2+50) for v in app.params["resolution"])
    image = cv2.rectangle(image, pt1, pt2, (255,0,0),5) 
    _, buffer = cv2.imencode('.png', cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    return repsonseImage(buffer.tobytes())


def start():
    app.thread = Thread(target=app.run, daemon=True, kwargs={"host": "0.0.0.0", "port": 5001, "debug":True, "use_reloader":False})
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.thread.start()

app.start = start

if __name__ == '__main__':
    start()