from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QGraphicsScene, QFileDialog
from PyQt5.QtSerialPort import QSerialPortInfo
from PyQt5 import uic
from PyQt5.QtCore import Qt, QObject, QEvent
from PyQt5.QtGui import QTextCursor, QPixmap
from PIL import Image, ImageDraw
import os
import sys
import copy
import math
#import serial.tools.list_ports as get_list


from response import *
# # dummy implementation of SendGcode and SendHex for testing GUI
# def SendGcode(port: str, gcodeLines: list[str], baudrate: int, chunkSize: int=250, retries: int=3) -> bool:
#     print(f"Sending G-codes: port={port}, baudrate={baudrate}; G-codes={gcodeLines}")
#     return True


# def SendHex(port: str, hexString: str, baudrate: int) -> bool:
#     print(f"Sending HEX packet: port={port}, baudrate={baudrate}; packet={hexString}")
#     return True


def nearest_anchor(x: int, y: int, anchors: set[tuple[int, int]]) -> tuple[int, int]:
    if not anchors:
        raise ValueError("Множество anchors не должно быть пустым")
    return min(anchors, key=lambda a: math.hypot(a[0] - x, a[1] - y))


def get_gcode(mode: str, paint: bool, x: int, y: int, ccw: bool=False, radius:int=0) -> str:
    if not paint:
        return f'G00 X{x} Y{y}'
    if mode in ('hrz', 'vrt', 'slp'):
        return f'G01 X{x} Y{y}'
    if mode == 'arc':
        if ccw:
            return f'G03 X{x} Y{y} R{radius}'
        else:
            return f'G02 X{x} Y{y} R{radius}'


def get_gcodes_htc(img, mode: str, paint: bool, x: int, y: int, angle: int, distance: int, x_cur: int, y_cur: int) -> tuple[list[str], int, int]:
    if not paint:
        return [list(), x_cur, y_cur]
    ret = []
    x_last, y_last = x_cur, y_cur
    for x1, y1, x2, y2 in get_hatch_lines(img, x, y, angle, distance):
        ret.append(f'G00 X{x1} Y{y1}')
        ret.append(f'G01 X{x2} Y{y2}')
        x_last, y_last = x2, y2
    return (ret, x_last, y_last)


def get_hatch_lines(img, x, y, angle, distance):

    def _extend_line(x1, y1, x2, y2, pixels):
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length == 0:
            return x1, y1, x2, y2
        ux = dx / length
        uy = dy / length
        return (int(round(x1 - ux * pixels)), int(round(y1 - uy * pixels)), int(round(x2 + ux * pixels)), int(round(y2 + uy * pixels)))

    img = copy.deepcopy(img.convert("L"))
    w, h = img.size

    inv = Image.eval(img, lambda p: 255 if p > 128 else 0)
    ImageDraw.floodfill(inv, (x, y), 128)

    region = inv.point(lambda p: 255 if p == 128 else 0)
    mask = region.load()

    angle_rad = math.radians(angle)
    dx, dy = math.cos(angle_rad), math.sin(angle_rad)
    nx, ny = -dy, dx
    diag = int(math.hypot(w, h)) + 2
    cx, cy = w / 2, h / 2

    segments = []
    offset = -diag
    while offset < diag:
        x1 = cx + nx * offset - dx * diag
        y1 = cy + ny * offset - dy * diag
        x2 = cx + nx * offset + dx * diag
        y2 = cy + ny * offset + dy * diag

        steps = int(math.hypot(x2 - x1, y2 - y1))
        inside = False
        sx = sy = None
        for i in range(steps + 1):
            t = i / steps
            xi = int(x1 + (x2 - x1) * t)
            yi = int(y1 + (y2 - y1) * t)
            if 0 <= xi < w and 0 <= yi < h and mask[xi, yi]:
                if not inside:
                    sx, sy = xi, yi
                    inside = True
            else:
                if inside:
                    segments.append((sx, sy, xi, yi))
                    inside = False
        if inside:
            segments.append(_extend_line(sx, sy, xi, yi, 2))
        offset += distance

    return segments


