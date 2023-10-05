import os
import sys
import math
import json
import glob
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
    QComboBox,
    QWidget,
    QGridLayout
)

from utils import load_mapping

from pathlib import Path
from audio_processing import AudioPlayer
root_path = str(Path(__file__).parent.parent)

# TODO: take into account channel numbering for decoder matrix
# TODO: take into account loudspeaker distance
# (calculate delays - nearest whole sample to begin with)
# TODO: use a basic 'stereo' mapping to test all of the above

# TODO: implement Furse-Malham as AmbisonicDecoder subclass

# TODO: decoder behaviour before audio clip is selected
# how to make menus behave properly if clip does not support settings?
# TODO: re-add FuMa menu item
# TODO: separate data struct / object to manage variables, available options
# TODO: playback progress bar
# TODO: display warnings in window
# TODO: {!}LONG TERM GOAL{!} loudspeaker layout editor window


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.player = None

        # general properties of the main window
        layout = QGridLayout()
        self.setWindowTitle('Ambidecstrous')
        self.setFixedSize(QSize(500, 300))

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
        self.device_channels_list = \
            [device['max_output_channels'] for device in device_list
             if device['max_output_channels'] > 0]

        # menu for device selection
        menu_index = self.output_device_indices.index(sd.default.device[1])
        self.device_dropdown = QComboBox()
        self.device_dropdown.addItems(output_device_names)
        self.device_dropdown.setCurrentIndex(menu_index)
        self.device_dropdown.currentIndexChanged.connect(self.device_changed)
        self.device_index = sd.default.device[1]
        self.device_n_channels = self.device_channels_list[menu_index]

        # menu for decoder selection
        self.decoder_dropdown = QComboBox()
        self.decoder_dropdown.addItems(['Raw', 'Stereo UHJ', 'Ambisonics'])
        self.decoder_dropdown.currentIndexChanged.connect(self.decoder_changed)
        self.decoder_dropdown.model().item(1).setEnabled(False)
        self.decoder_dropdown.model().item(2).setEnabled(False)
        self.decoder_dropdown.setDisabled(True)

        # menu for Ambisonic order
        self.ambi_order_dropdown = QComboBox()
        self.ambi_order_dropdown.addItems(['0', '1', '2', '3', '4'])
        self.ambi_order_dropdown.setDisabled(True)
        self.ambi_order_dropdown.currentIndexChanged.connect(
            self.ambi_order_changed
        )

        # menu for loudspeaker mapping
        self.loudspeaker_mapping_dropdown = QComboBox()
        mapping_files = glob.glob('mappings/*json')
        mapping_names = [list(x.keys())[0]
                         for x in [json.load(open(file, 'r'))
                         for file in mapping_files]]
        self.loudspeaker_mapping_dropdown.addItems(mapping_names)
        self.loudspeaker_mapping_dropdown.setDisabled(True)
        self.mapping_files = mapping_files
        self.loudspeaker_mapping_dropdown.currentIndexChanged.connect(
            self.loudspeaker_mapping_changed
        )
        self.loudspeaker_mapping_changed(
            self.loudspeaker_mapping_dropdown.currentIndex()
        )

        # add menus to a form
        form = QFormLayout()
        form.addRow('Output Device:', self.device_dropdown)
        form.addRow('Decoder:', self.decoder_dropdown)
        form.addRow('Ambisonic Order:', self.ambi_order_dropdown)
        form.addRow('Loudspeaker Mapping:', self.loudspeaker_mapping_dropdown)
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

        # set up main display
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        self.decoder_changed(0)

    @property
    def n_input_channels(self):
        return self._n_input_channels

    @n_input_channels.setter
    def n_input_channels(self, n):
        self.decoder_dropdown.setDisabled(False)

        # set Ambisonic orders available to select
        max_available_order = math.isqrt(n) - 1
        self.ambi_order_dropdown.setCurrentIndex(max_available_order)
        for i in range(len(self.ambi_order_dropdown)):
            if i > max_available_order:
                self.ambi_order_dropdown.model().item(i).setEnabled(False)
            else:
                self.ambi_order_dropdown.model().item(i).setEnabled(True)

        if max_available_order < 1:
            # Ambisonic decoding not available
            self.decoder_dropdown.model().item(1).setEnabled(False)
            self.decoder_dropdown.model().item(2).setEnabled(False)
        else:
            self.decoder_dropdown.model().item(1).setEnabled(True)
            self.decoder_dropdown.model().item(2).setEnabled(True)

        self.max_available_order = max_available_order
        self._n_input_channels = n

    @property
    def decoder(self):
        return self._decoder

    @decoder.setter
    def decoder(self, decoder):
        if self.player:
            self.player.decoder = decoder
        self._decoder = decoder

    @property
    def loudspeaker_mapping(self):
        return self._loudspeaker_mapping

    @loudspeaker_mapping.setter
    def loudspeaker_mapping(self, mapping):
        self._loudspeaker_mapping = mapping

        if not self.player:
            return False
        if isinstance(self.player.decoder, decoders.AmbisonicDecoder):
            self.decoder.loudspeaker_mapping = mapping

    def playButtonClicked(self):
        self.stop_button.setChecked(False)
        self.pause_button.setDisabled(False)
        self.pause_button.setChecked(False)
        self.play_button.setChecked(True)
        self.player.play()
        self.device_dropdown.setDisabled(True)
        self.decoder_dropdown.setDisabled(True)
        self.ambi_order_dropdown.setDisabled(True)
        self.loudspeaker_mapping_dropdown.setDisabled(True)

    def pauseButtonClicked(self):
        self.play_button.setChecked(False)
        self.pause_button.setChecked(True)
        self.player.pause()
        self.device_dropdown.setDisabled(False)
        self.decoder_dropdown.setDisabled(False)

        if self.decoder_dropdown.currentIndex() == 2:
            self.ambi_order_dropdown.setDisabled(False)
            self.loudspeaker_mapping_dropdown.setDisabled(False)

    def stopButtonClicked(self):
        self.stop_button.setChecked(True)
        self.play_button.setChecked(False)
        self.pause_button.setChecked(False)
        self.player.stop()
        self.pause_button.setDisabled(True)
        self.device_dropdown.setDisabled(False)
        self.decoder_dropdown.setDisabled(False)

        if self.decoder_dropdown.currentIndex() == 2:
            self.ambi_order_dropdown.setDisabled(False)
            self.loudspeaker_mapping_dropdown.setDisabled(False)

    def openButtonClicked(self, _):
        # set up dialog box
        dialog = QFileDialog()
        # allow single file only
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        # set accepted formats
        dialog.setNameFilter('Audio (*.wav *.flac)')
        dialog.exec()
        filepath = dialog.selectedFiles()

        if not filepath:
            return False
        self.filepath = filepath[0]
        self.label.setText(os.path.basename(self.filepath))

        self.file, self.fs = sf.read(self.filepath)
        self.n_input_channels = self.file.shape[1]

        self.player = AudioPlayer(
            self.file,
            self.fs,
            self.device_index,
            self.device_n_channels,
            self.decoder
        )

        self.play_button.setDisabled(False)
        self.stop_button.setDisabled(False)
        self.stop_button.setChecked(True)

    def device_changed(self, index):
        self.device_index = self.output_device_indices[index]
        if not self.player:
            return False
        self.player = AudioPlayer(
            self.file,
            self.fs,
            self.device_index,
            self.device_n_channels,
            self.decoder,
            current_frame=self.player.current_frame
        )

    def decoder_changed(self, index):
        match index:
            case 0:
                self.ambi_order_dropdown.setDisabled(True)
                self.loudspeaker_mapping_dropdown.setDisabled(True)
                self.decoder = decoders.RawDecoder(self.device_n_channels)
            case 1:
                self.ambi_order_dropdown.setDisabled(True)
                self.loudspeaker_mapping_dropdown.setDisabled(True)
                self.decoder = decoders.UHJDecoder(self.device_n_channels)
            case 2:
                self.ambi_order_dropdown.setDisabled(False)
                self.ambi_order_dropdown.setCurrentIndex(
                    self.max_available_order
                )
                self.loudspeaker_mapping_dropdown.setDisabled(False)
                self.decoder = decoders.ACNDecoder(
                    self.device_n_channels,
                    self.loudspeaker_mapping,
                    self.ambi_order
                )

    def loudspeaker_mapping_changed(self, index):
        # TODO: streamline this - we only need to save the index and
        # pass this to decoder with load_mapping function args

        mapping_file = self.mapping_files[index]
        name = self.loudspeaker_mapping_dropdown.itemText(index)
        self.loudspeaker_mapping = load_mapping(mapping_file, name)

    def ambi_order_changed(self, index):
        self.ambi_order = index
        self.decoder.N = index


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
