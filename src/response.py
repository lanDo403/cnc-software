# Формат протокола
import serial
import time
from typing import Generator, Optional

# Протокол

'''
SQN ответного пакета по идее должен быть равен SQN пакета команды
ADDR возможно также как и SQN, по идее передается из пакета команды, по дефолту равен 1
Нужна какая то логика обработки ACK_BAD_PARAM и может быть ACK_BAD_ADDR
'''

POLY = 0x31 # x^8 + x^5 + x^4 + 1
SYNC_1 = 0xAC # Синхрослово
SYNC_2 = 0x53 # Синхрослово
ADDR = 0x01 # В документе такой, мб другой будет на практике
ACK_OK = 0x01 # Команда принята и декодирована
ACK_BAD_ADDR = 0x02 # Неверный адрес
ACK_BAD_CRC = 0x03 # Ошибка в crc
ACK_BAD_PARAM = 0x04 # Ошибка в параметрах

# Разбиение на куски по 250 байт, ибо данных может быть больше, чем 250 байт, они же тогда будут отправляться не в одном пакете, а в нескольких
def ChunkBytes(data: bytes, chunkSize: int=250):
	for i in range(0, len(data), chunkSize):
		yield data[i:i + chunkSize]


# Вычисление crc
def Crc8(data: bytes) -> int:
	crc = 0
	for b in data:
		crc ^= b
		for _ in range(8):
			if crc & 0x80:
				crc = ((crc << 1) ^ POLY) & 0xFF
			else:
				crc = (crc << 1) & 0xFF
	return crc


# Преобразует список строк G-code в байтовый поток. Каждая строка заканчивается '\n'
def GcodeListToStr(gcodeLines: list[str]) -> bytes:
    lines = []
    for line in gcodeLines:
        lines.append(line.rstrip("\r\n") + "\n")
    return "".join(lines).encode("ascii")


# Формирование ответного пакета
def MakeResponse(sqn: int, data: bytes, addr: int=ADDR, ack: int=ACK_OK) -> bytes:
	# Проверка на длину данных
	if len(data) > 250:
		raise ValueError("\n<<<<DATA too long>>>>")

	# Формируем тело, содержащее в себе все поля SQN, ADDR, ACK, DATA
	body = bytes([
		sqn & 0xFF,
		addr & 0xFF,
		ack & 0xFF
		]) + data

	# Получаем длину тела, формируем пакет без синхрослов и crc, а затем вычисляем crc 
	length = len(body)
	packet_wo_crc = bytes([length]) + body
	crc = Crc8(packet_wo_crc)

	# Уже сформированный пакет со всеми полями (SYNC_1 | SYNC_2 | LEN | SQN | ADDR | ACK | DATA | CRC)
	#                                                                 <-----это и есть body----->
	packet = bytes([SYNC_1, SYNC_2]) + packet_wo_crc + bytes([crc])
	return packet


# Чтение ответного пакета и определение поля ACK
def ReadAckPacket(ser: serial.Serial, timeout: float = 0.05) -> Optional[int]:
	start = time.time()

	# Пока за 50мс не вышел, читаем первые 2 байта, если они равны нашим синхрословам, то выходим из while
	while time.time() - start < timeout:
		b = ser.read(1)
		if not b:
			continue
		if b[0] == SYNC_1 and ser.read(1) == bytes([SYNC_2]):
			break
	else: 
		return None

	# Получили поле LEN
	lenByte = ser.read(1)
	if not lenByte:
		return None

	#Читаем тело(SQN, ADDR, ACK, DATA) и crc
	length = lenByte[0]
	body = ser.read(length)
	crcRx = ser.read(1)

	if len(body) != length or not crcRx:
		return None

	# Если ошибка в CRC, возвращаем ACK_BAD_CRC
	if Crc8(lenByte + body) != crcRx[0]:
		return ACK_BAD_CRC

	# Возвращается поле ACK
	return body[2]


# Отправка уже готовой из ГУИ hex строки с G-code и со всеми заполненными полями
def SendHex(port: str, hexString: str, baudrate: int) -> bool:
	try:
		# Не знаю в каком конкретно будет формате hex строка(с пробелами или без), 
		# поэтому для корректности убираем лишние пробелы и переводы строк
		hexString = hexString.strip()

		# Если количество hex символов нечетное, то потенциально может быть ошибка
		# Ну и ошибка может быть, если в строке есть не hex символ, что вряд ли
		data = bytes.fromhex(hexString)

		# Открываем UART
		ser = serial.Serial(
			port=port,
			baudrate=baudrate,
			bytesize=8,
			parity='N',
			stopbits=1,
			timeout=0.01
		)

		# Отправляем как есть
		ser.write(data)
		ser.flush()
		time.sleep(0.01)

		ser.close()
		return True

	except Exception:
		try:
			ser.close()
		except Exception:
			pass
		return False


# Для инициализации отправки пакета можно вызывать эту функцию в ГУИ напрямую, передав параметры порта, пути до файла с g-code и baudrate
def SendGcode(port: str, gcodeLines: list[str], baudrate: int, chunkSize: int=250, retries: int=3) -> bool:#
	# Инициализация UART
	ser = serial.Serial(
		port = port, # Получить из ГУИ
		baudrate = baudrate, # Получить из ГУИ
		bytesize = 8,
		parity = 'N',
		stopbits = 1,
		timeout = 0.01
		)

	# Чтение файла с g-code
	gcodeBytes = GcodeListToStr(gcodeLines)

	# Отправляем пакеты и проверяем ответ, а именно, чему равно поле ACK
	sqn = 0
	for chunk in ChunkBytes(gcodeBytes, chunkSize):
		success = False
		for _ in range(retries):
			packet = MakeResponse(sqn=sqn, data=chunk)
			ser.write(packet)
			ser.flush()

			ack = ReadAckPacket(ser)

			if ack == ACK_OK:
				success = True
				break

			if ack == ACK_BAD_CRC or ack is None:
				time.sleep(0.02)
				continue

			elif ack in (ACK_BAD_ADDR, ACK_BAD_PARAM):
				ser.close()
				return False

		if not success:
			ser.close()
			return False

		# При каждой неудачной попытке увеличивается SQN
		sqn = (sqn + 1) & 0xFF
		time.sleep(0.005)

	ser.close()
	return True
