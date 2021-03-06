"""
GREEK STREAM TV

Ideas & Sources:
StreamTV (Black Hole image)
https://github.com/chrippa/livestreamer
http://code.google.com/p/airplayer/source/browse/trunk/AirPlayer/mediabackends/e2_media_backend.py
https://github.com/DonDavici/DreamPlex/blob/master/src/DP_Player.py
http://code.google.com/p/archivy-czsk/source/browse/trunk/engine/player/player.py?r=77
...all others...

"""

from sys import path
path.append("/usr/lib/enigma2/python/Plugins/Extensions/GreekStreamTV")

import os
import ssl
from time import sleep
from thread import start_new_thread
from xml.etree.cElementTree import ElementTree

from enigma import eTimer, ePicLoad, loadPNG, eServiceReference, iPlayableService, iServiceInformation
from enigma import gFont, eListboxPythonMultiContent, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.InfoBarGenerics import InfoBarAudioSelection, InfoBarNotifications
from Components.Label import Label
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Pixmap import Pixmap
from Components.AVSwitch import AVSwitch
from Components.ServiceEventTracker import ServiceEventTracker
from Tools.Directories import resolveFilename, SCOPE_PLUGINS

from livestreamer import Livestreamer

PLUGIN_PATH = resolveFilename(SCOPE_PLUGINS, "Extensions/GreekStreamTV")


class SelectQuality(Screen):
    skin = """
		<screen name="SelectQuality" position="center,center" size="280,180" title="Select Quality">
			<widget name="menu" itemHeight="35" position="0,0" size="270,130" scrollbarMode="showOnDemand" transparent="1" zPosition="9"/>
			<widget name="info" position="0,135" zPosition="2" size="270,40" font="Regular;22" foregroundColor="#ffffff" transparent="1" halign="center" valign="center" />
		</screen>
           """

    def __init__(self, session, streams, selectedFunc, enableWrapAround=False):
        Screen.__init__(self, session)
        self.session = session
        self["info"] = Label("...")
        self.selectedFunc = selectedFunc
        menu = [ (str(sn[0]), sn[1]) for sn in streams.items() ]
        self["menu"] = MenuList(menu, enableWrapAround)
        self["actions"] = ActionMap(["OkCancelActions"], {
            "ok": self.okbuttonClick,
            "cancel": self.cancelClick
        })

    def getCurrent(self):
        cur = self["menu"].getCurrent()
        return cur and cur[1]

    def okbuttonClick(self):
        self["info"].setText("Please Wait...")
        self.timer = eTimer()
        self.timer.callback.append(self.StartStreaming)
        self.timer.start(100, 1)

    def StartStreaming(self):
        self.timer.stop()
        self.selectedFunc(self.getCurrent())

    def up(self):
        self["menu"].up()

    def down(self):
        self["menu"].down()

    def cancelClick(self):
        self.close(False)


