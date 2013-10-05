from os import path, listdir

from Plugins.Plugin import PluginDescriptor
from Tools.LoadPixmap import LoadPixmap
from Components.MenuList import MenuList
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap 
from Screens.Console import Console

url_sc = "/usr/lib/enigma2/python/Plugins/Extensions/GreekStreamTV/update.sh"
url_pd = "/usr/lib/enigma2/python/Plugins/Extensions/GreekStreamTV/depends.sh"

def menu(menuid, **kwargs):
    if menuid == "mainmenu":
        return [("GreekStreamTV", main, "GreekStreamTV", 33)]
    return []

def main(session, **kwargs):
    try:
        session.open(GSMenu)
    except:
        print "[GreekStreamTV] Pluginexecution failed"

def autostart(reason,**kwargs):
    if reason == 0:
        print "[GreekStreamTV] no autostart"

def Plugins(**kwargs):
    return [
        PluginDescriptor(name="GreekStreamTV", where=PluginDescriptor.WHERE_MENU, description=_("Watching live stream TV"), fnc=menu),
        PluginDescriptor(
            name="GreekStreamTV",
            where=[PluginDescriptor.WHERE_EXTENSIONSMENU,PluginDescriptor.WHERE_PLUGINMENU],
            description=_("Watching live stream TV"),
            icon="plugin.png",
            fnc=main)]

class GSMenu(Screen):
    skin = """
		<screen name="GreekStreamTVList" position="center,center" size="280,220" title="GreekStreamTV">
			<widget name="menu" itemHeight="35" position="0,0" size="270,140" scrollbarMode="showOnDemand" transparent="1" zPosition="9"/>
			<ePixmap position="90,150" size="100,40" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/GreekStreamTV/plugin.png" alphatest="on" zPosition="1" />
		</screen>
           """

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        menu = []
        if path.isdir("/usr/lib/enigma2/python/Plugins/Extensions/GreekStreamTV"):
            menu.append((_("GreekStreamTV"),"/usr/lib/enigma2/python/Plugins/Extensions/GreekStreamTV/stream.xml"))
            menu.extend(self.getStreams())
            menu.append((_("Update Greek Stations"), "update"))
            menu.append((_("Install Dependencies"), "depends"))
            menu.append((_("About..."), "about"))
            self["menu"] = MenuList(menu)
            self["actions"] = ActionMap(["WizardActions", "DirectionActions"], {"ok": self.go,"back": self.close,}, -1)

    def go(self):
        if self["menu"].l.getCurrentSelection() is not None:
            choice = self["menu"].l.getCurrentSelection()[1]
            if choice.endswith(".xml"):
                try:
                    from Plugins.Extensions.GreekStreamTV.stream import main
                    main(self.session, streamFile = choice)
                except Exception as err:
                    print "[GreekStreamTV::PluginMenu] Exception: ", str(err)
                    import traceback
                    traceback.print_exc()
                    tmpMessage = "Error Loading Plugin!\n\nError: " + str(err)[:200] + "...\nInstall dependencies..."
                    self.session.open(MessageBox, tmpMessage, MessageBox.TYPE_INFO)
            elif choice == "update":
                self.session.openWithCallback(self.update, MessageBox,_("Confirm your selection, or exit"), MessageBox.TYPE_YESNO)
            elif choice == "depends":
                self.session.openWithCallback(self.depends, MessageBox,_("Confirm your selection, or exit"), MessageBox.TYPE_YESNO)
            elif choice == "about":
                tmpMessage = "For Informations and Questions please refer to www.satdreamgr.com forum.\n"
                tmpMessage += "\n\n"
                tmpMessage += "GreekStreamTV is free and source code included."
                self.session.open(MessageBox, tmpMessage, MessageBox.TYPE_INFO)

    def update(self, answer):
        if answer:
            self.session.open(Console,_("Install "),["%s update" % url_sc])

    def depends(self, answer):
        if answer:
            self.session.open(Console,_("Depedencies "),["%s update" % url_pd])

    def getStreams(self):
        xml = "/usr/lib/enigma2/python/Plugins/Extensions/GreekStreamTV/xml"
        list = []
        if path.isdir(xml):
            for file in listdir(xml):
                if file.endswith(".xml"):
                    list.append((path.splitext(file)[0].title().replace("_", " "), path.join(xml, file)))

        return list

