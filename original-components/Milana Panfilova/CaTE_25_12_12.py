import serial
import serial.tools.list_ports
import bitstring
import crcmod.predefined
#from time import sleep
import argparse
from datetime import datetime
import csv

########################################################################################
#	Control and Testing Equipment for CNC (interaction tester)
########################################################################################

# Класс мастера для отправки и приёма пакетов
class C_COM_P_MASTER:
	def __init__(self, port, baudrate, bytesize, stopbits, timeout, crc):
		self.port		 = port
		self.baudrate	 = baudrate
		self.bytesize	 = bytesize
		self.stopbits	 = stopbits
		self.timeout	 = timeout
		self.crc_func	 = crc		# тип контрольной суммы CRC
		self.crc_error	 = False	# ошибка CRC

		self.LEN_w	 = 0	# 4...253
		self.CMD_w	 = 0	# LEN-3
		self.PARAM	 = 0	# G-code
		self.SYNC1	 = 0xAC	# синхрослово 1
		self.SYNC2	 = 0x53	# синхрослово 2
		self.ADDR_w	 = 0x01	# адрес приёмника
		self.SQN_w	 = 0x00	# счетчик кадров по модулю 255

		self.ADDR_r	 = 0	# адрес со стороны worker ноды
		self.ACK_r	 = 0	# ответ со стороны worker ноды
		self.DATA_r	 = 0	# метаданные со стороны worker ноды
		self.CRC_r	 = 0	# CRC со стороны worker ноды

		self.synq_m	 = [ bitstring.BitArray(uint=self.SYNC1, length=8), bitstring.BitArray(uint=self.SYNC2, length=8) ]
		self.log_m	 = [ ['id', 'SQN', 'metadata'] ]
		self.cnt	 = 1

		try:
			self.ser = serial.Serial(
									#port	 = self.port, # Нужно раскоментировать. У меня на компьютере нет COM-порта
									baudrate = self.baudrate,
									bytesize = self.bytesize,
									parity	 = 'N',	# по условию
									stopbits = self.stopbits,
									timeout	 = self.timeout
									)
			print(f"COM-порт = {self.port} настроен и открыт")
		except Exception as e:
			print(f"Error: Не удалось открыть COM-порт = {self.port}; {e}")



#	Формируем пакет, отправляем его
	def send_packet(self, LEN, CMD, PARAM):
		if LEN < 4 or LEN > 253:
			print("Error: LEN должен быть в диапазоне 4...253")
			return None

		self.LEN_w	 = LEN
		self.CMD_w	 = CMD
		self.PARAM	 = PARAM

		packet_write_wo_crc = b''.join( [ (bitstring.BitArray(uint=group, length=8).tobytes()) for group in \
			( self.SYNC1, self.SYNC2, self.LEN_w, self.SQN_w, self.ADDR_w, self.CMD_w, ( self.PARAM if self.crc_error else self.PARAM.next_data() ) ) ] ) #; print(f'packet_write_wo_crc = {packet_write_wo_crc}')
		self.crc_error = False

		crc_v = bitstring.BitArray( uint=self.crc_func(packet_write_wo_crc[2:]), length=8 ).tobytes() #; print(packet_write_wo_crc[2:])
		packet_write = b''.join( [ packet_write_wo_crc, crc_v ] ) #print(f'packet_w_crc = {packet_write}')

		#self.ser.write(packet_write) # Нужно раскоментировать. У меня на компьютере нет COM-порта
		print(f"Отправлен пакет при SQN =	{self.SQN_w}: {bitstring.BitArray(packet_write).hex}")

		self.SQN_w = (self.SQN_w + 1) % 255 # по условию
		return None



