import sys
import csv
from PyQt5.QtWidgets import *
from PyQt5 import uic, QtCore
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

import numpy as np
import serial as serial
import time
import cv2


app = QApplication([])

window = uic.loadUi('interface.ui')

children = window.findChildren(QWidget)
print(children)

window.setFixedSize(1131, 900)

# WARNING!!!: max value of last wave range needs to be adjusted if sample rate is modified
SAMPLE_RATE = 50
SAMPLE_INTERVAL = 1.0/SAMPLE_RATE

#WARNING!!!: Frame cutpoint values change from video to video
DELTA_FRAMES = (0,268)
THETA_FRAMES = (269, 390)
ALPHA_FRAMES =(391, 685)
BETA_FRAMES = (686, 1079)

WAVE_RANGES = (
    {"name": "delta", "min": 0, "max": 4, "color": "r", "frames": DELTA_FRAMES},
    {"name": "theta", "min": 4, "max": 8, "color": "g", "frames": THETA_FRAMES},
    {"name": "alpha", "min": 8, "max": 14, "color": "b", "frames": ALPHA_FRAMES},
    {"name": "beta", "min": 14, "max": 25, "color": "y", "frames": BETA_FRAMES},
)

window.xdata = np.array([])
window.ydata = np.array([])

window.isLoading = False
window.timer = None
window.classCheckTimer = None
window.waveClass = None
window.cap = None
window.temp1 = False

window.waveCounter = []
wave_names = []
wave_duration = []
wave_colors = []
for wave in WAVE_RANGES:
    wave_names.append(wave["name"])
    wave_duration.append(0.0)
    wave_colors.append(wave["color"])

window.waveCounter.append(wave_names)
window.waveCounter.append(wave_duration)
window.waveCounter.append(wave_colors)

# window.waveClass = WAVE_RANGES[2]

VIDEO_NAME = "hologram.mp4"
FRAME_CUTPOINTS = (268, 390, 685, 1079, 1469)

window.figure = Figure()
window.ax1 = window.figure.add_subplot(311, title="time-amplitude")
window.ax2 = window.figure.add_subplot(312, title="fft")
window.ax3 = window.figure.add_subplot(313, title="duration spent in wave range")
window.figure.subplots_adjust(hspace=0.3)

window.canvas = FigureCanvas(window.figure)
window.layoutPlot.addWidget(window.canvas)
window.toolbar = NavigationToolbar(window.canvas, window.wgtPlot, coordinates=True)
window.layoutPlot.addWidget(window.toolbar)         

    
def load_csv():
    filename = QFileDialog.getOpenFileName(window, 'Open File')
    filename = str(filename[0])

    if filename != '' and filename.endswith('.csv'):
        with open(filename) as f:
            window.ydata = np.array([])
            next(f)
            for line in f:
                line = line[:-2]
                temp = float(line).__round__(4)
                window.ydata = np.append(window.ydata, [temp])
            
        print("data loaded")
        plot_amp()
    else:
        window.lblLoadError.setText("Error: the file chosen is not a .csv file")
        window.lblLoadError.setHidden(False)


def plot_amp():
    window.ax1.clear()
    window.ax1.set_title("time-amplitude")
    window.ax1.set_xlim(left=0, right=20)
    window.xdata = np.arange(0, len(window.ydata)/SAMPLE_RATE, SAMPLE_INTERVAL)
    # window.xdata = np.linspace(0, 10, 50)
    # window.ydata = (np.cos(3*window.xdata))
    start = time.time()
    print("plotting graph...")
    # window.ax1.plot(X, Y)
    window.ax1.plot(window.xdata, window.ydata)
    plot_fft()
    window.canvas.draw()
    end = time.time()
    print(end-start)


def load_raw():
    
    if not window.isLoading:
        try:
            window.lblLoadError.setHidden(True)         
            window.ser = serial.Serial('COM4', baudrate=9600, timeout=1)

            window.isLoading = True
            disable_input(window.isLoading)
            window.btnRoll.setText("Stop")

            for duration in window.waveCounter[1]:
                duration = 0.0

            window.xdata = np.array([])
            window.ydata = np.array([])
            discard = window.ser.readline()

            window.fetchTimer = QtCore.QTimer(window)
            window.fetchTimer.timeout.connect(fetch_raw)
            window.fetchTimer.start(20)
            window.drawTimer = QtCore.QTimer(window)
            window.drawTimer.timeout.connect(roll_live)
            window.drawTimer.start(1000)
            window.classCheckTimer = QtCore.QTimer(window)
            window.classCheckTimer.setSingleShot(True)
            window.classCheckTimer.timeout.connect(video_init)
            window.classCheckTimer.start(5000)

        except:
            window.lblLoadError.setText("no external device found")
            window.lblLoadError.setHidden(False)
    else:
        window.fetchTimer.stop()
        window.drawTimer.stop()
        window.ser.close()
        window.fetchTimer = None
        window.drawTimer = None
        window.isLoading = False
        window.waveClass = None

        disable_input(window.isLoading)
        window.btnRoll.setText("Roll")

        
