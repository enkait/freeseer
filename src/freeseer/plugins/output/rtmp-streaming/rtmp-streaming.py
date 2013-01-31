'''
freeseer - vga/presentation capture software

Copyright (C) 2011-2012  Free and Open Source Software Learning Centre
http://fosslc.org

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

For support, questions, suggestions or any other inquiries, visit:
http://wiki.github.com/Freeseer/freeseer/

@author: Jonathan Shen
'''

import ConfigParser

import pygst
pygst.require("0.10")
import gst

from PyQt4 import QtGui, QtCore

from freeseer.framework.plugin import IOutput

class RTMPOutput(IOutput):
    name = "RTMP Streaming"
    os = ["linux", "linux2", "win32", "cygwin"]
    type = IOutput.BOTH
    recordto = IOutput.STREAM
    tags = None
    
    # RTMP Streaming variables
    url = ""
    audio_quality = 0.3
    video_bitrate = 2400
    video_tune='none'
    audio_codec='lame'
    
    TUNE_VALUES = ['none', 'film', 'animation', 'grain', 'stillimage', 'psnr', 'ssim', 'fastdecode', 'zerolatency']
    AUDIO_CODEC_VALUES = ['lame', 'faac']

    def __init__(self):
        super(IOutput, self).__init__()
        self._audio_codec_producer = AudioCodecProducer(self.audio_codec)
    
	#@brief - RTMP Streaming plugin.
	# Structure for function was based primarily off the ogg function
	# Creates a bin to stream flv content to [self.url]
	# Bin has audio and video ghost sink pads 
	# Converts audio and video to flv with [flvmux] element
	# Streams flv content to [self.url]
	# TODO - Error handling - verify pad setup
    def get_output_bin(self, audio=True, video=True, metadata=None):
        bin = gst.Bin(self.name)
        
        if metadata is not None:
            self.set_metadata(metadata)
       
        # Muxer
        muxer = gst.element_factory_make("flvmux", "muxer")
        
        # Setup metadata
        # set tag merge mode to GST_TAG_MERGE_REPLACE
        merge_mode = gst.TagMergeMode.__enum_values__[2]
    
        muxer.merge_tags(self.tags, merge_mode)
        muxer.set_tag_merge_mode(merge_mode)
        
        bin.add(muxer)
        
        # RTMP sink
        rtmpsink = gst.element_factory_make('rtmpsink', 'rtmpsink')
        rtmpsink.set_property('location', self.url)
        bin.add(rtmpsink)
        
        #
        # Setup Audio Pipeline if Audio Recording is Enabled
        #
        if audio:
            audioqueue = gst.element_factory_make("queue", "audioqueue")
            bin.add(audioqueue)
            
            audioconvert = gst.element_factory_make("audioconvert", "audioconvert")
            bin.add(audioconvert)
            
            audiolevel = gst.element_factory_make('level', 'audiolevel')
            audiolevel.set_property('interval', 20000000)
            bin.add(audiolevel)
            
            audiocodec = gst.element_factory_make(self.audio_codec, "audiocodec")
            # audiocodec.set_property("quality", float(self.audio_quality))
            bin.add(audiocodec)
            
            # Setup ghost pads
            audiopad = audioqueue.get_pad("sink")
            audio_ghostpad = gst.GhostPad("audiosink", audiopad)
            bin.add_pad(audio_ghostpad)
            
            gst.element_link_many(audioqueue, audioconvert, audiolevel, audiocodec, muxer)
        
        
        #
        # Setup Video Pipeline
        #
        if video:
            videoqueue = gst.element_factory_make("queue", "videoqueue")
            bin.add(videoqueue)
            
            videocodec = gst.element_factory_make("x264enc", "videocodec")
            videocodec.set_property("bitrate", int(self.video_bitrate))
            if self.video_tune != 'none':
            	videocodec.set_property('tune', self.video_tune)
            bin.add(videocodec)
            
            # Setup ghost pads
            videopad = videoqueue.get_pad("sink")
            video_ghostpad = gst.GhostPad("videosink", videopad)
            bin.add_pad(video_ghostpad)
            
            gst.element_link_many(videoqueue, videocodec, muxer)
        
        #
        # Link muxer to rtmpsink
        #
        gst.element_link_many(muxer, rtmpsink)
        
        return bin
    
    def set_metadata(self, data):
        '''
        Populate global tag list variable with file metadata for
        vorbistag audio element
        '''
        self.tags = gst.TagList()

        for tag in data.keys():
            if(gst.tag_exists(tag)):
                self.tags[tag] = data[tag]
            else:
                #self.core.logger.log.debug("WARNING: Tag \"" + str(tag) + "\" is not registered with gstreamer.")
                pass
            
    def load_config(self, plugman):
        self.plugman = plugman
        
        try:
            self.url = self.plugman.get_plugin_option(self.CATEGORY, self.get_config_name(), "Stream URL")
            self.audio_quality = self.plugman.get_plugin_option(self.CATEGORY, self.get_config_name(), "Audio Quality")
            self.video_bitrate = self.plugman.get_plugin_option(self.CATEGORY, self.get_config_name(), "Video Bitrate")
            self.video_tune = self.plugman.get_plugin_option(self.CATEGORY, self.get_config_name(), "Video Tune")
            self.audio_codec = self.plugman.get_plugin_option(self.CATEGORY, self.get_config_name(), "Audio Codec")
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            self.plugman.set_plugin_option(self.CATEGORY, self.get_config_name(), "Stream URL", self.url)
            self.plugman.set_plugin_option(self.CATEGORY, self.get_config_name(), "Audio Quality", self.audio_quality)
            self.plugman.set_plugin_option(self.CATEGORY, self.get_config_name(), "Video Bitrate", self.video_bitrate)
            self.plugman.set_plugin_option(self.CATEGORY, self.get_config_name(), "Video Tune", self.video_tune)
            self.plugman.set_plugin_option(self.CATEGORY, self.get_config_name(), "Audio Codec", self.audio_codec)
    
    def get_widget(self):
        if self.widget is None:
            self.widget = QtGui.QWidget()
            self.widget.setWindowTitle("RTMP Streaming Options")
            
            layout = QtGui.QFormLayout()
            self.widget.setLayout(layout)
            
            #
            # Stream URL
            #
            
            # TODO: URL validation?
            
            self.label_stream_url = QtGui.QLabel("Stream URL")
            self.lineedit_stream_url = QtGui.QLineEdit()
            layout.addRow(self.label_stream_url, self.lineedit_stream_url)

            self.lineedit_stream_url.textEdited.connect(self.set_stream_url)
            
            #
            # Audio Quality
            #
            
            self.label_audio_quality = QtGui.QLabel("Audio Quality")
            self.spinbox_audio_quality = QtGui.QDoubleSpinBox()
            self.spinbox_audio_quality.setMinimum(0.0)
            self.spinbox_audio_quality.setMaximum(1.0)
            self.spinbox_audio_quality.setSingleStep(0.1)
            self.spinbox_audio_quality.setDecimals(1)
            self.spinbox_audio_quality.setValue(0.3)            # Default value 0.3
            layout.addRow(self.label_audio_quality, self.spinbox_audio_quality)
            
            self.widget.connect(self.spinbox_audio_quality, QtCore.SIGNAL('valueChanged(double)'), self.set_audio_quality)

            #
            # Audio Codec
            #
            
            self.label_audio_codec = QtGui.QLabel("Audio Codec")
            self.combobox_audio_codec = QtGui.QComboBox()
            self.combobox_audio_codec.addItems(self.AUDIO_CODEC_VALUES)
            layout.addRow(self.label_audio_codec, self.combobox_audio_codec)
            
            self.widget.connect(self.combobox_audio_codec, 
                                QtCore.SIGNAL('currentIndexChanged(const QString&)'), 
                                self.set_audio_codec)

            audioCodecSettingsButton = QtGui.QToolButton()
            audioCodecSettingsButton.setText("Settings")
            configIcon = QtGui.QIcon.fromTheme("preferences-other")
            audioCodecSettingsButton.setIcon(configIcon)
            audioCodecSettingsButton.setSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Maximum)
            audioCodecSettingsButton.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
            
            layout.addWidget(audioCodecSettingsButton)
            self.widget.connect(audioCodecSettingsButton, QtCore.SIGNAL('clicked()'), self.show_audio_codec_settings)

            #
            # Video Quality
            #
            
            self.label_video_quality = QtGui.QLabel("Video Quality (kb/s)")
            self.spinbox_video_quality = QtGui.QSpinBox()
            self.spinbox_video_quality.setMinimum(0)
            self.spinbox_video_quality.setMaximum(16777215)
            self.spinbox_video_quality.setValue(2400)           # Default value 2400
            layout.addRow(self.label_video_quality, self.spinbox_video_quality)
            
            self.widget.connect(self.spinbox_video_quality, QtCore.SIGNAL('valueChanged(int)'), self.set_video_bitrate)
            
            #
            # Video Tune
            #
            
            self.label_video_tune = QtGui.QLabel("Video Tune")
            self.combobox_video_tune = QtGui.QComboBox()
            self.combobox_video_tune.addItems(self.TUNE_VALUES)
            layout.addRow(self.label_video_tune, self.combobox_video_tune)
            
            self.widget.connect(self.combobox_video_tune, 
                                QtCore.SIGNAL('currentIndexChanged(const QString&)'), 
                                self.set_video_tune)
            
            #
            # Note
            #
            
            self.label_note = QtGui.QLabel("*For RTMP streaming, all other outputs must be set to leaky")
            layout.addRow(self.label_note)


        return self.widget

    def widget_load_config(self, plugman):
        self.load_config(plugman)
        
        self.lineedit_stream_url.setText(self.url)

        self.spinbox_audio_quality.setValue(float(self.audio_quality))
        self.spinbox_video_quality.setValue(int(self.video_bitrate))

        tuneIndex = self.combobox_video_tune.findText(self.video_tune)
        self.combobox_video_tune.setCurrentIndex(tuneIndex)
        
        acIndex = self.combobox_audio_codec.findText(self.audio_codec)
        self.combobox_audio_codec.setCurrentIndex(acIndex)

    def set_stream_url(self, text):
        self.url = text
        self.plugman.set_plugin_option(self.CATEGORY, self.get_config_name(), "Stream URL", self.url)
        self.plugman.save()
        
    def set_audio_quality(self):
        self.audio_quality = self.spinbox_audio_quality.value()
        self.plugman.set_plugin_option(self.CATEGORY, self.get_config_name(), "Audio Quality", str(self.audio_quality))
        self.plugman.save()
        
    def set_video_bitrate(self):
        self.video_bitrate = self.spinbox_video_quality.value()
        self.plugman.set_plugin_option(self.CATEGORY, self.get_config_name(), "Video Bitrate", str(self.video_bitrate))
        self.plugman.save()
        
    def set_video_tune(self, tune):
        self.video_tune = tune
        self.plugman.set_plugin_option(self.CATEGORY, self.get_config_name(), "Video Tune", str(self.video_tune))
        self.plugman.save()

    def set_audio_codec(self, codec):
        self.audio_codec = codec
        self.plugman.set_plugin_option(self.CATEGORY, self.get_config_name(), "Audio Codec", str(self.audio_codec))
        self.plugman.save()
        self._audio_codec_producer.audio_codec_name = str(self.audio_codec)
        
    def show_audio_codec_settings(self):
        self._audio_codec_producer.get_dialog().show()
        
    def get_properties(self):
        return ['StreamURL', 'AudioQuality', 'VideoBitrate', 'VideoTune', 'AudioCodec']
    
    def get_property_value(self, property):
        if property == "StreamURL":
            return self.url
        elif property == "AudioQuality":
            return self.audio_quality
        elif property == "VideoBitrate":
            return self.video_bitrate
        elif property == "VideoTune":
            return self.video_tune
        elif property == "AudioCodec":
            return self.audio_codec
        else:
            return "There's no property with such name"
        
    def set_property_value(self, property, value):
        if property == "StreamURL":
            return self.set_stream_url(value)
        elif property == "AudioQuality":
            return self.set_audio_quality(value)
        elif property == "VideoBitrate":
            return self.set_video_bitrate(value)
        elif property == "VideoTune":
            return self.set_video_tune(value)
        elif property == "AudioCodec":
            return self.set_audio_codec(value)
        else:
            return "Error: There's no property with such name" 

