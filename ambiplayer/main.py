import os
import sys
import soundfile as sf
import sounddevice as sd

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QPushButton,
    QMainWindow, 
    QApplication, 
    QLabel, 
    QFileDialog, 
    QFormLayout,
    QDial,
    QComboBox,
    QWidget, 
    QGridLayout
)

from audio_processing import AudioPlayer

from pathlib import Path
root_path = str(Path(__file__).parent.parent)

# TODO: Save position in file when output device changes
# TODO: Support for files with channels > 2

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.player = None

        self.setMaximumHeight(500)
        self.setMinimumHeight(300)
        self.setMaximumWidth(500)
        self.setMinimumWidth(300)

        layout = QGridLayout()
        self.setWindowTitle('Audio Player')

        # label shown in main part of window
        self.label = QLabel('Audio Player')
        layout.addWidget(self.label, 0, 0, 1, 3, Qt.AlignmentFlag.AlignCenter)

        # find default output device
        device_list = list(sd.query_devices())
        output_device_names = \
            [device['name'] for device in device_list
             if device['max_output_channels'] > 0]
        self.output_device_indices = \
            [device['index'] for device in device_list
             if device['max_output_channels'] > 0]

        # create dropdown menu for device selection
        self.device_dropdown = QComboBox()
        # add devices with output channels available
        self.device_dropdown.addItems(output_device_names)
        self.device_dropdown.setCurrentIndex(
            self.output_device_indices.index(sd.default.device[1]))
        self.device_dropdown.currentIndexChanged.connect(self.device_changed)
        layout.addWidget(self.device_dropdown, 1, 1, 2, 2)
        
        self.device_index = sd.default.device[1]

        form = QFormLayout()
        form.addRow('Output Device:', self.device_dropdown)
        layout.addLayout(form, 1, 0, 1, 3, Qt.AlignmentFlag.AlignJustify)
        
        # play/pause button
        self.play_button = QPushButton(
            QIcon(root_path + '/icons/play.png'), 'Play', self)
        self.play_button.clicked.connect(self.playButtonClicked)
        self.play_button.setMinimumWidth(100)
        self.play_button.setMaximumWidth(100)
        self.play_button.setMinimumHeight(100)
        layout.addWidget(self.play_button, 2, 0)

        # stop button
        self.stop_button = QPushButton(
            QIcon(root_path + '/icons/stop.png'), 'Stop', self)
        self.stop_button.clicked.connect(self.stopButtonClicked)
        self.stop_button.setMinimumWidth(100)
        self.stop_button.setMaximumWidth(100)
        self.stop_button.setMinimumHeight(100)
        layout.addWidget(self.stop_button, 2, 1)

        # open button
        self.open_button = QPushButton(
            QIcon(root_path + '/icons/open-folder.png'), 'Open', self)
        # self.open_button.setStatusTip('Open File')
        self.open_button.clicked.connect(self.openButtonClicked)
        self.open_button.setMinimumWidth(100)
        self.open_button.setMaximumWidth(100)
        self.open_button.setMinimumHeight(100)
        layout.addWidget(self.open_button, 2, 2)
        
        # layout.addWidget(QDial(), 4, 0)
        # layout.addWidget(QDial(), 4, 1)

        widget = QWidget()
        widget.setLayout(layout)

        self.setCentralWidget(widget)

    def playButtonClicked(self, playing):
        if not self.player: return False

        if playing:
            self.play_button.setIcon(QIcon(root_path + '/icons/pause.png'))
            self.play_button.setText('Pause')
            self.play_button.setToolTip('Pause')
            self.player.play()
            self.device_dropdown.setDisabled(True)
        else:
            self.play_button.setIcon(QIcon(root_path + '/icons/play.png'))
            self.play_button.setText('Play')
            self.play_button.setToolTip('Play')
            self.player.pause()
            self.device_dropdown.setDisabled(False)

    def stopButtonClicked(self):
        if not self.player: return False

        self.play_button.setChecked(False)
        self.play_button.setIcon(QIcon(root_path + '/icons/play.png'))
        self.play_button.setText('Play')
        self.play_button.setToolTip('Play')
        self.player.stop()
        self.device_dropdown.setDisabled(False)

    def openButtonClicked(self, _):
        # set up dialog box
        dialog = QFileDialog()
        # single file only
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        # accepted audio formats
        dialog.setNameFilter('Audio (*.wav *.flac)')
        # run the dialog
        dialog.exec()
        # retrieve filepath
        filepath = dialog.selectedFiles()
        
        try:
            self.filepath = filepath[0]
            self.label.setText(os.path.basename(self.filepath))
        except ValueError:
            print('Invalid filepath')
            return False

        self.file, self.fs = sf.read(self.filepath)
        print(self.device_index)
        self.player = AudioPlayer(self.file, self.fs, self.device_index)
        self.play_button.setCheckable(True)

    def device_changed(self, index):
        self.device_index = self.output_device_indices[index]
        if self.player:
            self.player = AudioPlayer(self.file, self.fs, self.device_index)

app = QApplication(sys.argv)
window = MainWindow()
window.show()

app.exec()
