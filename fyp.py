import sys
import csv
import os
from PyQt5.QtWidgets import *
from PyQt5 import uic, QtCore
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

import numpy as np
import serial as serial
import serial.tools.list_ports as port_list
import time
import cv2


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

app = QApplication([])

window = uic.loadUi(resource_path('interface.ui'))

children = window.findChildren(QWidget)
print(children)

window.setFixedSize(1131, 900)

# WARNING!!!: max value of last wave range needs to be adjusted if sample rate is modified
SAMPLE_RATE = 50
SAMPLE_INTERVAL = 1.0/SAMPLE_RATE
GRAPH_UPDATE_RATE = 10

#WARNING!!!: Frame cutpoint values change from video to video
VIDEO_NAME = resource_path("hologram.mp4")
DELTA_FRAMES = (0,234)
THETA_FRAMES = (235, 342)
ALPHA_FRAMES =(605, 960)
BETA_FRAMES = (343, 604)
GAMMA_FRAMES = (961, 1261)

WAVE_RANGES = (
    {"name": "delta", "min": 0, "max": 4, "color": "r", "frames": DELTA_FRAMES},
    {"name": "theta", "min": 4, "max": 8, "color": "g", "frames": THETA_FRAMES},
    {"name": "alpha", "min": 8, "max": 14, "color": "b", "frames": ALPHA_FRAMES},
    {"name": "beta", "min": 14, "max": 25, "color": "y", "frames": BETA_FRAMES},
    {"name": "gamma", "min": 25, "max": 100, "color": "k", "frames": GAMMA_FRAMES}
)

window.xdata = np.array([])
window.ydata = np.array([])

window.isLoading = False            
window.timer = None
window.waveClass = None
window.cap = None
window.fetch_thread = None
window.training_thread = None
window.waveCounter = []
wave_names = []
wave_duration = []
wave_colors = []
for wave in WAVE_RANGES:            #create array for holding graph 3 info
    wave_names.append(wave["name"])
    wave_duration.append(0.0)
    wave_colors.append(wave["color"])

window.waveCounter.append(wave_names)
window.waveCounter.append(wave_duration)
window.waveCounter.append(wave_colors)

window.figure = Figure()
window.ax1 = window.figure.add_subplot(311, title="time-amplitude")
window.ax2 = window.figure.add_subplot(312, title="fft")
window.ax3 = window.figure.add_subplot(313, title="duration spent in wave range")
window.figure.subplots_adjust(hspace=0.6)

window.canvas = FigureCanvas(window.figure)
window.layoutPlot.addWidget(window.canvas)
window.toolbar = NavigationToolbar(window.canvas, window.wgtPlot, coordinates=True)
window.layoutPlot.addWidget(window.toolbar)         

def load_from_file():
    successful_load = load_csv()            #load csv file into memory
    if successful_load:
        clear_wave_counter()            #clear bottom graph wave counters
        fft_segments = range(SAMPLE_RATE, len(window.ydata), GRAPH_UPDATE_RATE)
        for segment in fft_segments:            #do fft analysis for previous 1s segment for each 0.2s after the 1s mark
            x, y, peak_freq = calc_current_fft(segment)
            increase_wave_counter(peak_freq)
        plot_amp()          #plot graph 1
        plot_histogram()            #plot graph 3


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

        window.xdata = np.arange(0, len(window.ydata)/SAMPLE_RATE, SAMPLE_INTERVAL)
        print("data loaded")
        return True
    else:
        window.lblLoadError.setText("Error: the file chosen is not a .csv file")
        window.lblLoadError.setHidden(False)
        return False


def plot_amp():
    window.ax1.clear()
    window.ax1.set_title("time-amplitude")
    window.ax1.set_xlabel("time (s)")
    window.ax1.set_ylabel("voltage (μV)")
    if len(window.ax1.lines) == 0:          #plot graph if graph has no line yet, update tip of line if there is
        window.ax1.plot(window.xdata, window.ydata)
    else:
        update_count = SAMPLE_RATE / GRAPH_UPDATE_RATE
        window.ax1.set_data(window.xdata[-(update_count):], window.ydata[-(update_count):])
    window.canvas.draw()


