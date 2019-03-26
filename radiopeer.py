# SPDX-License-Identifier: BSD-2-Clause

import time
import sys
import traceback
import socket
import struct
import threading
import curses

try:
    import RPi.GPIO as gpio
except:
    pierr = "Rpi.GPIO not loaded"

try:
    import audiodev
    import audiospeex

except:
    print('cannot load audiodev.so and audiospeex.so, please set the PYTHONPATH')
    traceback.print_exc()
    sys.exit(-1)

class radiopeer():
    #os.system('clear')

    def __init__(self):
        self.__parent = super(radiopeer, self)
        self._loopthread = False
        self._rqueue = []
        self._squeue = []
        self._timec = 0
        self._packlag = 0
        self._remotepacklag = 0
        self._thispeer_ipin = None
        self._thispeer_portin = None
        self._sockin = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self._sockout = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self._upsample = None
        self._downsample = None
        self._enc = None
        self._dec = None
        self._to_peer_port = None
        self._peerip = None
        self._cardname = 'default'
        self._stimeout = 0
        self._stimeout_ct = True
        self._isbase = True
        self._statsndpack = " "
        self._statrecvpack = " "
        self._pttstate = "OFF"
        self._pttstaterec = 0
        self._recbuffer = 0
        self._buffcontrol = True
        self._stdscr = curses.initscr()
        self._lock = threading.RLock()
        self.termcolor = False
        self._screenrefresh = 0
        self.pttpin = 0
        self._soundbuff = []
        self._databuff = []

    def startout(self):
        self._loopthread = True
        self.__ctrdev(1)
        self._stdscr.nodelay(1)
        self.__raspberryconf()
        #self._stdscr.timeout(0)
        self._sockin.bind((self._thispeer_ipin, self._thispeer_portin))
        g = threading.Thread(target=self.__getpacks, args=())
        g.setDaemon(True)
        g.start()
        r = threading.Thread(target=self.__sendpacks, args=())
        r.setDaemon(True)
        r.start()
        s = threading.Thread(target=self.__statscreen, args=())
        s.setDaemon(True)
        s.start()
        y = threading.Thread(target=self.__getkeyboard, args=())
        y.setDaemon(True)
        y.start()

    def getcardinfo(self):
        d1 = audiodev.get_api_name()
        d2 = audiodev.get_devices()
        print("API name: "+str(d1))
        print("Sound devices: "+str(d2))

    def __raspberryconf(self):
        if self.pttpin != 0 and self._isbase:
            gpio.setmode(gpio.BCM)
            gpio.setup(self.pttpin, gpio.OUT)  # PTT
            gpio.output(self.pttpin, False)

    def __getkeyboard(self):
        while self._loopthread == True:
            #stdscr = curses.initscr()
            self._lock.acquire()
            curses.noecho()
            self._stdscr.keypad(1)
            key = self._stdscr.getch()
            if not self._isbase:
                if key == 80 or key == 112:
                    if self._pttstate == "ON":
                        self._pttstate = "OFF"
                    else:
                        self._pttstate = "ON"

            if key == 101:
                if self.pttpin != 0 and self._isbase:
                    gpio.output(self.pttpin, False)
                    gpio.cleanup()
                curses.echo()
                curses.endwin()
                self._loopthread = False
                #os.kill(os.getppid(), signal.SIGKILL)
            curses.flushinp()
            self._lock.release()
            time.sleep(0.1)

    def __statscreen(self):
        while self._loopthread == True:
            tt = int(time.time())
            if  tt - self._screenrefresh > 5:
                self._stdscr.clear()
                self._stdscr.refresh()
                self._screenrefresh = tt

            mode = "Remote"
            if self._isbase:
                mode = "Base"
            # https://stackoverflow.com/questions/18551558/how-to-use-terminal-color-palette-with-curses
            if self.termcolor == True:
                curses.start_color()
                curses.init_pair(1, 254, 0)
                cl1 = curses.color_pair(1)
                curses.init_pair(2, 227, 0)
                cl2 = curses.color_pair(2)
                curses.init_pair(3, 46, 0)
                cl3 = curses.color_pair(3)
                curses.init_pair(4, 111, 0)
                cl4 = curses.color_pair(4)
                curses.init_pair(5, 196, 0)
                cl5 = curses.color_pair(5)
                curses.init_pair(6, 172, 0)
                cl6 = curses.color_pair(6)
            else:
                cl1 = 0
                cl2 = 0
                cl3 = 0
                cl4 = 0
                cl5 = 0
                cl6 = 0

            lline = "-"*60
            # maker color disponible: export TERM='xterm-256color'

            try:
                self._stdscr.addstr(0, 0, "(P)", cl6)
                self._stdscr.addstr(0, 3, "TT switch", cl1)
                self._stdscr.addstr(0, 14, "(E)", cl6)
                self._stdscr.addstr(0, 17, "xit", cl1)
                self._stdscr.addstr(1, 0, lline, cl4)
                self._stdscr.addstr(2, 0, "Mode:" , cl1)
                self._stdscr.clrtoeol()
                self._stdscr.addstr(2, 8, mode, cl3)
                self._stdscr.clrtoeol()
                self._stdscr.addstr(3, 0, lline, cl4)
                self._stdscr. clrtoeol()
                self._stdscr.addstr(4, 0, "Status:", cl1)
                self._stdscr.clrtoeol()
                self._stdscr.addstr(4, 8, "Listening on", cl1)
                self._stdscr.addstr(4, 21, self._thispeer_ipin + ":" + str(self._thispeer_portin), cl3)
                self._stdscr.clrtoeol()
                self._stdscr.addstr(4, 44, "To Port:", cl1)
                self._stdscr.clrtoeol()
                self._stdscr.addstr(4, 53, str(self._to_peer_port), cl3)
                self._stdscr.clrtoeol()
                self._stdscr.addstr(5, 0, "Peer:", cl1)
                self._stdscr.clrtoeol()
                self._stdscr.addstr(5, 6, str(self._peerip), cl3)
                self._stdscr.clrtoeol()
                self._stdscr.addstr(5, 23, "Lag:", cl1)
                self._stdscr.clrtoeol()
                self._stdscr.addstr(5, 28, str(self._packlag), cl3)
                self._stdscr.clrtoeol()
                self._stdscr.addstr(5, 35, "Remote Lag:", cl1)
                self._stdscr.clrtoeol()
                self._stdscr.addstr(5, 47, str(self._remotepacklag), cl3)
                self._stdscr.clrtoeol()
                self._stdscr.addstr(6, 0, lline, cl4)
                self._stdscr.clrtoeol()
                self._stdscr.addstr(7, 0, "Send: ", cl1)
                self._stdscr.clrtoeol()
                self._stdscr.addstr(7, 6, self._statsndpack, cl2)
                self._stdscr.clrtoeol()
                self._stdscr.addstr(7, 11, "Receive:", cl1)
                self._stdscr.clrtoeol()
                self._stdscr.addstr(7, 20, self._statrecvpack, cl2)
                if self._buffcontrol == True and self._stimeout_ct == False:
                    self._stdscr.addstr(7, 35, "Buffering ...", cl5)
                self._stdscr.clrtoeol()
                self._stdscr.clrtoeol()
                self._stdscr.addstr(8, 0, lline, cl4)
                self._stdscr.clrtoeol()
                if not self._isbase:
                    self._stdscr.addstr(9, 0, "PTT:", cl1)
                    if self._pttstate == "ON":
                        tc = cl5
                    else:
                        tc = cl3
                    self._stdscr.addstr(9, 5, self._pttstate, tc)
                    self._stdscr.clrtoeol()
                    self._stdscr.addstr(10, 0, lline, cl4)
                    self._stdscr.move(12,0)
                else:
                    self._stdscr.move(10, 0)
                if pierr != None and self._isbase:
                    self._stdscr.addstr(13, 0, "Warning: " + pierr, cl5)
            except:
                pass
            time.sleep(0.05)

    def setcardname(self, card):
        self._cardname = card

    def thispeer(self, thispeer_ip, thispeer_port, to_peer_port):
        self._thispeer_ipin = thispeer_ip
        self._thispeer_portin = thispeer_port
        self._to_peer_port = to_peer_port

    def getbaseon(self, peerip):
        self._peerip = peerip
        self._isbase = False

    def __sendpacks(self):
        while self._loopthread == True:
            self.__timeoutcheck()
            pl = len(self._squeue)
            if pl == 26 and self._isbase == False or pl == 26 and self._stimeout_ct == False:
                packtime = int(time.time())
                self._squeue.append(packtime)
                if self._pttstate == "ON":
                    pttstate = 1
                else:
                    pttstate = 0
                self._squeue.append(pttstate)
                self._squeue.append(self._packlag)

                packer = struct.Struct('38s ' * 26 + 'I' + 'I' + 'I')
                packed_data = packer.pack(*self._squeue)
                #self._sockout.sendto(packed_data, ("10.10.0.4", self._to_peer_port))
                self._sockout.sendto(packed_data, (self._peerip, self._to_peer_port))
                self._squeue = []
                if self._statsndpack == " ":
                    self._statsndpack = "X"
                else:
                    self._statsndpack = " "
            elif len(self._squeue) > 26:
                self._statsndpack = " "
                self._peerip = None
                self._squeue = []

    def __timeoutcheck(self):
        time.sleep(0.01) # Avoid hog CPU
        if int(time.time()) - self._stimeout > 2:
            self._stimeout_ct = True
            self._statrecvpack = " "
            self._packlag = 0
        else:
            self._stimeout_ct = False

    def __getpacks(self):
        while self._loopthread == True:
            data, addr = self._sockin.recvfrom(1024)  # buffer size is 1024 bytes
            self._stimeout = int(time.time())
            if self._peerip is None:
                self._peerip = addr[0]
            unpacker = struct.Struct('38s ' * 26 + 'I' + 'I' + 'I')
            ntq = unpacker.unpack(data)
            for fragment in ntq:
                self._rqueue.append(fragment)
            self.__packprocs()
            if self._statrecvpack == " ":
                self._statrecvpack = "X"
            else:
                self._statrecvpack = " "

    def __ctrdev(self, ct):
        if ct == 1:
            audiodev.open(output=self._cardname, input=self._cardname,
                          format="l16", sample_rate=48000, frame_duration=20,
                          output_channels=2, input_channels=1, flags=0x01, callback=self.__datainout)
        if ct == 0:
            audiodev.close()

    def defbuffer(self, buff):
        self._recbuffer = buff * 50

    def __packprocs(self):
        if len(self._rqueue) > self._recbuffer and self._buffcontrol == True:
            self._buffcontrol = False
        if len(self._rqueue) != 0 and self._buffcontrol == False:
            while len(self._rqueue) > 0:
                for x in range(0, 26):
                    self._soundbuff.append(self._rqueue.pop(0))
                for x in range(26, 29):
                    self._databuff.append(self._rqueue.pop(0))

    def __getparams(self):
        self._timec = self._timec + 1
        if self._timec == 26:
            self._timec = 0
            self._packlag = int(time.time()) - self._databuff.pop(0)
            pttstate = self._databuff.pop(0)
            self._remotepacklag = self._databuff.pop(0)
            if pttstate == 1 and self._pttstaterec == 0:
                self._pttstaterec = 1
                gpio.output(self.pttpin, True)
            elif pttstate == 0 and self._pttstaterec == 1:
                self._pttstaterec = 0
                gpio.output(self.pttpin, False)

    def __uglywave(self):
        res = b''
        pt = 0
        for y in range(0, 320):
            pt = pt + 1
            if pt > 76:
                uu = 0
                pt = 0
            else:
                uu = 125
            ba = bytes([uu])
            res = res + ba
        return res

    def __datainout(self, fragment, timestamp, userdata):
        fragout1, self._downsample = audiospeex.resample(fragment, input_rate=48000, output_rate=8000, state=self._downsample)
        #fragout1 = self.__uglywave()
        fragout2, self._enc = audiospeex.lin2speex(fragout1, sample_rate=8000, state=self._enc)
        self._squeue.append(fragout2)
        try:
            if len(self._soundbuff) != 0:
                self.__getparams()
                fragin1 = self._soundbuff.pop(0)
                fragin3, self._dec = audiospeex.speex2lin(fragin1, sample_rate=8000, state=self._dec)
                fragin4, self._upsample = audiospeex.resample(fragin3, input_rate=8000, output_rate=48000, state=self._upsample)
                fragin5 = fragin4 + fragin4  # create stereo
                return fragin5
            else:
                fragment = b'\x00' * 3840  # silence sample at output_rate=48000
                self._buffcontrol = True
                if self.pttpin !=0 and self._isbase:
                    gpio.output(self.pttpin, False)
                return fragment
        except:
            pass

    def close(self):
        audiodev.close()
        self._loopthread = False