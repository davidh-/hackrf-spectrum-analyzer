import sys
import subprocess
import datetime
import numpy as np
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg
from pyqtgraph.colormap import ColorMap

import signal

def signal_handler(signal, frame):
    global app
    print("\nCTRL-C detected. Stopping the program...")
    app.quit()

# Create a separate thread to run the hackrf_sweep process
class HackRFSweepThread(QtCore.QThread):
    data_received = QtCore.pyqtSignal(list)

    def __init__(self, command):
        super().__init__()
        self.command = command
        self.should_run = True  # Add this line

    def stop(self):  # Add this method
        self.should_run = False

    def run(self):
        process = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
        for line in iter(process.stdout.readline, ""):
            if not self.should_run:  # Add this check
                break
    
            data = process_data_line(line)
            if data is not None:
                # print("Data received in HackRFSweepThread:", data)
                self.data_received.emit(list(data))

        process.terminate()  # Terminate the process when the thread stops running
        process.wait()


def process_data_line(line):
    timestamp, timestamp_time, start_freq, stop_freq, step, _, *db_values = line.strip().split(', ')
    print("2", timestamp, timestamp_time, start_freq, stop_freq, step, _, *db_values)
    start_freq = float(start_freq) / 1e9  # Convert to GHz
    stop_freq = float(stop_freq) / 1e9  # Convert to GHz
    step = float(step) / 1e6  # Convert to MHz
    # print(db_values)
    l = len(db_values)
    # print(l)
    if l == 6:
        # print("exit")
        exit()
    db_values = list(map(float, db_values))
    # print("3", start_freq, stop_freq, step, db_values)
    return start_freq, stop_freq, step, db_values

class SpectrumAnalyzer(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        self.win = pg.GraphicsLayoutWidget()
        layout.addWidget(self.win)

        self.spectrum_plot = self.win.addPlot(title="Spectrum Analyzer")
        self.spectrum_plot.setLabels(left="Power (dB)", bottom="Frequency (GHz)")
        self.spectrum_plot.setYRange(-80, 0)
        self.spectrum_plot.setXRange(0, 6)
        self.spectrum_curve = self.spectrum_plot.plot(pen="y")

        self.win.nextRow()

        self.waterfall_plot = self.win.addPlot(title="Waterfall View")
        self.waterfall_plot.setLabels(left="Time (s)", bottom="Frequency (GHz)")
        self.waterfall_plot.setYRange(0, 5)
        self.waterfall_plot.setXRange(0, 100)
        self.waterfall_img = pg.ImageItem()
        self.waterfall_plot.addItem(self.waterfall_img)

        viridis_colors = [
            (68, 1, 84), (72, 35, 116), (64, 67, 135), (52, 94, 141), (41, 120, 142), (32, 144, 140), (34, 167, 132),
            (68, 190, 112), (121, 209, 81), (189, 222, 38), (253, 231, 36)
        ]
        viridis_colormap = pg.ColorMap(np.linspace(0, 1, len(viridis_colors)), viridis_colors)
        self.waterfall_img.setLookupTable(viridis_colormap.getLookupTable())

        self.waterfall_img.setLevels([-80, 0])

    def update_spectrum(self, data):
        start_freq, stop_freq, step, db_values = data
        freqs = np.arange(start_freq, stop_freq, step / 1e3)  # Convert step to GHz

        # print("Spectrum data received:", data)

        min_len = min(len(freqs), len(db_values))
        freqs = freqs[:min_len]
        db_values = db_values[:min_len]

        # print("update:", db_values)
        # print("len freqs", len(freqs), "len db_values", len(db_values))
        self.spectrum_curve.setData(freqs, db_values)

    def update_waterfall(self, data):
        start_freq, stop_freq, step, db_values = data
        
        img_data = self.waterfall_img.image
        if img_data is None:
            img_data = np.empty((100, len(db_values)))
            img_data[:] = np.nan
        img_data = np.roll(img_data, 1, axis=0)
        img_data[0] = db_values
        self.waterfall_img.setImage(img_data)

        # print("Waterfall data received:", data)  # Add this line



class MyApp(QtWidgets.QApplication):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyle("Fusion")

def main():
    global app
    app = MyApp(sys.argv)
    window = SpectrumAnalyzer()


    # Set up signal handler for CTRL-C
    signal.signal(signal.SIGINT, signal_handler)


    # Start the thread to run the hackrf_sweep process
    command = "hackrf_sweep"
    hackrf_thread = HackRFSweepThread(command)
    hackrf_thread.data_received.connect(window.update_spectrum)
    hackrf_thread.data_received.connect(window.update_waterfall)
    hackrf_thread.start()
    window.show()
    exit_code = app.exec_()
    hackrf_thread.stop()  # Stop the thread when the application exits
    hackrf_thread.wait()  # Wait for the thread to finish

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