class GreekStreamTVPlayer(Screen, InfoBarAudioSelection, InfoBarNotifications):
    skin = """
               <screen name="GreekStreamTVPlayer" flags="wfNoBorder" position="0,570" size="1280,190" title="GreekStreamTV Player" backgroundColor="#41000000" >
                   <ePixmap position="80,25" size="117,72" pixmap="%s/channel_background.png" zPosition="-1" transparent="1" alphatest="blend" />
                   <widget name="channel_icon" position="121,43" zPosition="10" size="35,35" backgroundColor="#41000000" />
                   <widget name="channel_name" position="250,20" size="650,40" font="Regular;36" halign="left" valign="center" foregroundColor="#ffffff" backgroundColor="#41000000" />
                   <widget name="channel_uri" position="250,70" size="950,60" font="Regular;22" halign="left" valign="top" foregroundColor="#ffffff" backgroundColor="#41000000" />
                   <widget source="session.CurrentService" render="Label" position="805,20" size="300,40" font="Regular;30" halign="right" valign="center" foregroundColor="#f4df8d" backgroundColor="#41000000" transparent="1" >
                       <convert type="ServicePosition">Position,ShowHours</convert>
                   </widget>
               </screen>
           """ % (PLUGIN_PATH)

    PLAYER_IDLE    = 0
    PLAYER_PLAYING = 1
    PLAYER_PAUSED  = 2

    def __init__(self, session, service, stopPlayer, chName, chURL, chIcon):
        Screen.__init__(self, session)
        InfoBarAudioSelection.__init__(self)
        InfoBarNotifications.__init__(self)

        isEmpty = lambda x: x is None or len(x)==0 or x == "None"
        if isEmpty(chName): chName = "Unknown"
        if isEmpty(chURL):  chURL  = "Unknown"
        if isEmpty(chIcon): chIcon = "default.png"
        chIcon = "%s/icons/%s" % (PLUGIN_PATH, chIcon)
        self.session = session
        self.service = service
        self.stopPlayer = stopPlayer

        self.setTitle(chName)

        self["actions"] = ActionMap(["OkCancelActions", "InfobarSeekActions", 
                                     "MediaPlayerActions", "MovieSelectionActions"], {
            "ok": self.doInfoAction,
            "cancel": self.doExit,
            "stop": self.doExit,
            "playpauseService": self.playpauseService,
        }, -2)

        self.__event_tracker = ServiceEventTracker(screen = self, eventmap = {
            iPlayableService.evSeekableStatusChanged: self.__seekableStatusChanged,
            iPlayableService.evStart: self.__serviceStarted,
            iPlayableService.evEOF: self.__evEOF,
            iPlayableService.evUser + 10: self.__evAudioDecodeError,
            iPlayableService.evUser + 11: self.__evVideoDecodeError,
            iPlayableService.evUser + 12: self.__evPluginError,
        })

        self.hidetimer = eTimer()
        self.hidetimer.timeout.get().append(self.doInfoAction)

        self.state = self.PLAYER_IDLE
        self.__seekableStatusChanged()
 
        self.onClose.append(self.__onClose)
        self.doPlay()

        self["channel_icon"] = Pixmap()
        self["channel_name"] = Label(chName)
        self["channel_uri"]  = Label(chURL)

        self.picload = ePicLoad()
        self.scale   = AVSwitch().getFramebufferScale()
        self.picload.PictureData.get().append(self.cbDrawChannelIcon)
        self.picload.setPara((35, 35, self.scale[0], self.scale[1], False, 0, "#00000000"))
        self.picload.startDecode(chIcon)

    def cbDrawChannelIcon(self, picInfo=None):
        ptr = self.picload.getData()
        if ptr != None:
            self["channel_icon"].instance.setPixmap(ptr.__deref__())
            self["channel_icon"].show()

    def __onClose(self):
        self.session.nav.stopService()

    def __seekableStatusChanged(self):
        service = self.session.nav.getCurrentService()
        if service is not None:
            seek = service.seek()
            if seek is None or not seek.isCurrentlySeekable():
                self.setSeekState(self.PLAYER_PLAYING)

    def __serviceStarted(self):
        self.state = self.PLAYER_PLAYING
        self.__seekableStatusChanged()

    def __evEOF(self):
        self.doExit()

    def __evAudioDecodeError(self):
        currPlay = self.session.nav.getCurrentService()
        sAudioType = currPlay.info().getInfoString(iServiceInformation.sUser + 10)
        print "[__evAudioDecodeError] audio-codec %s can't be decoded by hardware" % (sAudioType)
        self.session.open(MessageBox, _("This Dreambox can't decode %s streams!") % sAudioType, type=MessageBox.TYPE_INFO, timeout=20)

    def __evVideoDecodeError(self):
        currPlay = self.session.nav.getCurrentService()
        sVideoType = currPlay.info().getInfoString(iServiceInformation.sVideoType)
        print "[__evVideoDecodeError] video-codec %s can't be decoded by hardware" % (sVideoType)
        self.session.open(MessageBox, _("This Dreambox can't decode %s streams!") % sVideoType, type=MessageBox.TYPE_INFO, timeout=20)

    def __evPluginError(self):
        currPlay = self.session.nav.getCurrentService()
        message = currPlay.info().getInfoString(iServiceInformation.sUser + 12)
        print "[__evPluginError]" , message
        self.session.open(MessageBox, message, type=MessageBox.TYPE_INFO, timeout=20)

    def __setHideTimer(self):
        self.hidetimer.start(5000)

    def doExit(self):
        print "[GreekStreamTVPlayer::doExit]"
        self.stopPlayer()
        self.close()

    def setSeekState(self, wantstate):
        service = self.session.nav.getCurrentService()
        if service is None:
            print "[GreekStreamTV:: ::setSeekState] No Service found"
            return

        pauseable = service.pause()
        if pauseable is not None:
            if wantstate == self.PLAYER_PAUSED:
                pauseable.pause()
                self.state = self.PLAYER_PAUSED
                if not self.shown:
                    self.hidetimer.stop()
                    self.show()
            elif wantstate == self.PLAYER_PLAYING:
                pauseable.unpause()
                self.state = self.PLAYER_PLAYING
                if self.shown:
                    self.__setHideTimer()
        else:
            self.state = self.PLAYER_PLAYING

    def doInfoAction(self):
        if self.shown:
            self.hidetimer.stop()
            self.hide()
        else:
            self.show()
            if self.state == self.PLAYER_PLAYING:
                self.__setHideTimer()

    def doPlay(self):
        if self.state == self.PLAYER_PAUSED:
            if self.shown:
                self.__setHideTimer()
        self.state = self.PLAYER_PLAYING
        self.session.nav.playService(self.service)
        if self.shown:
            self.__setHideTimer()

    def playpauseService(self):
        print "[GreekStreamTVPlayer::playpauseService] State ", self.state
        if self.state == self.PLAYER_PLAYING:
            self.setSeekState(self.PLAYER_PAUSED)
        elif self.state == self.PLAYER_PAUSED:
            self.setSeekState(self.PLAYER_PLAYING)