def draw_gcode_arc(parent, draw, x1: int, y1: int, x2: int, y2: int, r: int, ccw: bool, steps: int=330) -> bool:

    def _get_arc_angle(a1: float, a2: float, ccw: bool):
        if ccw:
            if a2 < a1:
                a2 += 2 * math.pi
            return a2 - a1
        else:
            if a2 > a1:
                a2 -= 2 * math.pi
            return a1 - a2

    dx = x2 - x1
    dy = y2 - y1
    distance = math.hypot(dx, dy)

    if distance == 0:
        return True

    R = abs(r)
    if distance > 2 * R:
        alert(parent, "Дуга невозможна: расстояние больше диаметра!")
        return False

    mx = (x1 + x2) / 2
    my = (y1 + y2) / 2
    h = math.sqrt(R * R - (distance / 2) ** 2)
    nx = -dy / distance
    ny = dx / distance
    centers = [
        (mx + nx * h, my + ny * h),
        (mx - nx * h, my - ny * h),
    ]

    candidates = []
    for cx, cy in centers:
        a1 = math.atan2(y1 - cy, x1 - cx)
        a2 = math.atan2(y2 - cy, x2 - cx)
        sweep = _get_arc_angle(a1, a2, ccw)
        candidates.append((sweep, cx, cy, a1, a2))

    if r > 0:
        sweep, cx, cy, a1, a2 = min(candidates, key=lambda c: c[0])
    else:
        sweep, cx, cy, a1, a2 = max(candidates, key=lambda c: c[0])

    prev = (x1, y1)
    for i in range(1, steps + 1):
        t = i / steps
        angle = a1 + (sweep * t if ccw else -sweep * t)
        x = cx + R * math.cos(angle)
        y = cy + R * math.sin(angle)
        draw.line([prev, (x, y)], fill="black", width=3)
        prev = (x, y)

    return True


