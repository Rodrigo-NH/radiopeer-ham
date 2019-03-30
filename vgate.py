# SPDX-License-Identifier: BSD-2-Clause

import threading
import time
import atexit
import socket

class vgate():
    def __init__(self):
        self.__parent = super(vgate, self)
        self._basesock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.inputport = None
        self.outputport = None
        self._baseip = None
        self._remoteip = None
        self._ttime1 = 0
        self._ttime2 = 0

    def startgate(self):
        self._basesock.bind(('', self.inputport))
        y = threading.Thread(target=self._basetimeout, args=())
        y.start()
        r = threading.Thread(target=self._rungate, args=())
        r.start()

    def _basetimeout(self):
        while True:
            if time.time() - self._ttime1 > 20:
                self._baseip = None
            if time.time() - self._ttime2 > 20:
                self._remoteip = None
            time.sleep(1)

    def _rungate(self):
        while True:
            st =""
            data, addr = self._basesock.recvfrom(1024)
            try:
                st = data.decode('utf-8')
            except:
                pass
            if st == 'HELLO GATE-BASE':
                self._baseip = addr[0]
                self._ttime1 = int(time.time())
                #print("Gate get base")
            elif st == 'HELLO GATE-REMOTE':
                self._remoteip = addr[0]
                self._ttime2 = int(time.time())
                #print("Gate get remote")
            elif self._baseip is not None and self._remoteip is not None:
                addr = addr[0]
                if addr == self._baseip:
                    self._basesock.sendto(data, (self._remoteip, self.outputport))
                if addr == self._remoteip:
                    self._basesock.sendto(data, (self._baseip, self.outputport))

A = vgate()
A.inputport = 5007
A.outputport = 5006
A.startgate()