class StreamURIParser:
    def __init__(self, xml):
        self.xml = xml

    def parseStreamList(self):
        tvlist = []
        tree = ElementTree()
        tree.parse(self.xml)
        for iptv in tree.findall("iptv"):
            tvlist.append({
                "name" : str(iptv.findtext("name")).title(), 
                "icon" : str(iptv.findtext("icon")),
                "type" : str(iptv.findtext("type")), 
                "uri"  : self.parseStreamURI(str(iptv.findtext("uri")))
            })
        return sorted(tvlist, key=lambda item: item["name"])

    def parseStreamURI(self, uri):
        uriInfo = {}
        splitedURI = uri.split()
        uriInfo["URL"] = splitedURI[0]
        for x in splitedURI[1:]:
            i = x.find("=")
            uriInfo[x[:i]] = str(x[i+1:])
        return uriInfo

def streamListEntry(entry):
    uriInfo = entry[1].get("uri")
    return [entry,
        (eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST,5,1,35,35,loadPNG("%s/icons/%s" % (PLUGIN_PATH, str(entry[1].get("icon"))) )),
        (eListboxPythonMultiContent.TYPE_TEXT,45,7,360,37,0,RT_HALIGN_LEFT,entry[0]),
        (eListboxPythonMultiContent.TYPE_TEXT,410,7,400,37,1,RT_HALIGN_LEFT,str(uriInfo.get("URL")))
    ]

