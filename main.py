import sys
import asyncio
import websockets
import time
from PyQt5 import QtWidgets, QtCore
import qasync
import pyqtgraph as pg
import struct


# Klasa odpowiedzialna za odbiór danych z WebSocket
class DataReceiver(QtCore.QObject):
    dataReceived = QtCore.pyqtSignal(dict)  # Sygnał wysyłający odebrane dane (słownik)

    async def run(self, uri):
        while True:
            try:
                print("Próba połączenia z WebSocket...")
                async with websockets.connect(uri) as ws:
                    print("Połączono z ESP32 przez WebSocket!")
                    while True:
                        message =  await ws.recv()
                        print(f"Odebrano wiadomość: {message}")
                        # Oczekujemy, że długość wiadomości wynosi dokładnie 28 bajtów
                        if isinstance(message, bytes) and len(message) == 28:
                            try:
                                # Rozpakowanie 7 floatów (little endian)
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
            except websockets.exceptions.ConnectionClosedError as e:
                print("Połączenie zamknięte, próbuję ponownie...", e)
                await asyncio.sleep(1)
            except Exception as e:
                print("Błąd połączenia WebSocket:", e)
                await asyncio.sleep(1)

    async def close_connection(self):
        # Można zaimplementować zamykanie połączenia, jeśli potrzebne
        pass