# ожидаем ответ и записываем данные в csv файл
	def get_packet(self):
		if self.ser.is_open:
			try:
				while self.ser.in_waiting > 0: # если есть данные в буфере # Читаем до тех пор, пока не встретим синхрослово
					unified_packet_read_synq_1 = bitstring.BitArray(bytes=self.ser.read(1))
					if unified_packet_read_synq_1 != self.synq_m[0]: # проверка 1 синхрослова
						continue
					unified_packet_read_synq_2 = bitstring.BitArray(bytes=self.ser.read(1))
					if unified_packet_read_synq_2 != self.synq_m[1]: # проверка 2 синхрослова
						continue
					unified_packet_read_len = bitstring.BitArray(bytes=self.ser.read(1)) # чтение LEN
					if not unified_packet_read_len: # проверка LEN на пустоту
						continue
					self.LEN_r = unified_packet_read_len.hex # перевод LEN в hex для удобства
					if self.LEN_r < 4 or self.LEN_r > 253:
						print("Error: LEN должен быть в диапазоне 4...253")
						return None
					else: # если мы прошли стартовые проверки, то проводим еще больше проверок, которые уже более осязаемы
						unified_packet_read = bitstring.BitArray(bytes=self.ser.read(self.LEN_r)) # читаем основной пласт данных, включающий ADDR, ACK, DATA, CRC
						if not unified_packet_read: # Возможно нужна проверка на пустоту с 'or len(unified_packet_read) // self.bytesize < self.LEN_r '
							continue
						if not hasattr(self.get_packet.__func__, 'SQN_r_old'):	# Проверка, что есть атрибут с заданным именем
							self.METH_PR_TRANSACTION.__func__.SQN_r_old = unified_packet_read[:self.bytesize].hex
						else:
							self.SQN_r_new = unified_packet_read[:self.bytesize].hex
							if self.SQN_r_new != ( self.METH_PR_TRANSACTION.__func__.SQN_r_old + 1 ) % 255: # по условию
								print(f"Error: SQN не верный: SQN_r_old = {self.METH_PR_TRANSACTION.__func__.SQN_r_old} \
								а SQN_r_new = {self.SQN_r_new}")
								return None
							self.METH_PR_TRANSACTION.__func__.SQN_r_old = self.SQN_r_new # Возможно присвоение лучше сделать в самом конце

						fields =	[
									('ADDR_r',	self.bytesize),
									('ACK_r',	self.bytesize),
									('DATA_r',	self.bytesize*(self.LEN_r-3)), # Надо проверить
									('CRC_r',	self.bytesize),
									]

						offset = 0
						for name, size in fields:
							segment = unified_packet_read[offset : offset + size]
							setattr(self, name, segment)
							offset += size

						crc_v = self.crc_func( unified_packet_read_len + unified_packet_read[:-self.bytesize] )
						if crc_v != self.CRC_r: # проверка CRC
							print(f"Error: CRC не верный: CRC_r = {self.CRC_r} а crc_v = {crc_v}")
							return None

						match ( ACK ): # проверка ACK
							case bitstring.BitArray(uint=0, length=8):
								print(f'ACK = {ACK}: команда принята и декодирована')
							case bitstring.BitArray(uint=1, length=8):
								print(f'ACK = {ACK}: не верный адрес устройства')
								return None
							case bitstring.BitArray(uint=2, length=8):
								print(f'ACK = {ACK}: ошибка CRC')
								self.crc_error = True
								return None
							case bitstring.BitArray(uint=3, length=8):
								print(f'ACK = {ACK}: недопустимый параметр команды')
								return None
							case _:
								return None

						#				   [ 'id',			'SQN',				 'metadata']
						self.log_m.append( [ f'{self.cnt}', f'{self.SQN_r_new}', f'{self.DATA_r}'] )
						self.cnt += 1

					packet_read = b''.join( [ unified_packet_read_synq_1, unified_packet_read_synq_2, unified_packet_read ] ) #print(f'packet_read = {packet_read}')
					print(f"Получен пакет при SQN = {self.SQN_r_new}:	{packet_read}")

			except serial.SerialException as se:
				print("Error:", str(se))
		else:
			print(f"COM-порт = {self.port} не открыт")
		return None



	def write_csv(self):
		# .csv логи
		try:
			date = datetime.now().strftime("test_%Y_%m_%d_%H_%M_%S")
			filename = f"{date}.csv"
			with open(filename, "w", encoding="utf-8") as wf:
				writer = csv.writer(wf)
				for row in self.log_m:
					writer.writerow(row)
				print(f"Метаданные записаны в файл {filename} ")
		except Exception as e:
			print("An error occurred:", str(e))



	def close(self):
		try:
			self.ser.close()
			print(f"COM-порт = {self.port} закрыт")
		except Exception as e:
			print(f"Error: Не удалось закрыть COM-порт = {self.port}; {e}")