def confirm(parent=None, text="Точно?") -> bool:
    if parent.btn_radio_no_confirm.isChecked():
        return True
    return QMessageBox.question(parent, "Подтверждение", text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes


def alert(parent=None, text="Ошибка!") -> None:
    return QMessageBox.information(parent, "Предупреждение", text, QMessageBox.Ok)


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
        self.mainTabs.setCurrentIndex(0)
        self.GetCOMPorts()
        self.filter = GraphicsViewClickFilter(self.on_paint_view_clicked)
        self.paint_view.viewport().installEventFilter(self.filter)
        self.scene = QGraphicsScene()
        self.paint_view.setScene(self.scene)
        self.paint_view.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        self.mode_paint_label.setText(f'Горизонтальное перемещение')
        self.file_gcodes: str = ''

        self.btn_refresh.clicked.connect(self.GetCOMPorts)
        self.btn_dump_codes.clicked.connect(self.clicked_btn_dump_codes)
        self.btn_paint_calibrate.clicked.connect(self.clicked_btn_calibrate)
        self.btn_paint_clear_img.clicked.connect(self.clicked_btn_clear_img)
        self.btn_paint_vertical.clicked.connect(self.clicked_btn_mode_vrt)
        self.btn_paint_horizontal.clicked.connect(self.clicked_btn_mode_hrz)
        self.btn_paint_sloped.clicked.connect(self.clicked_btn_mode_slp)
        self.btn_paint_hatch.clicked.connect(self.clicked_btn_mode_htc)
        self.btn_paint_arc.clicked.connect(self.clicked_btn_mode_arc)
        self.btn_pro_gcode_send.clicked.connect(self.clicked_btn_send_gcode)
        self.btn_pro_hex_send.clicked.connect(self.clicked_btn_send_hex)
        self.btn_select_file.clicked.connect(self.clicked_btn_select_file)
        self.btn_send_file.clicked.connect(self.clicked_btn_send_file)
        self.btn_paint_add_anchor_point.clicked.connect(self.clicked_btn_paint_add_anchor_point)

        self.mode: str = 'hrz'  # hrz, vrt, slp, htc, arc
        self.drawing: bool = self.btn_radio_paint.isChecked()
        self.current_x: int = 0
        self.current_y: int = 0
        self.goto_x: int = None
        self.goto_y: int = None
        self.draw_commands: list = []
        self.g_codes: list = []
        self.anchors: set = {(0, 0),}

        self.draw_img()

    def draw_img(self, pre=None) -> bool:
        self.img = Image.new("RGB", (330, 228), "white")
        draw = ImageDraw.Draw(self.img)
        local_commands = copy.deepcopy(self.draw_commands)
        if pre is not None:
            local_commands.append(pre)
        # all commands
        while len(local_commands) > 0:
            command = local_commands.pop(0)
            if len(local_commands) != 0 or pre is None:
                color = 'black'
            else:
                if self.btn_radio_paint.isChecked():
                    color = 'green'
                else:
                    color = 'orange'
            if command[0] in ('hrz', 'vrt', 'slp'):
                x1, y1, x2, y2, r, ccw, angle, distance = command[1:]
                draw.line((x1, y1, x2, y2), fill=color, width=3)
            if command[0] == 'arc':
                x1, y1, x2, y2, r, ccw, angle, distance = command[1:]
                if not draw_gcode_arc(self, draw, x1, y1, x2, y2, r, ccw):
                    return False
            if command[0] == 'htc':
                x1, y1, x2, y2, r, ccw, angle, distance = command[1:]
                hatch_lines = get_hatch_lines(self.img, x2, y2, angle, distance)
                for line in hatch_lines:
                    xi1, yi1, xi2, yi2 = line
                    draw.line((xi1, yi1, xi2, yi2), fill=color, width=3)
            pass
        # current position
        if self.current_x is not None and self.current_y is not None:
            r = 3
            draw.ellipse((self.current_x - r, self.current_y - r, self.current_x + r, self.current_y + r), fill="red")
        self.img.save(f".field_img.png")
        pixmap = QPixmap(".field_img.png")
        self.scene.addPixmap(pixmap)
        return True

    def GetCOMPorts(self):
        self.getPorts = QSerialPortInfo()
        ports = list(self.getPorts.availablePorts())
        self.portsComboBox.clear()
        if ports:
            self.Append('<<<< ПОРТЫ НАЙДЕНЫ >>>>\n')
            self.Append(' Список портов: \n')
            for port in ports:
                self.portsComboBox.addItem(port.portName())
                self.Append(port.portName())
            self.Append('\n<<<< ВЫПАДАЮЩИЙ СПИСОК ЗАПОЛНЕН ВСЕМИ ДОСТУПНЫМИ ПОРТАМИ >>>>\n')
        else:
            self.Append('<<<< ПОРТЫ НЕ ОБНАРУЖЕНЫ >>>>\n')

    def Append(self, text):
        cursor = self.consoleEdit.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(text)
        self.consoleEdit.moveCursor(QTextCursor.End)

    def on_paint_view_clicked(self, x, y):
        # processing & snapping
        goto_x = x
        goto_y = y
        if self.mode == 'hrz':
            goto_y = self.current_y
            if self.btn_radio_snapping.isChecked():
                nearest_x, nearest_y = nearest_anchor(x, y, self.anchors)
                goto_x = nearest_x
        if self.mode == 'vrt':
            goto_x = self.current_x
            if self.btn_radio_snapping.isChecked():
                nearest_x, nearest_y = nearest_anchor(x, y, self.anchors)
                goto_y = nearest_y
        if self.mode in ('slp', 'arc') and self.btn_radio_snapping.isChecked():
            goto_x, goto_y = nearest_anchor(goto_x, goto_y, self.anchors)
        self.Append(f"<<<< Конечная точка: x={goto_x}, y={goto_y} >>>>\n")
        # pre-paint and confirm
        if not self.draw_img(pre=(self.mode, self.current_x, self.current_y, goto_x, goto_y, int(self.spinbox_paint_radius.text()), self.btn_radio_paint_ccw.isChecked(), int(self.spinbox_paint_hatch_angle.text()), int(self.spinbox_paint_hatch_distance.text()))):
            return
        if not confirm(self, f"Вы уверены, что хотите выполнить это действие?"):
            self.draw_img()
            return
        # sending
        if self.mode == 'htc':
            self.draw_img()
            g_codes, goto_htc_x, goto_htc_y = get_gcodes_htc(self.img, self.mode, self.btn_radio_paint.isChecked(), goto_x, goto_y, int(self.spinbox_paint_hatch_angle.text()), int(self.spinbox_paint_hatch_distance.text()), self.current_x, self.current_y)
            if not SendGcode(self.portsComboBox.currentText(), g_codes, int(self.baudRateLineEdit.text())):
                alert(self, "Ошибка отправки! Проверьте подключение!")
                self.draw_img()
                return
        else:
            if not SendGcode(self.portsComboBox.currentText(), [get_gcode(self.mode, self.btn_radio_paint.isChecked(), goto_x, goto_y, self.btn_radio_paint_ccw.isChecked(), int(self.spinbox_paint_radius.text())),], int(self.baudRateLineEdit.text())):
                alert(self, "Ошибка отправки! Проверьте подключение!")
                self.draw_img()
                return
        # draw if sent succesfully
        if self.mode == 'htc':
            self.g_codes.extend(g_codes)
        else:
            self.g_codes.append(get_gcode(self.mode, self.btn_radio_paint.isChecked(), goto_x, goto_y, self.btn_radio_paint_ccw.isChecked(), int(self.spinbox_paint_radius.text())))
        if self.btn_radio_paint.isChecked():
            self.draw_commands.append((self.mode, self.current_x, self.current_y, goto_x, goto_y, int(self.spinbox_paint_radius.text()), self.btn_radio_paint_ccw.isChecked(), int(self.spinbox_paint_hatch_angle.text()), int(self.spinbox_paint_hatch_distance.text())))
            # add anchor
            self.anchors.add((self.current_x, self.current_y))
            if self.mode != 'htc':
                self.anchors.add((goto_x, goto_y))
        if self.mode == 'htc':
            if self.btn_radio_paint.isChecked():
                goto_x = goto_htc_x
                goto_y = goto_htc_y
            else:
                goto_x = self.current_x
                goto_y = self.current_y
        self.current_x = goto_x
        self.current_y = goto_y
        self.draw_img()

    def clicked_btn_dump_codes(self):
        if os.path.exists('g_codes_dump.cnc'):
            if not confirm(self, "Файл с дампом сущесвует. Вы уверены, что хотите его перезаписать?"):
                return
        with open('g_codes_dump.cnc', 'w') as file:
            file.write('\n'.join(self.g_codes))
        self.Append('<<<< G-коды сдамплены в файл "g_codes_dump.cnc" >>>>\n')
        alert(self, 'G-коды сдаплены в файл "g_codes_dump.cnc" успешно!')

    def clicked_btn_calibrate(self):
        if not confirm(self, "Вы уверены, что хотите выполнить калибровку?"):
            return
        self.current_x: int = 0
        self.current_y: int = 0
        if not SendGcode(self.portsComboBox.currentText(), ["G00 X0 Y0",], int(self.baudRateLineEdit.text())):
            alert(self, "Ошибка отправки! Проверьте подключение!")
            return
        self.Append("<<<< ЧПУ отклабирован >>>>\n")
        self.g_codes.append('G00 X0 Y0')
        self.draw_img()

    def clicked_btn_clear_img(self):
        if not confirm(self, "Вы уверены, что хотите очистить картинку?"):
            return
        self.draw_commands = []
        self.g_codes = []
        print("Image cleared")
        self.Append("<<<< Изображение очищено >>>>\n")
        self.draw_img()

    def clicked_btn_mode_hrz(self):
        self.mode = 'hrz'
        self.mode_paint_label.setText(f'Горизонтальное перемещение')

    def clicked_btn_mode_vrt(self):
        self.mode = 'vrt'
        self.mode_paint_label.setText(f'Вертикальное перемещение')

    def clicked_btn_mode_slp(self):
        self.mode = 'slp'
        self.mode_paint_label.setText(f'Произвольное перемещение')

    def clicked_btn_mode_htc(self):
        self.mode = 'htc'
        self.mode_paint_label.setText(f'Штриховка')

    def clicked_btn_mode_arc(self):
        self.mode = 'arc'
        self.mode_paint_label.setText(f'Перемещение по дуге')

    def clicked_btn_paint_add_anchor_point(self):
        alert(self, f"Добавлена якорная точка на координатах x={self.current_x} y={self.current_y}!")
        self.anchors.add((self.current_x, self.current_y))

    def clicked_btn_select_file(self):
        self.file_gcodes, _ = QFileDialog.getOpenFileName(self, "Выберите файл", "", "Все файлы (*.*)")
        self.label_filename.setText(f"Выбранный файл: {self.file_gcodes}")

    def clicked_btn_send_file(self):
        if not confirm(self, f"Вы уверены, что хотите отправить файл {self.file_gcodes}?"):
            return
        self.file_gcodes_content = []
        with open(self.file_gcodes, 'r') as file:
            file_gcodes_content = file.readlines()
            for line in file_gcodes_content:
                line: str = line.replace('\n', '')
                if line != '':
                    self.file_gcodes_content.append(line)
        if not SendGcode(self.portsComboBox.currentText(), self.file_gcodes_content, int(self.baudRateLineEdit.text())):
            alert(self, "Ошибка отправки! Проверьте подключение!")
            return
        self.Append(f'<<<< Успешно отправлен файл с G-кодами: {self.file_gcodes} >>>>\n')
        alert(self, "Отправлено успешно!")

    def clicked_btn_send_gcode(self):
        if not confirm(self, "Вы уверены, что хотите отправить этот G-код?"):
            return
        if not SendGcode(self.portsComboBox.currentText(), [self.lineEdit_pro_gcode.text(),], int(self.baudRateLineEdit.text())):
            alert(self, "Ошибка отправки! Проверьте подключение!")
            return
        self.Append(f'<<<< Успешно отправлен G-код: {self.lineEdit_pro_gcode.text()} >>>>\n')
        alert(self, "Отправлено успешно!")

    def clicked_btn_send_hex(self):
        if not confirm(self, "Вы уверены, что хотите отправить этот HEX пакет?"):
            return
        if not SendHex(self.portsComboBox.currentText(), self.lineEdit_pro_hex.text(), int(self.baudRateLineEdit.text())):
            alert(self, "Ошибка отправки! Проверьте подключение!")
            return
        self.Append(f'<<<< Успешно отправлен пакет: {self.lineEdit_pro_hex.text()} >>>>\n')
        alert(self, "Отправлено успешно!")


if __name__ == "__main__":
    if sys.platform.startswith('win'):
        current_encoding = 'cp1251'
    else:
        current_encoding = 'utf8'

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
