from __future__ import annotations

import hashlib
from enum import Enum, auto
from PySide6.QtCore import QObject, Signal, QLockFile, QDir
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class InstanceResult(Enum):
    STARTED = auto()
    ALREADY_RUNNING = auto()
    ERROR = auto()


class SingleInstanceGuard(QObject):
    activation_requested = Signal()

    def __init__(self, server_name: str):
        super().__init__()
        self._server_name = server_name
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._server.newConnection.connect(self._accept_connections)
        digest = hashlib.sha256(server_name.encode()).hexdigest()[:24]
        self._lock = QLockFile(QDir.tempPath() + "/quiz-assistant-" + digest + ".lock")
        self._lock.setStaleLockTime(0)
        self._owned = False
        self.error = ""

    def _activate_existing(self):
        probe = QLocalSocket()
        probe.connectToServer(self._server_name)
        if not probe.waitForConnected(250):
            return False
        probe.write(b"activate")
        probe.waitForBytesWritten(250)
        probe.disconnectFromServer()
        return True

    def acquire(self):
        if self._owned:
            return InstanceResult.STARTED
        if self._activate_existing():
            return InstanceResult.ALREADY_RUNNING
        if not self._lock.tryLock(750):
            if self._activate_existing():
                return InstanceResult.ALREADY_RUNNING
            self.error = "Inny proces uruchamia program albo blokada instancji jest niedostępna. Spróbuj ponownie."
            return InstanceResult.ERROR
        if self._activate_existing():
            self._lock.unlock()
            return InstanceResult.ALREADY_RUNNING
        QLocalServer.removeServer(self._server_name)
        if not self._server.listen(self._server_name):
            self.error = "Nie można utworzyć lokalnego kanału aplikacji. Sprawdź uprawnienia lub uruchom komputer ponownie."
            self._lock.unlock()
            return InstanceResult.ERROR
        self._owned = True
        return InstanceResult.STARTED

    def _accept_connections(self):
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is not None:
                socket.disconnected.connect(socket.deleteLater)
                self.activation_requested.emit()
                socket.disconnectFromServer()

    def close(self):
        if self._owned:
            self._server.close()
            QLocalServer.removeServer(self._server_name)
            self._lock.unlock()
            self._owned = False