# Класс для чтения G-code и их последующей отправки 
class C_DATA_ITERATOR:
	def __init__(self, file_name, bytesize):
		try:
			with open(file_name, "r", encoding="utf-8") as inf:
				file_data = inf.read().splitlines() #; print(len(file_data))
			if len(file_data) == 0:
				raise ValueError("Недопустимая длина файла, минимум = 1")
			else:
				self.bitarray = [ (bitstring.BitArray(letter.encode()).int) for letter in ''.join(line for line in file_data) ] # bitstring.BitArray( ''.join(line for line in file_data).encode() )
				self.it = iter(self.bitarray) #; print(self.bitarray)
		except ValueError as ve:
			print("Error:", str(ve))
		except Exception as e:
			print("An error occurred:", str(e))

	def next_data(self):
		try:
			return next(self.it)
		except StopIteration as si:
			print("Warning:", str(si))
			return None 



# Вывод COM-портов
def f_show_com_ports():
	try:
		ports = serial.tools.list_ports.comports()
		port = next((p.device for p in ports), None)
		if port is None:
			raise ValueError("Нет доступных COM-портов")

		print("Доступные COM-порты:")
		for i, port in enumerate(ports):
			print(f"{i} = {port.device}")
		return ports

	except ValueError as ve:
		print("Error:", str(ve))
	except Exception as e:
		print("An error occurred:", str(e))



# Получение полей из командной строки
def f_get_args():
#	основные настройки передачи
	parser = argparse.ArgumentParser(
									prog = "former_rs_232.py",
									description = "RS-232 packet generator and receiver",
									epilog = "CNC IVT-42 P.M.A"
									)
	parser.add_argument(	'-wc',	'--whatcomport',	action = 'store_true',
							help = f"Показать список доступных COM-портов" )
	parser.add_argument(	'-cn',	'--comportname',	type = str,	default = "COM1",
							help = f"Имя COM-порта. По умолчанию = COM1")
	parser.add_argument(	'-br',	'--baudrate',	type = int,	default = 9600,
							help = f"Частота COM-порта. По умолчанию = 9600")
	parser.add_argument(	'-bs',	'--bytesize',	type = int,	default = 8,
							help = f"Кол-во информационных бит COM-порта. По умолчанию = 8 (от 0 до 7 \
							или от 1 до 8 включительно)")
	parser.add_argument(	'-sb',	'--stopbits',	type = int,	default = 1,
							help = f"Кол-во стоповых бит COM-порта. По умолчанию = 1")
	parser.add_argument(	'-to',	'--timeout',	type = int,	default = 5,
							help = f"Время ожидания ответа COM-порта в секундах. После истечения этого \
							времени связь будет разорвана. По умолчанию = 5")
	parser.add_argument(	'-crc',	'--controlsum',	type = int,	default = 8,
							help = f"Разрядность CRC. По умолчанию = 8")
	parser.add_argument(	'-f',	'--filename',	type = str,	default = 'tst.txt',
							help = f"Файл с данными для передачи. Содержит только PARAM = G-code. \
							По умолчанию = tst.txt")
	return parser.parse_args()


# 1. надо сделать логирование телеметрии в .csv file
# 2. надо дописать прием данных
if __name__ == "__main__":
	args = f_get_args()

	if args.whatcomport:
		f_show_com_ports()
	else:
		# CRC8: полином x^8 + x^5 + x^4 + 1 (0x31)
		crc = crcmod.predefined.mkPredefinedCrcFun(f"crc-{args.controlsum}")

		# объект класса C_COM_P_MASTER
		obj_com_p = C_COM_P_MASTER(
									port	 = args.comportname,
									baudrate = args.baudrate,
									bytesize = args.bytesize,
									stopbits = args.stopbits,
									timeout	 = args.timeout,
									crc		 = crc
									)

		LEN		 = 0x05	# ?
		CMD		 = 0x01	# ?
		PARAM	 = C_DATA_ITERATOR(args.filename, args.bytesize)

		# Микротесты
		obj_com_p.send_packet(LEN, CMD, PARAM)	# Запись 1
		obj_com_p.send_packet(LEN, CMD, PARAM)	# Запись 2
		obj_com_p.get_packet()					# Чтение
		obj_com_p.write_csv()					# Логирование


		obj_com_p.close()