class GreekStreamTVList(Screen):
    skin = """
 		<screen name="GreekStreamTVList" position="center,center" size="800,400" title="GreekStreamTV List (Livestreamer) v3.2">
			<widget name="streamlist" position="0,0" size="800,360" backgroundColor="#000000" zPosition="10" scrollbarMode="showOnDemand" />
			<widget name="info" position="0,365" zPosition="2" size="800,35" font="Regular;22" foregroundColor="#ffffff" transparent="1" halign="center" valign="center" />
		</screen>
           """

    def __init__(self, session, streamFile = None):
        self.session = session
        Screen.__init__(self, session)

        self["info"] = Label("...")
        self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", 
                                      "ColorActions", "SetupActions", "NumberActions", "MenuActions"], {
            "ok"    : self.keyOK,
            "cancel": self.keyCancel,
            "up"    : self.keyUp,
            "down"  : self.keyDown,
            "left"  : self.keyLeft,
            "right" : self.keyRight,
        }, -1)

        self.streamBin  = "/usr/bin/rtmpdump"
        self.streamPipe = "/tmp/greekstreamtv.avi"

        if not streamFile:
            self.streamFile = resolveFilename(SCOPE_PLUGINS, "Extensions/GreekStreamTV/stream.xml")
        else:
            self.streamFile = streamFile

        self.lvstreamer = Livestreamer()

        self.streamList = []
        self.makeStreamList()

        self.streamMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
        self.streamMenuList.l.setFont(0, gFont("Regular", 22))
        self.streamMenuList.l.setFont(1, gFont("Regular", 18))
        self.streamMenuList.l.setItemHeight(37)
        self["streamlist"] = self.streamMenuList
        self.streamMenuList.setList(map(streamListEntry, self.streamList))

        self.onLayoutFinish.append(self.layoutFinished)

        self.beforeService  = None
        self.currentService = None
        self.playerStoped   = False
        self.keyLocked = False
        self.pd = None
        self.qsel = None

    def layoutFinished(self):
        os.system("killall -9 rtmpdump")
        self.showName()

    def keyLeft(self):
        if self.keyLocked:
            return
        self["streamlist"].pageUp()
        self.showName()

    def keyRight(self):
        if self.keyLocked:
            return
        self["streamlist"].pageDown()
        self.showName()

    def keyUp(self):
        if self.keyLocked:
            return
        self["streamlist"].up()
        self.showName()

    def keyDown(self):
        if self.keyLocked:
            return
        self["streamlist"].down()
        self.showName()

    def keyCancel(self):
        self.LivestreamerStop()
        if "/usr/lib/enigma2/python/Plugins/Extensions/GreekStreamTV" in path:
            path.remove("/usr/lib/enigma2/python/Plugins/Extensions/GreekStreamTV")
        self.close()

    def showName(self):
        try:
            tmpName = self["streamlist"].getCurrent()[0][1].get("name")
        except:
            tmpName = "..."
        self["info"].setText(tmpName)

    def keyOK(self):
        print "[GreekStreamTVList::keyOK]"
        if self.keyLocked:
            return

        uriName  = self["streamlist"].getCurrent()[0][1].get("name")
        self["info"].setText("Starting %s Please Wait..." % uriName)
        self.timer = eTimer()
        self.timer.callback.append(self.StartStream)
        self.timer.start(100, 1)

    def StartStream(self):
        self.timer.stop()
        self.keyLocked        = True
        self.beforeService    = None
        self.currentService   = None
        self.playerStoped     = False
        self.pd               = None

        streamInfo  = self["streamlist"].getCurrent()[0][1]
        uriInfo     = streamInfo.get("uri")
        typeInfo    = streamInfo.get("type").split(":")
        protocol    = typeInfo[0]
        serviceType = typeInfo[1]
        bufferSize  = typeInfo[2]
        url         = uriInfo.get("URL")

        if protocol == "rtmp":
            url += " "
            url += " ".join(["%s=%s" % (key, value) for (key, value) in uriInfo.items() if key != "URL"])
            url = " ".join(url.split())
            print "[GreekStreamTVList::keyOK] URL is ", url, " URI is ", uriInfo
            self.doStreamAction(url, serviceType, bufferSize)
        elif protocol in ("rtsp", "http"):
            self.doStreamAction(url, serviceType, bufferSize)
        elif protocol == "livestreamer":
            channel = None
            streams = None
            try:
                url += " "
                url += " ".join(["%s=%s" % (key, value) for (key, value) in uriInfo.items() if key != "URL"])
                url = " ".join(url.split())
                print "[GreekStreamTVList::keyOK] URL is ", url, " URI is ", uriInfo
                channel = self.lvstreamer.resolve_url(url)
                streams = channel.get_streams()
                print "[GreekStreamTVList::keyOK] Streams: ", streams.keys()
                print "[GreekStreamTVList::keyOK] Streams: ", streams.items()
                if len(streams) == 3 and "best" in streams and "worst" in streams:
                    self.streamPreBuffer(streams["best"])
                elif len(streams) == 0:
                    raise Exception("No Streams Found")
                else:
                    self.qsel = self.session.openWithCallback(self.QualitySelClosed, SelectQuality, streams, self.streamPreBuffer)
            except Exception as err:
                print "[GreekStreamTVList::keyOK::Exception] Error: ", err
                tmpMessage = "An Error Occured: " + str(err)[:200] + "..."
                self.session.openWithCallback(self.stopPlayer, MessageBox, tmpMessage, type=MessageBox.TYPE_ERROR, timeout=20)
        else:
            print "[GreekStreamTVList::keyOK] Unknown Protocol: ", protocol
            tmpMessage = "Unknown Protocol: " + protocol
            self.session.openWithCallback(self.stopPlayer, MessageBox, tmpMessage, type=MessageBox.TYPE_WARNING, timeout=20)

    def QualitySelClosed(self, recursive):
        if self.qsel:
            self.qsel.close()
        self.qsel = None
        self.stopPlayer()

    def streamPreBuffer(self, stream):
        fd = None
        try:
            fd = stream.open()
            prebuffer = fd.read(8196 * 128) #PREBUFFER
            if len(prebuffer) == 0:
               raise Exception("No Data Received From Stream Server")
            start_new_thread(self.streamCopy, (fd,prebuffer))
            sleep(1.5)
            self.doStreamAction(self.streamPipe)
        except Exception as err:
            if fd and hasattr(fd, "close"):
                fd.close()
            print "[GreekStreamTVList::streamPreBuffer::Exception] Error: ", err
            tmpMessage = "An Error Occured while buffering: " + str(err)[:200] + "..."
            self.session.openWithCallback(self.stopPlayer, MessageBox, tmpMessage, type=MessageBox.TYPE_ERROR, timeout=20)

    def streamCopy(self, fd, prebuffer):
        print "[GreekStreamTVList::streamCopy]"
        if os.access(self.streamPipe, os.F_OK):
            os.remove(self.streamPipe)
        os.mkfifo(self.streamPipe)
        self.pd = open(self.streamPipe, "wb")
        try:
            self.pd.write(prebuffer)
            while self is not None and self.session is not None and not self.playerStoped:
                data = fd.read(8192)
                if len(data) == 0:
                    break
                self.pd.write(data)
            print "[GreekStreamTVList:streamCopy] playerStoped"
            self.pd.close()
            if hasattr(fd, "close"):
                fd.close()
            fd = None
        except Exception as err:
            print "[GreekStreamTVList::streamCopy] Exception: ", err
        finally:
            self.playerStoped = True
            if fd and hasattr(fd, "close"):
                fd.close()

    def LivestreamerStop(self):
        print "[GreekStreamTVList::LivestreamStop]"
        self["info"].setText("...")
        self.keyLocked = False
        self.playerStoped = True
        os.system("killall -9 rtmpdump")
        sleep(0.5)
        if self.pd:
            try: self.pd.close()
            except:
                sleep(0.5)
                try: self.pd.close()
                except: pass
        if self.qsel is not None:
            self.qsel.close(False)
        self.pd   = None
        self.qsel = None

    def doStreamAction(self, url=None, serviceType=4097, bufferSize=None):
        if url is None:
            url=self.streamPipe
            self.streamPlayerTimer.stop()

        try: serviceType = int(serviceType)
        except: serviceType = 4097
        try: bufferSize = int(bufferSize)
        except: bufferSize = None

        service = eServiceReference(serviceType, 0, url)

        #if bufferSize is not None:
        #    service.setData(2, bufferSize*1024)

        streamInfo = self["streamlist"].getCurrent()[0][1]
        service.setName(str(streamInfo.get("name")))
        uriInfo    = streamInfo.get("uri")

        self.beforeService  = self.session.nav.getCurrentlyPlayingServiceReference()
        self.currentService = self.session.openWithCallback(self.onStreamFinished,
                                    GreekStreamTVPlayer, 
                                    service, 
                                    stopPlayer=self.stopPlayer,
                                    chName=str(streamInfo.get("name")),
                                    chURL =str(uriInfo.get("URL")),
                                    chIcon=str(streamInfo.get("icon")))

    def stopPlayer(self, params=None):
        print "[GreekStreamTV::stopPlayer]"
        if params is None or isinstance(params, bool):
            self.playerStoped = True
            self.LivestreamerStop()
            return

    def onStreamFinished(self):
        print "[GreekStreamTV::onStreamFinished]"
        self.LivestreamerStop()
        self.session.nav.playService(self.beforeService)
        print "[GreekStreamTV::onStreamFinished] player done!!"

    def makeStreamList(self):
        try: streamDB = StreamURIParser(self.streamFile).parseStreamList()
        except Exception as err:
            print "[GreekStreamTV::makeStreamList] Error: ", err
            streamDB = []
        self.streamList = [ (x.get("name"), x) for x in streamDB ]

def main(session, **kwargs):
    session.open(GreekStreamTVList, kwargs['streamFile'])
                                                           
def Plugins(**kwargs):
    return PluginDescriptor(
        name = _("GreekStreamTVPlayer"),
        description = "Watching live stream TV",
        where = PluginDescriptor.WHERE_PLUGINMENU,
        fnc = main,
        icon = "plugin.png")

