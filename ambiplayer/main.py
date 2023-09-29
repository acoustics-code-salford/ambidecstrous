import os
import sys
import decoders
import soundfile as sf
import sounddevice as sd

from PyQt6.QtCore import Qt, QSize
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

# TODO: Support for files with channels > 2

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # general properties of the main window
        layout = QGridLayout()
        self.setWindowTitle('Ambisonic Audio Player')
        self.setFixedSize(QSize(500,300))

        # label shown in main part of window
        self.label = QLabel('')
        layout.addWidget(self.label, 1, 0, 1, 4, Qt.AlignmentFlag.AlignCenter)

        # find default output device
        device_list = list(sd.query_devices())
        # list devices with output channels available
        output_device_names = \
            [device['name'] for device in device_list
             if device['max_output_channels'] > 0]
        self.output_device_indices = \
            [device['index'] for device in device_list
             if device['max_output_channels'] > 0]
        self.output_device_channels = \
            [device['max_output_channels'] for device in device_list
             if device['max_output_channels'] > 0]

        # menu for device selection
        menu_index = self.output_device_indices.index(sd.default.device[1])
        self.device_dropdown = QComboBox()
        self.device_dropdown.addItems(output_device_names)
        self.device_dropdown.setCurrentIndex(menu_index)
        self.device_dropdown.currentIndexChanged.connect(self.device_changed)
        self.device_index = sd.default.device[1]
        self.device_n_channels = self.output_device_channels[menu_index]
        print(output_device_names[menu_index])

        # menu for decoder selection
        self.decoder_dropdown = QComboBox()
        self.decoder_dropdown.addItems(['Raw', 'Stereo UHJ', 'Ambisonics'])
        self.decoder_dropdown.currentIndexChanged.connect(self.decoder_changed)
        self.decoder_dropdown.model().item(1).setEnabled(False)
        self.decoder_dropdown.model().item(2).setEnabled(False)
        
        # menu for channel format selection
        self.channel_format_dropdown = QComboBox()
        self.channel_format_dropdown.addItems(['ACN', 'FuMa'])
        self.channel_format_dropdown.setDisabled(True)

        # add all menus to a form
        form = QFormLayout()
        form.addRow('Output Device:', self.device_dropdown)
        form.addRow('Decoder:', self.decoder_dropdown)
        form.addRow('Channel Format:', self.channel_format_dropdown)
        layout.addLayout(form, 0, 0, 1, 4, Qt.AlignmentFlag.AlignJustify)
        
        # play button
        self.play_button = QPushButton(
            QIcon(root_path + '/icons/play.png'), 'Play', self)
        self.play_button.clicked.connect(self.playButtonClicked)
        self.play_button.setMinimumWidth(100)
        self.play_button.setMaximumWidth(100)
        self.play_button.setMinimumHeight(100)
        self.play_button.setCheckable(True)
        self.play_button.setDisabled(True)
        layout.addWidget(self.play_button, 2, 0)

        # pause button
        self.pause_button = QPushButton(
            QIcon(root_path + '/icons/pause.png'), 'Pause', self)
        self.pause_button.clicked.connect(self.pauseButtonClicked)
        self.pause_button.setMinimumWidth(100)
        self.pause_button.setMaximumWidth(100)
        self.pause_button.setMinimumHeight(100)
        self.pause_button.setCheckable(True)
        self.pause_button.setDisabled(True)
        layout.addWidget(self.pause_button, 2, 1)

        # stop button
        self.stop_button = QPushButton(
            QIcon(root_path + '/icons/stop.png'), 'Stop', self)
        self.stop_button.clicked.connect(self.stopButtonClicked)
        self.stop_button.setMinimumWidth(100)
        self.stop_button.setMaximumWidth(100)
        self.stop_button.setMinimumHeight(100)
        self.stop_button.setCheckable(True)
        self.stop_button.setDisabled(True)
        layout.addWidget(self.stop_button, 2, 2)

        # open button
        self.open_button = QPushButton(
            QIcon(root_path + '/icons/open-folder.png'), 'Open', self)
        self.open_button.clicked.connect(self.openButtonClicked)
        self.open_button.setMinimumWidth(100)
        self.open_button.setMaximumWidth(100)
        self.open_button.setMinimumHeight(100)
        layout.addWidget(self.open_button, 2, 3)
        
        # layout.addWidget(QDial(), 4, 0)
        # layout.addWidget(QDial(), 4, 1)

        # set up main display
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        # audio properties
        self.player = None

    @property
    def n_input_channels(self):
        return self._n_input_channels
    
    @n_input_channels.setter
    def n_input_channels(self, n):
        if n < 4:
            self.decoder_dropdown.model().item(1).setEnabled(False)
            self.decoder_dropdown.model().item(2).setEnabled(False)
        elif n >= 4:
            self.decoder_dropdown.model().item(1).setEnabled(True)
            self.decoder_dropdown.model().item(2).setEnabled(True)

    def playButtonClicked(self):
        self.stop_button.setChecked(False)
        self.pause_button.setDisabled(False)
        self.pause_button.setChecked(False)
        self.play_button.setChecked(True)
        self.player.play()
        self.device_dropdown.setDisabled(True)
        self.decoder_dropdown.setDisabled(True)
        self.channel_format_dropdown.setDisabled(True)
    
    def pauseButtonClicked(self):
        self.play_button.setChecked(False)
        self.pause_button.setChecked(True)
        self.player.pause()
        self.device_dropdown.setDisabled(False)
        self.decoder_dropdown.setDisabled(False)

        if self.decoder_dropdown.currentIndex() != 0:
            self.channel_format_dropdown.setDisabled(False)

    def stopButtonClicked(self):
        self.stop_button.setChecked(True)
        self.play_button.setChecked(False)
        self.pause_button.setChecked(False)
        self.player.stop()
        self.pause_button.setDisabled(True)
        self.device_dropdown.setDisabled(False)
        self.decoder_dropdown.setDisabled(False)
        
        if self.decoder_dropdown.currentIndex() != 0:
            self.channel_format_dropdown.setDisabled(False)

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
        
        if not filepath: return False
        self.filepath = filepath[0]
        self.label.setText(os.path.basename(self.filepath))

        self.file, self.fs = sf.read(self.filepath)
        # needs getter/setter method for enabling decoder menu options
        self.n_input_channels = self.file.shape[1]

        match self.decoder_dropdown.currentIndex():
            case 0: decoder = decoders.raw
            case 1: decoder = decoders.stereo_uhj
            case 2: pass # Ambisonics
        # MIGHT NEED TO STORE CURRENT DECODER
        self.player = AudioPlayer(
            self.file, 
            self.fs, 
            self.device_index, 
            self.device_n_channels,
            decoder
        )

        self.play_button.setDisabled(False)
        self.stop_button.setDisabled(False)
        self.stop_button.setChecked(True)

    def device_changed(self, index):
        self.device_index = self.output_device_indices[index]
        if not self.player: return False
        self.player = AudioPlayer(self.file,
                                  self.fs,
                                  self.device_index,
                                  self.device_n_channels,
                                  current_frame=self.player.current_frame
        )
    
    def decoder_changed(self, index):
        match index:
            case 0:
                self.channel_format_dropdown.setDisabled(True)
                if self.player: self.player.decoder = decoders.raw
            case 1:
                self.channel_format_dropdown.setDisabled(False)
                if self.player: self.player.decoder = decoders.stereo_uhj
            case 2:
                self.channel_format_dropdown.setDisabled(False)
                if self.player: pass # Ambisonics

app = QApplication(sys.argv)
window = MainWindow()
window.show()

app.exec()
