import sys
import csv
from PyQt5.QtWidgets import *
from PyQt5 import uic, QtCore
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

import numpy as np
import serial as serial


app = QApplication([])

window = uic.loadUi('interface.ui')

children = window.findChildren(QWidget)
print(children)

window.setFixedSize(1131, 636)

window.xdata = np.array([])
window.ydata = np.array([])
window.loopcount = 20
window.isLoading = False
window.timer = None

window.figure = Figure()
window.ax1 = window.figure.add_subplot(111)
window.canvas = FigureCanvas(window.figure)
window.layoutPlot.addWidget(window.canvas)
window.toolbar = NavigationToolbar(window.canvas, window.wgtPlot, coordinates=True)
window.layoutPlot.addWidget(window.toolbar)


def load_file():
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
        plot_graph()
        # plot_rolling()
    else:
        window.lblLoadError.setText("Error: the file chosen is not a .csv file")
        window.lblLoadError.setHidden(False)



def plot_graph():
    window.ax1.clear()
    window.ax1.set_xlim(left=0, right=20)
    window.xdata = np.arange(0, len(window.ydata)*0.02, 0.02)
    # fft = np.fft.fft(window.ydata[:50])
    # print(fft)
    print("plotting graph...")
    # window.ax1.plot(fft)
    window.ax1.plot(window.xdata, window.ydata)
    window.canvas.draw()

#     window.layoutPlot.removeWidget(window.canvas)
#     window.canvas.deleteLater()
#     window.layoutPlot.removeWidget(window.toolbar)
#     window.toolbar.deleteLater()



def plot_rolling():
    window.xdata = np.arange(0, 30, 0.02)
    window.ydata = window.ydata[:1500]
    window.timer = QtCore.QTimer()
    window.timer.timeout.connect(plot_rolling_animate)
    window.timer.start(20)



def plot_rolling_animate(): 
    window.ax1.clear()

    if window.loopcount > 220:
        window.ax1.set_xlim(left=0 + 0.02 * (window.loopcount-220), right=10 + 0.02 * (window.loopcount-220))
    else:
        window.ax1.set_xlim(left=0, right=10)

    window.ax1.plot(window.xdata[0:window.loopcount], window.ydata[0:window.loopcount])
    window.canvas.draw()
    window.loopcount += 1



def load_raw():
    
    if not window.isLoading:   
        window.ser = serial.Serial('COM4', baudrate=9600, timeout=1)

        window.isLoading = True
        disable_input(window.isLoading)
        window.btnRoll.setText("Stop")

        # window.canvas = FigureCanvas(window.figure)
        # window.layoutPlot.addWidget(window.canvas)
        window.ax1.clear()
        window.xdata = np.array([])
        window.ydata = np.array([])
        discard = window.ser.readline()
        window.timer = QtCore.QTimer(window)
        window.timer.timeout.connect(roll_live)
        window.timer.start(20)
    else:
        window.timer.stop()
        window.timer = None
        window.isLoading = False
        disable_input(window.isLoading)
        window.btnRoll.setText("Roll")
        window.ser.close()

        

def roll_live():
    try:
        if len(window.ser.readline().strip()) != 0:
            rawdata = int(window.ser.readline().strip())
        else:
            rawdata = 0

        window.ydata = np.append(window.ydata, [rawdata])
        x = len(window.ydata) * 0.02
        window.xdata = np.append(window.xdata, [x])
        window.ax1.clear()

        if x > 5:
            window.ax1.set_xlim(left=x-5, right=x)
        else:
            window.ax1.set_xlim(left=0, right=5)
        
        window.ax1.plot(window.xdata, window.ydata)
        window.canvas.draw()
    except:
        window.ser.close()
        window.timer.stop()
        window.timer = None

        window.lblLoadError.setText("external device disconnected")
        window.lblLoadError.setHidden(False)
        window.isLoading = False
        disable_input(window.isLoading)



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



window.btnLoad.clicked.connect(load_file)
window.btnSave.clicked.connect(save_file)
window.btnRoll.clicked.connect(load_raw)
window.btnSavePreview.clicked.connect(save_preview)

window.lblSaveError.setHidden(True)
window.lblLoadError.setHidden(True)

window.show()
sys.exit(app.exec_())