def fetch_raw():
    if window.temp1 == False:
        print(int(QtCore.QThread.currentThreadId()))
        window.temp1 = True
    # start = time.time()
    try:
        if len(window.ser.readline().strip()) != 0:
            rawdata = float(window.ser.readline().strip())
        else:
            rawdata = 10

        print(rawdata)

        window.ydata = np.append(window.ydata, [rawdata])
        x = len(window.ydata) * 0.02
        window.xdata = np.append(window.xdata, [x])

    except:
        window.ser.close()
        window.fetchTimer.stop()
        window.drawTimer.stop()
        window.isLoading = False
        window.fetchTimer = None
        window.drawTimer = None
        window.waveClass = None
        window.lblLoadError.setText("external device disconnected")
        window.lblLoadError.setHidden(False)
        window.btnRoll.setText("Roll")
        disable_input(window.isLoading)
    # end = time.time()
    # print(end-start)

def roll_live():
    x = len(window.ydata) * 0.02
    window.ax1.clear()
    window.ax1.set_title("time-amplitude")
    
    max_width = 5
    if x > max_width:
        window.ax1.set_xlim(left=x-max_width, right=x)
    else:
        window.ax1.set_xlim(left=0, right=max_width)
    
    print(len(window.xdata))
    window.ax1.plot(window.xdata, window.ydata)
    plot_fft()
    window.canvas.draw()


def plot_fft():
    if len(window.ydata) >= SAMPLE_RATE:
            sample = window.ydata[-1 * SAMPLE_RATE:]
            adjusted_sample = np.subtract(sample, np.average(sample))
            fftY = np.fft.fft(adjusted_sample)
            fftY = 2.0/SAMPLE_RATE * np.abs(fftY[:int(SAMPLE_RATE/2)])
            fftX = np.linspace(0, int(SAMPLE_RATE/2), int(SAMPLE_RATE/2))
            brain_freq_index = np.where(fftY == np.amax(fftY))[0][0]
            brainFreq = fftX[brain_freq_index]

            fftColor = None

            window.waveClass = next((wave for wave in WAVE_RANGES if brainFreq > wave["min"] and brainFreq <= wave["max"]), None)
            if window.waveClass is not None:
                fftColor = window.waveClass["color"]
                index_to_increase = (next(window.waveCounter[0].index(wave) for wave in window.waveCounter[0] if wave == window.waveClass["name"]))
                window.waveCounter[1][index_to_increase] += 0.2
                plot_histogram()
            else:
                fftColor = "k"
            
            window.ax2.clear()
            window.ax2.set_title("fft")
            window.ax2.plot(fftX, fftY, color=fftColor)


def plot_histogram():
    window.ax3.clear()
    window.ax3.set_title("duration spent in wave range")
    x = window.waveCounter[0]
    y = window.waveCounter[1]
    window.ax3.bar(x, y, color=window.waveCounter[2])


def video_breakdown():
    window.cap.release()
    cv2.destroyAllWindows()


def video_init():
    hasClass = True

    try:
        currentClass = window.waveClass["name"]
        print("currentClass found")
    except:
        hasClass = False
        print("no currentClass")

    if hasClass:
        window.cap = cv2.VideoCapture(VIDEO_NAME)
        cv2.namedWindow('azalea')
        load_frames()


def load_frames():
    current_frame = window.waveClass["frames"][0]
    print(current_frame)
    while window.waveClass is not None:
        counter = 0
        start_frame = window.waveClass["frames"][0]
        end_frame = window.waveClass["frames"][1]

        if current_frame >= start_frame and current_frame < end_frame:
            window.cap.set(1, current_frame)
        else:
            window.cap.set(1, start_frame)
            current_frame = start_frame

        while counter < 5:
            if current_frame + counter > end_frame:           #designed to be triggered only once per while loop, sets currentframe to start for video looping
                window.cap.set(1, start_frame)
                current_frame = start_frame
                    
            check, frame = window.cap.read()
            cv2.imshow("azalea", frame)

            current_frame += 1
            counter += 1
            cv2.waitKey(40)

    video_breakdown()


def save_file():
    fileName = QFileDialog.getSaveFileName(window, 'Save File')

    if fileName != '':
        fileName = str(fileName[0]) + '.csv'
        with open(fileName, "w+") as f:
            try:
                leftLim = int(window.tfFrom.text())
                rightLim = int(window.tfTo.text())
                np.savetxt(f, window.ydata[leftLim*50:rightLim*50], delimiter=',', header='number')
            except:      
                np.savetxt(f, window.ydata, delimiter=',', header='number')
            print("saved")
            window.lblSaveError.setText("data saved")
            window.lblSaveError.setHidden(False)


def disable_input(a: bool):
    window.btnLoad.setEnabled(not a)
    window.btnSave.setEnabled(not a)
    window.tfFrom.setEnabled(not a)
    window.tfTo.setEnabled(not a)


def save_preview():
    try:
        leftLim = int(window.tfFrom.text())
        rightLim = int(window.tfTo.text())

        window.ax1.set_xlim(left=leftLim, right=rightLim)
        window.canvas.draw()
    except:
        window.lblSaveError.setText("from and to values must be numbers")
    window.lblSaveError.setHidden(False)


window.btnLoad.clicked.connect(load_csv)
window.btnSave.clicked.connect(save_file)
window.btnRoll.clicked.connect(load_raw)
window.btnSavePreview.clicked.connect(save_preview)

window.lblSaveError.setHidden(True)
window.lblLoadError.setHidden(True)

window.show()
sys.exit(app.exec_())