class AudioCodecProducer(object):
    def __init__(self, audio_codec_name):
        self._audio_codec_name = audio_codec_name
        self.set_codec(audio_codec_name)

    def get_codec(self):
        return self._audiocodec

    def set_codec(self, audio_codec_name):
        self._audiocodec = gst.element_factory_make(audio_codec_name, "audiocodec")

    @property
    def audio_codec_name(self):
        return self._audio_codec_name

    @audio_codec_name.setter
    def audio_codec_name(self, audio_codec_name):
        self._audio_codec_name = audio_codec_name
        self.set_codec(audio_codec_name)

    def get_dialog(self):
        self.dialog = QtGui.QDialog()
        self.dialog.setWindowTitle("%s Audio Codec Options" % self._audio_codec_name)

        self.dialog_layout = QtGui.QFormLayout()
        self.dialog.setLayout(self.dialog_layout)

        self.field_dict = dict()
        for name in self._audiocodec.get_property_names():
            property_label = QtGui.QLabel(name)
            property_field = QtGui.QLineEdit()
            self.field_dict[name] = property_field
            self.dialog_layout.addRow(property_label, property_field)

        self.dialog.closeButton = QtGui.QPushButton("Close")
        self.dialog_layout.addWidget(self.dialog.closeButton)
        self.dialog.connect(self.dialog.closeButton, QtCore.SIGNAL('clicked()'), self.dialog.close)
        self.dialog.setModal(True)

        return self.dialog
