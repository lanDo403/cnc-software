from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QGraphicsScene
from PyQt5.QtSerialPort import QSerialPortInfo
from PyQt5 import uic
from PyQt5.QtCore import Qt, QObject, QEvent
from PyQt5.QtGui import QTextCursor, QImage, QPixmap
from PIL import Image, ImageDraw
import sys
#import serial.tools.list_ports as get_list

def SendGcode(port: str, gcodeLines: list[str], baudrate: int, chunkSize: int=250, retries: int=3) -> bool:
    print(f"Sending G-codes: port={port}, baudrate={baudrate}; G-codes=\n{gcodeLines}")
    return True


def confirm(parent=None, text="Точно?") -> bool:
    return QMessageBox.question(parent, "Подтверждение", text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes


class GraphicsViewClickFilter(QObject):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            pos = event.pos()
            self.callback(pos.x(), pos.y())
        return False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = uic.loadUi('mainwindow.ui', self)
        self.mainTabs.setCurrentIndex(1)
        self.GetCOMPorts()
        self.filter = GraphicsViewClickFilter(self.on_field_view_clicked)
        self.field_view.viewport().installEventFilter(self.filter)
        self.scene = QGraphicsScene()
        self.field_view.setScene(self.scene)
        self.field_view.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

        self.btn_colebrate.clicked.connect(self.clicked_btn_calibrate)
        self.btn_clear_img.clicked.connect(self.clicked_btn_clear_img)
        self.btn_g00.clicked.connect(self.clicked_btn_g00)
        self.btn_g01.clicked.connect(self.clicked_btn_g01)
        # TBD

        self.mode: str = 'G00'  # G00, G01, G02, G03, G90, G91
        self.current_x: int = 0
        self.current_y: int = 0
        self.goto_x: int = None
        self.goto_y: int = None
        self.draw_commands: list = []

    def draw_img(self):
        img = Image.new("RGB", (330, 228), "white")
        draw = ImageDraw.Draw(img)
        # all commands
        for command in self.draw_commands:
            mode, x1, y1, x2, y2 = command
            if mode == 'G01':
                draw.line((x1, y1, x2, y2), fill="black", width=2)
        # current position
        if self.current_x is not None and self.current_y is not None:
            r = 3  # радиус текущей позиции
            draw.ellipse((self.current_x - r, self.current_y - r, self.current_x + r, self.current_y + r), fill="red")
        img.save(".field_img.png")
        pixmap = QPixmap(".field_img.png")
        self.scene.addPixmap(pixmap)

        # data = img.tobytes("raw", "RGB")
        # qimage = QImage(data, img.width, img.height, QImage.Format_RGB888)
        # pixmap = QPixmap.fromImage(qimage)
        # self.scene.addPixmap(pixmap)


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

    def on_field_view_clicked(self, x, y):
        print(f"Clicked at x={x}, y={y}")
        if not confirm(self, f"Вы уверены, что хотите выполнить {self.mode} на координаты x={x}, y={y}?"):
            return
        if self.mode != 'G00':
            self.draw_commands.append((self.mode, self.current_x, self.current_y, x, y))
        self.current_x = x
        self.current_y = y
        self.draw_img()
        SendGcode(self.portsComboBox.currentText(), f"{self.mode} X{x} Y{y}", int(self.baudRateLineEdit.text()))

    def clicked_btn_calibrate(self):
        if not confirm(self, "Вы уверены, что хотите выполнить калибровку?"):
            return
        self.current_x: int = 0
        self.current_y: int = 0
        self.draw_img()
        SendGcode(self.portsComboBox.currentText(), "G00 X0 Y0", int(self.baudRateLineEdit.text()))

    def clicked_btn_clear_img(self):
        if not confirm(self, "Вы уверены, что хотите очистить картинку?"):
            return
        self.draw_commands = []
        print("Image cleared")
        self.draw_img()

    def clicked_btn_g00(self):
        self.mode = 'G00'
        self.mode_label.setText(f'Режим: {self.mode}')

    def clicked_btn_g01(self):
        self.mode = 'G01'
        self.mode_label.setText(f'Режим: {self.mode}')

    def clicked_btn_g02(self):
        pass

    def clicked_btn_g03(self):
        pass

    def clicked_btn_g90(self):
        pass

    def clicked_btn_g91(self):
        pass

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        current_encoding = 'cp1251'
    else:
        current_encoding = 'utf8'

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