def load_raw():
    
    if not window.isLoading:            #start loading if not loading and stop loading if loading
        try:
            window.lblLoadError.setHidden(True)
            port = get_port()           #use first port in list of com ports, should detect no com ports if no legacy devices are connected
            print(port)
            window.ser = serial.Serial(port, baudrate=9600, timeout=1)          #open connection to port

            window.isLoading = True
            disable_input(window.isLoading)         #disable buttons during loading
            window.btnRoll.setText("Stop")
            clear_wave_counter()

            window.xdata = np.array([])
            window.ydata = np.array([])
            discard = window.ser.readline()         #discard fist line, normally has characters that are not data we want

            window.fetch_thread = Fetch_Thread()            #launch thread that does fetching
            window.fetch_thread.start()

            window.drawTimer = QtCore.QTimer(window)            #use main thread for drawing graphs
            window.drawTimer.timeout.connect(plot_live)
            window.drawTimer.start(200)

            window.training_thread = Training_Thread()          #launch thread that updates attention training interface
            window.training_thread.start()

        except:
            window.lblLoadError.setText("no external device found")
            window.lblLoadError.setHidden(False)
    else:
        window.fetch_thread.timer.stop()
        window.training_thread.timer.stop()
        window.drawTimer.stop()
        window.ser.close()
        window.isLoading = False
        window.waveClass = None
        window.lblLoadError.setHidden(True)

        disable_input(window.isLoading)
        window.btnRoll.setText("Roll")


def get_port():
    comports = list(port_list.comports())           #get list of com ports
    if len(comports) > 0:
        portname = str(comports[0])         #get name of first port in list
        split = portname.split(' ')         #get the comport ID which is the first few characters before first space in name
        portnum = split[0]
        return portnum
    else:
        return None


def fetch_raw():
    # start = time.time()
    try:
        if len(window.ser.readline().strip()) != 0:         #strip data of irrelevant characters such as newline
            rawdata = float(window.ser.readline().strip())
        else:
            rawdata = 0

        # print(rawdata)

        window.ydata = np.append(window.ydata, [rawdata])       #append read data to memory
        x = len(window.ydata) * 0.02
        window.xdata = np.append(window.xdata, [x])

    except ValueError:
        print("unable to convert to float")
        window.lblLoadError.setText("unable to convert to float")
        window.lblLoadError.setHidden(False)

    except:
        window.ser.close()
        window.fetch_thread.timer.stop()
        window.drawTimer.stop()
        window.isLoading = False
        window.training_thread.timer.stop()
        window.waveClass = None
        window.lblLoadError.setText("external device disconnected")
        window.lblLoadError.setHidden(False)
        window.btnRoll.setText("Roll")
        disable_input(window.isLoading)
    # end = time.time()
    # print(end-start)


def plot_live():
    x = len(window.xdata) * 0.02
    max_width = 5                                                        #set range for visible x values
    plot_amp()
    if x > max_width:                                                    #create scrolling effect of graph
        window.ax1.set_xlim(left=x-max_width, right=x)
    else:
        window.ax1.set_xlim(left=0, right=max_width)
    
    if (len(window.ydata) >= 50):                                        #calculate fft if more than 1s of data has been collected and plot graph 2 and 3
        x, y, peak = calc_current_fft(len(window.ydata) - 1)
        increase_wave_counter(peak)
        plot_fft(x, y)
        plot_histogram()
    window.canvas.draw()


def calc_current_fft(endpoint):
    sample = window.ydata[(endpoint - SAMPLE_RATE):(endpoint + 1)]      #take past 1s of data as sample
    adjusted_sample = np.subtract(sample, np.average(sample))           #sample - sample average to prevent spiking of fft graph at 0
    fftY = np.fft.fft(adjusted_sample)                                  #fft
    fftY = 2.0/SAMPLE_RATE * np.abs(fftY[:int(SAMPLE_RATE/2)])          #scale down fft results to max val 1, take latter half of fft results (positive half, negative half is just mirrored)
    fftX = np.linspace(0, int(SAMPLE_RATE/2), int(SAMPLE_RATE/2))       #x-axis values representing frequency, max frequency is half of samples/sec
    peak_index = np.where(fftY == np.amax(fftY))[0][0]                  #find y value of peak
    peak_freq = fftX[peak_index]                                        #find y value of peak
    return (fftX, fftY, peak_freq)


def clear_wave_counter():
    for count in range(len(window.waveCounter[1])):
        window.waveCounter[1][count] = 0.0


def increase_wave_counter(freq):
    window.waveClass = next((wave for wave in WAVE_RANGES if freq > wave["min"] and freq <= wave["max"]), None)         #find waveclass that frequency belongs to, uses list comprehension in attempt at optimization
    if window.waveClass is not None:
        index_to_increase = (next(window.waveCounter[0].index(wave) for wave in window.waveCounter[0] if wave == window.waveClass["name"]))         #find counter to increase, again uses list comprehension
        window.waveCounter[1][index_to_increase] += 0.2


