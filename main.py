import sys
import asyncio
import websockets
import time
from PyQt5 import QtWidgets, QtCore
import qasync
import pyqtgraph as pg
import struct

# Kod klienta WebSocket: wyłącza client-side pingi, aby uniknąć "no close frame received or sent"
default_close_code = 1000

class DataReceiver(QtCore.QObject):
    dataReceived = QtCore.pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.running = True
        self.ws = None

    async def run(self, uri):
        """
        Utrzymuje nieprzerwane połączenie WebSocket. Wyłącza ping_interval,
        dzięki czemu nie czekamy na odpowiedzi ping/pong.
        """
        while self.running:
            try:
                print(f"Próba połączenia z {uri}...")
                # Wyłączamy client-side pingi
                async with websockets.connect(
                        uri,
                        ping_interval=None,
                        close_timeout=5,
                        max_size=2**20
                    ) as ws:
                    self.ws = ws
                    print("Połączono z ESP32 przez WebSocket!")
                    # Odbieraj dane w pętli
                    async for message in ws:
                        if isinstance(message, bytes) and len(message) == 28:
                            try:
                                v1, v2, v3, c1, c2, c3, temp = struct.unpack('<7f', message)
                                data = {
                                    "Voltage1": v1,
                                    "Voltage2": v2,
                                    "Voltage3": v3,
                                    "Current1": c1,
                                    "Current2": c2,
                                    "Current3": c3,
                                    "Temperature": temp
                                }
                                self.dataReceived.emit(data)
                            except Exception as e:
                                print("Błąd parsowania danych binarnych:", e)
                        else:
                            print(f"Błędna długość wiadomości: {len(message)} bajtów")
            except websockets.exceptions.ConnectionClosedOK:
                # Normalne zakończenie (oznaczone kodem 1000)
                print("Połączenie zamknięte normalnie.")
                break
            except websockets.exceptions.ConnectionClosedError as e:
                # Zerwanie połączenia bez close frame -> retry
                print("ConnectionClosedError, retrying…", e)
            except asyncio.CancelledError:
                print("Task anulowany, wychodzę z run().")
                break
            except Exception:
                import traceback; traceback.print_exc()
            finally:
                self.ws = None
                if self.running:
                    # krótki delay przed ponowną próbą
                    await asyncio.sleep(1)
        print("DataReceiver.run() zakończone.")

    async def close_connection(self):
        """Zatrzymuje pętlę i wysyła close frame (kod 1000)."""
        self.running = False
        if self.ws:
            try:
                await self.ws.close(code=default_close_code, reason="Client exit")
                print("Wysłano poprawny close frame.")
            except Exception as e:
                print("Błąd przy zamykaniu ws:", e)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monitor danych ESP32")

        # Bufory danych i wykresy
        self.time_data = []
        self.voltage1_data, self.voltage2_data, self.voltage3_data = [], [], []
        self.current1_data, self.current2_data, self.current3_data = [], [], []
        self.temp_data = []
        self.start_time = time.time()

        plots = []
        for label in ("Voltage 1", "Voltage 2", "Voltage 3", "Current 1", "Current 2", "Current 3", "Temperature"):
            pw = pg.PlotWidget(title=label)
            pw.setBackground('#2b2b2b')
            for ax in ('left', 'bottom'):
                pw.getAxis(ax).setPen('w')
                pw.getAxis(ax).setTextPen('w')
            plots.append(pw)

        self.voltage1_curve, self.voltage2_curve, self.voltage3_curve = [plots[i].plot() for i in range(3)]
        self.current1_curve, self.current2_curve, self.current3_curve = [plots[i].plot() for i in range(3,6)]
        self.temp_curve = plots[6].plot()

        # Sterowanie
        self.voltageLineEdit = QtWidgets.QLineEdit()
        self.setVoltageButton = QtWidgets.QPushButton("Ustaw napięcie")
        controlGroup = QtWidgets.QGroupBox("Sterowanie")
        cg_layout = QtWidgets.QVBoxLayout(controlGroup)
        cg_layout.addWidget(QtWidgets.QLabel("Podaj napięcie:"))
        cg_layout.addWidget(self.voltageLineEdit)
        cg_layout.addWidget(self.setVoltageButton)

        left = QtWidgets.QVBoxLayout(); [left.addWidget(p) for p in plots[:3]]
        center = QtWidgets.QVBoxLayout(); [center.addWidget(p) for p in plots[3:6]]
        right = QtWidgets.QVBoxLayout(); right.addWidget(plots[6]); right.addWidget(controlGroup); right.addStretch()

        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(left, 1)
        main_layout.addLayout(center, 1)
        main_layout.addLayout(right, 1)
        container = QtWidgets.QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.setStyleSheet("""
            QWidget { background-color: #2b2b2b; color: #fff; font-size:14px }
            QLineEdit, QPushButton { background:#3c3f41; border:1px solid #5c5c5c; padding:5px; border-radius:4px }
            QPushButton:hover { background:#4b4f51 }
            QGroupBox { border:1px solid #5c5c5c; border-radius:6px; padding:10px; margin-top:10px; font-weight:bold }
        """)

        # Sygnały i połączenia
        self.setVoltageButton.clicked.connect(self.sendVoltageCommand)
        self.dataReceiver = DataReceiver()
        self.dataReceiver.dataReceived.connect(self.updateData)
        QtCore.QTimer.singleShot(0, self.start_websocket_connection)

    def start_websocket_connection(self):
        uri = "ws://192.168.87.229/ws"
        asyncio.create_task(self.dataReceiver.run(uri))

    def updateData(self, data):
        t = time.time() - self.start_time
        self.time_data.append(t)
        for key, arr in zip(("Voltage1","Voltage2","Voltage3","Current1","Current2","Current3","Temperature"),
                            (self.voltage1_data,self.voltage2_data,self.voltage3_data,
                             self.current1_data,self.current2_data,self.current3_data,self.temp_data)):
            arr.append(data.get(key, 0))

        max_points = 100
        for arr in (self.time_data, self.voltage1_data, self.voltage2_data, self.voltage3_data,
                    self.current1_data, self.current2_data, self.current3_data, self.temp_data):
            if len(arr) > max_points:
                del arr[:-max_points]

        # Aktualizacja wykresów
        self.voltage1_curve.setData(self.time_data, self.voltage1_data)
        self.voltage2_curve.setData(self.time_data, self.voltage2_data)
        self.voltage3_curve.setData(self.time_data, self.voltage3_data)
        self.current1_curve.setData(self.time_data, self.current1_data)
        self.current2_curve.setData(self.time_data, self.current2_data)
        self.current3_curve.setData(self.time_data, self.current3_data)
        self.temp_curve.setData(self.time_data, self.temp_data)

    def sendVoltageCommand(self):
        cmd = f"SET_VOLTAGE:{self.voltageLineEdit.text()}"
        print(f"Wysyłam komendę: {cmd}")

    def closeEvent(self, event):
        asyncio.create_task(self.dataReceiver.close_connection())
        event.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main()