# Główne okno aplikacji
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monitor danych ESP32")
# Bufory danych
        self.time_data = []
        self.voltage1_data = []
        self.voltage2_data = []
        self.voltage3_data = []
        self.current1_data = []
        self.current2_data = []
        self.current3_data = []
        self.temp_data = []
        self.start_time = time.time()

        # Tworzymy wykresy dla napięć
        self.voltage1_plot = pg.PlotWidget(title="Voltage 1")
        self.voltage2_plot = pg.PlotWidget(title="Voltage 2")
        self.voltage3_plot = pg.PlotWidget(title="Voltage 3")
        # Tworzymy wykresy dla prądów
        self.current1_plot = pg.PlotWidget(title="Current 1")
        self.current2_plot = pg.PlotWidget(title="Current 2")
        self.current3_plot = pg.PlotWidget(title="Current 3")
        # Wykres dla temperatury
        self.temp_plot = pg.PlotWidget(title="Temperature")

        # Ustawienia wykresów - ciemne tło, jasne osie
        for plot in (self.voltage1_plot, self.voltage2_plot, self.voltage3_plot,
                     self.current1_plot, self.current2_plot, self.current3_plot,
                     self.temp_plot):
            plot.setBackground('#2b2b2b')
            plot.getAxis('left').setPen('w')
            plot.getAxis('bottom').setPen('w')
            plot.getAxis('left').setTextPen('w')
            plot.getAxis('bottom').setTextPen('w')

        # Krzywe dla wykresów
        self.voltage1_curve = self.voltage1_plot.plot(pen='r')
        self.voltage2_curve = self.voltage2_plot.plot(pen='r')
        self.voltage3_curve = self.voltage3_plot.plot(pen='r')

        self.current1_curve = self.current1_plot.plot(pen='y')
        self.current2_curve = self.current2_plot.plot(pen='y')
        self.current3_curve = self.current3_plot.plot(pen='y')

        self.temp_curve = self.temp_plot.plot(pen='c')

        # Grupa sterowania napięciem - przykładowa kontrolka do wysłania komendy SET_VOLTAGE
        self.voltageLineEdit = QtWidgets.QLineEdit()
        self.setVoltageButton = QtWidgets.QPushButton("Ustaw napięcie")

        controlGroup = QtWidgets.QGroupBox("Sterowanie")
        controlLayout = QtWidgets.QVBoxLayout()
        controlLayout.addWidget(QtWidgets.QLabel("Podaj napięcie:"))
        controlLayout.addWidget(self.voltageLineEdit)
        controlLayout.addWidget(self.setVoltageButton)
        controlGroup.setLayout(controlLayout)

        # Układ kolumnowy:
        # Lewa kolumna – wykresy napięć (voltage1, voltage2, voltage3) ułożone pionowo
        leftLayout = QtWidgets.QVBoxLayout()
        leftLayout.addWidget(self.voltage1_plot)
        leftLayout.addWidget(self.voltage2_plot)
        leftLayout.addWidget(self.voltage3_plot)

        # Środkowa kolumna – wykresy prądów (current1, current2, current3)
        centerLayout = QtWidgets.QVBoxLayout()
        centerLayout.addWidget(self.current1_plot)
        centerLayout.addWidget(self.current2_plot)
        centerLayout.addWidget(self.current3_plot)

        # Prawa kolumna – wykres temperatury i sterowanie napięciem
        rightLayout = QtWidgets.QVBoxLayout()
        rightLayout.addWidget(self.temp_plot)
        rightLayout.addWidget(controlGroup)
        rightLayout.addStretch()

        # Łączymy trzy kolumny
        mainLayout = QtWidgets.QHBoxLayout()
        mainLayout.addLayout(leftLayout, stretch=1)
        mainLayout.addLayout(centerLayout, stretch=1)
        mainLayout.addLayout(rightLayout, stretch=1)

        container = QtWidgets.QWidget()
        container.setLayout(mainLayout)
        self.setCentralWidget(container)

        # Ustaw globalny ciemny motyw
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                font-size: 14px;
            }
            QLineEdit, QPushButton {
                background-color: #3c3f41;
                border: 1px solid #5c5c5c;
                padding: 5px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4b4f51;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #5c5c5c;
                border-radius: 6px;
                margin-top: 10px;
                padding: 10px;
            }
        """)

        # Połączenie przycisku sterowania z akcją
        self.setVoltageButton.clicked.connect(self.sendVoltageCommand)

        # Tworzymy obiekt odbierający dane z WebSocket
        self.dataReceiver = DataReceiver()
        self.dataReceiver.dataReceived.connect(self.updateData)

        # Odroczenie uruchomienia połączenia WebSocket
        QtCore.QTimer.singleShot(0, self.start_websocket_connection)

    def start_websocket_connection(self):
        uri = "ws://192.168.18.229/ws"  # Zamień na właściwy adres Twojego ESP32
        print("Uruchamiam połączenie z WebSocket...")
        asyncio.ensure_future(self.dataReceiver.run(uri))

    def updateData(self, data):
        # Odczyt danych
        voltage1 = data.get("Voltage1", 0)
        voltage2 = data.get("Voltage2", 0)
        voltage3 = data.get("Voltage3", 0)
        current1 = data.get("Current1", 0)
        current2 = data.get("Current2", 0)
        current3 = data.get("Current3", 0)
        temp = data.get("Temperature", 0)

        # Aktualizacja etykiet (opcjonalnie, możesz dodać osobne etykiety)
        # Aktualizacja wykresów
        current_time = time.time() - self.start_time
        # Aktualizacja list czasowych
        self.time_data.append(current_time)
        # Aktualizacja list danych - osobno dla każdego kanału
        self.voltage1_data.append(voltage1)
        self.voltage2_data.append(voltage2)
        self.voltage3_data.append(voltage3)

        self.current1_data.append(current1)
        self.current2_data.append(current2)
        self.current3_data.append(current3)

        self.temp_data.append(temp)

        # Ograniczenie liczby punktów do ostatnich 100
        max_points = 100
        if len(self.time_data) > max_points:
            self.time_data = self.time_data[-max_points:]
            self.voltage1_data = self.voltage1_data[-max_points:]
            self.voltage2_data = self.voltage2_data[-max_points:]
            self.voltage3_data = self.voltage3_data[-max_points:]
            self.current1_data = self.current1_data[-max_points:]
            self.current2_data = self.current2_data[-max_points:]
            self.current3_data = self.current3_data[-max_points:]
            self.temp_data = self.temp_data[-max_points:]

        # Aktualizacja krzywych wykresów
        self.voltage1_curve.setData(self.time_data, self.voltage1_data)
        self.voltage2_curve.setData(self.time_data, self.voltage2_data)
        self.voltage3_curve.setData(self.time_data, self.voltage3_data)
        self.current1_curve.setData(self.time_data, self.current1_data)
        self.current2_curve.setData(self.time_data, self.current2_data)
        self.current3_curve.setData(self.time_data, self.current3_data)
        self.temp_curve.setData(self.time_data, self.temp_data)

    def sendVoltageCommand(self):
        voltage = self.voltageLineEdit.text()
        command = f"SET_VOLTAGE:{voltage}"
        # Logika wysłania komendy przez WebSocket do ESP32 (do zaimplementowania)
        print(f"Wysyłam komendę: {command}")


# Główna funkcja aplikacji, integrująca PyQt5 z asyncio przez qasync
async def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet(""" 
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
            font-size: 14px;
        }
        QLineEdit, QPushButton {
            background-color: #3c3f41;
            border: 1px solid #5c5c5c;
            padding: 5px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #4b4f51;
        }
    """)

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