def plot_fft(x, y):
    fftColor = None
    try:
        fftColor = window.waveClass["color"]
    except:
        fftColor = "k"
    
    window.ax2.clear()
    window.ax2.set_title("fft")
    window.ax2.set_xlabel("frequency (Hz)")
    window.ax2.plot(x, y, color=fftColor)


def plot_histogram():
    window.ax3.clear()
    window.ax3.set_title("duration spent in wave range")
    window.ax3.set_ylabel("time (s)")
    x = window.waveCounter[0]
    y = window.waveCounter[1]
    window.ax3.bar(x, y, color=window.waveCounter[2])
    window.canvas.draw()


def video_breakdown():
    window.cap.release()
    cv2.destroyAllWindows()


def video_init():           #starts attention training interface if a current wave class is found
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
    # print(current_frame)
    while window.waveClass is not None:                                     #infinite loop until waveclass is set to none which happens when you press the stop button
        counter = 0
        start_frame = window.waveClass["frames"][0]
        end_frame = window.waveClass["frames"][1]

        if current_frame >= start_frame and current_frame < end_frame:      #loop back to first frame if end is reached for segment
            window.cap.set(1, current_frame)
        else:
            window.cap.set(1, start_frame)
            current_frame = start_frame

        while counter < 5:                                                  #shows 5 frames before checking wave class again     
            if current_frame + counter > end_frame:                         #designed to be triggered only once per while loop, sets currentframe to start for video looping
                window.cap.set(1, start_frame)
                current_frame = start_frame
                    
            check, frame = window.cap.read()                                #read next frame
            cv2.imshow("azalea", frame)                                     #show frame

            current_frame += 1
            counter += 1
            cv2.waitKey(40)                                                 #frame delay of 40ms, 5 frames is 0.2s total

    video_breakdown()


def validate_from_to(from_val, to_val):                                     #validation for from and to textbox data before performing functions
    save = False
    left = None
    right = None

    if from_val == "" and to_val == "" and len(window.ydata) > 0:
        save = True

    else:
        try:
            leftLim = int(from_val)
            rightLim = int(to_val)

            if leftLim < 0 or rightLim < 0:
                raise ValueError

            elif leftLim >= rightLim:
                raise Exception("To value must be larger than From value")

            elif rightLim > 300:
                raise Exception("To value has a limit of 300")

            elif rightLim > window.xdata[-1]:
                raise Exception("To value is over current data length")

        except ValueError:
            window.lblSaveError.setText("From and To values must be positive integers") 
            window.lblSaveError.setHidden(False)

        except Exception as error:
            window.lblSaveError.setText(str(error))
            window.lblSaveError.setHidden(False)

        else:
            save = True
            left = leftLim
            right = rightLim

    return(save, left, right)


def save_file():
    save, left, right = validate_from_to(window.tfFrom.text(), window.tfTo.text())

    if save == True:     
        fileName = QFileDialog.getSaveFileName(window, 'Save File')

        if fileName != '':
            fileName = str(fileName[0]) + '.csv'
            with open(fileName, "w+") as f:
                if left != None:
                    np.savetxt(f, window.ydata[left*50:right*50], delimiter=',', header='number')
                else:
                    np.savetxt(f, window.ydata, delimiter=',', header='number')
                
                window.lblSaveError.setText("data saved")
                window.lblSaveError.setHidden(False)


def disable_input(a: bool):             #disable elements during live data loading
    window.btnLoad.setEnabled(not a)
    window.btnSave.setEnabled(not a)
    window.tfFrom.setEnabled(not a)
    window.tfTo.setEnabled(not a)


def save_preview():
    save, left, right = validate_from_to(window.tfFrom.text(), window.tfTo.text())

    if save == True:
        if left != None:
            window.ax1.set_xlim(left=left, right=right)
        else:
            window.ax1.set_xlim(left=window.xdata[0], right=window.xdata[-1])

        window.canvas.draw()


class Fetch_Thread(QtCore.QThread):
    timer = None
    def run(self):                                  #fetch data from port every 20ms
        print("fetch_thread started")
        self.timer = QtCore.QTimer()        
        self.timer.timeout.connect(fetch_raw)
        self.timer.start(20)
        self.exec()


class Training_Thread(QtCore.QThread):
    timer = None
    def run(self):                                  #start attention training interface after 5s
        print("training thread started")
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(video_init)
        self.timer.start(5000)
        self.exec()


window.btnLoad.clicked.connect(load_from_file)              #connect buttons to functions
window.btnSave.clicked.connect(save_file)
window.btnRoll.clicked.connect(load_raw)
window.btnSavePreview.clicked.connect(save_preview)

window.lblSaveError.setHidden(True)
window.lblLoadError.setHidden(True)

window.show()
sys.exit(app.exec_())