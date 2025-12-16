from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtSerialPort import QSerialPortInfo
from PyQt5 import uic
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor
import sys
from dataclasses import dataclass
#import serial.tools.list_ports as get_list


@dataclass
class GCodePayload:
    opcode: int  # one of: 0, 1, 2, 3, 90, 91
    x: int
    y: int


def process_gcode(payload: GCodePayload) -> None:
    print(f"GCode aqcquired: opcode={payload.code}, x={payload.x}, y={payload.y}")
    # dummy placeholder
    # Ivan, implement your logic here
    pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = uic.loadUi('mainwindow.ui', self)
        self.mainTabs.setCurrentIndex(1)
        self.GetCOMPorts()

    def GetCOMPorts(self):
        self.getPorts = QSerialPortInfo()
        ports = list(self.getPorts.availablePorts())
        if ports:
            self.Append('<<<<ПОРТЫ НАЙДЕНЫ>>>>\n')
            self.Append('Список портов:\n')
            for port in ports:
                self.portsComboBox.addItem(port.portName())
                self.Append(port.portName())
            self.Append('\n<<<<ВЫПАДАЮЩИЙ СПИСОК ЗАПОЛНЕН ВСЕМИ ДОСТУПНЫМИ ПОРТАМИ>>>>\n')
        else:
            self.Append('<<<<ПОРТЫ НЕ ОБНАРУЖЕНЫ>>>>\n')

    def Append(self, text):
        cursor = self.consoleEdit.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(text)
        self.consoleEdit.moveCursor(QTextCursor.End)

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        current_encoding = 'cp1251'
    else:
        current_encoding = 'utf8'

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
