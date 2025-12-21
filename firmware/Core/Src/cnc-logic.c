#include "cnc-logic.h"
#include "string.h"
#include "stdio.h"
#include "stdlib.h"
#include "math.h"

uint8_t uartRxBuffer[UART_RX_BUFFER_SIZE];
uint16_t numberOfReceivedBytes = 0;
uint8_t cmdLen = 0;
uint8_t sqn    = 0;
uint8_t receivedCrc = 0;

//UART RX receive stage flags
bool signReceivedFlag  = false;
bool lenReceivedFlag   = false;
bool sqnReceivedFlag   = false;
bool addrReceivedFlag  = false;
bool uartRxComplete    = false;

//Uart RX error flags
bool wrongSignFlag     = false;
bool wrongLenFlag      = false;
bool wrongSqnFlag      = false;
bool wrongAddrFlag     = false;
bool wrongCrcFlag      = false;
bool packageTooBigFlag = false;
bool badPackageFlag    = false;

bool unknownCmdFlag    = false;
bool wrongGcodeFlag    = false;
bool wrongGcoordFlag   = false;
bool wrongGspeedFlag   = false;
bool badCmdFlag        = false;

bool errorFlag         = false;

bool commandRunSuccess = false;

uint8_t  command;
uint8_t *params;

cnc_struct   Cnc;
gArgs_struct gArgs;

int stepsQuantityX = 0;
int stepsQuantityY = 0;

periph_struct periph;
 
void InitDevice()
{
	periph = GetPeriph();
	StartUartReceive();
}

void MainLogic()
{
	errorFlag = badPackageFlag || badCmdFlag;
	
	if (errorFlag)
	{
		ReportError();
		ClearError();
		StartUartReceive();
	}
	else if (uartRxComplete)
	{
		ReportRxSuccess();
		RunReceivedCommand();
	}
	
	if (commandRunSuccess)
	{
		ReportCommandRunSuccess();
		StartUartReceive();
	}
}

void ReportError(void)
{
	uint8_t err[] = "SOME_ERR\n\r";
	HAL_UART_Transmit(periph.uart, err, sizeof(err), 100);
}

void ReportRxSuccess(void)
{
	uint8_t suc[] = "RX_COMPLETE!\n\r";
	HAL_UART_Transmit(periph.uart, suc, sizeof(suc), 100);
}

void ReportCommandRunSuccess()
{
	uint8_t suc[] = "CMD_COMPLETE!\n\r";
	HAL_UART_Transmit(periph.uart, suc, sizeof(suc), 100);
}

void ClearError(void)
{
	badPackageFlag = false;
	badCmdFlag     = false;
}

void StartUartReceive()
{
	numberOfReceivedBytes = 0;
	badPackageFlag = false;
	uartRxComplete = false;
	HAL_UART_Receive_IT(periph.uart, uartRxBuffer, 1);
}

void ReceiveUart()
{
	numberOfReceivedBytes++;
	
	signReceivedFlag = (numberOfReceivedBytes >= SIGN_END_INDEX + 1);
	lenReceivedFlag  = (numberOfReceivedBytes >= LEN_INDEX  + 1);
	sqnReceivedFlag  = (numberOfReceivedBytes >= SQN_INDEX  + 1);
	addrReceivedFlag = (numberOfReceivedBytes >= ADDR_INDEX + 1);
	uartRxComplete   =  lenReceivedFlag && (numberOfReceivedBytes == LEN_INDEX + cmdLen + 1);
	
	if (lenReceivedFlag)
	{
		cmdLen = uartRxBuffer[LEN_INDEX];
	}
	else if (uartRxComplete)
	{
		receivedCrc = uartRxBuffer[numberOfReceivedBytes - 1];
		uartRxBuffer[numberOfReceivedBytes] = '\0';
	}
	
	packageTooBigFlag = numberOfReceivedBytes > 256;
	
	wrongLenFlag      = lenReceivedFlag  && ((cmdLen < 4) || (cmdLen > 253));
	wrongSignFlag     = signReceivedFlag && ((uartRxBuffer[0] != 0xAC) || (uartRxBuffer[1] != 0x53));
	wrongSqnFlag      = sqnReceivedFlag  && (uartRxBuffer[SQN_INDEX]  != sqn);
	wrongAddrFlag     = addrReceivedFlag && (uartRxBuffer[ADDR_INDEX] != DEVICE_ADDR);
	wrongCrcFlag      = uartRxComplete   && (receivedCrc != CalcCrc8(uartRxBuffer, numberOfReceivedBytes));
	
	badPackageFlag    = wrongLenFlag || wrongSignFlag ||
	                    wrongSqnFlag || wrongAddrFlag ||
	                    wrongCrcFlag || packageTooBigFlag;
 	
	if (!badPackageFlag && !uartRxComplete) 
	{
		HAL_UART_Receive_IT(periph.uart, uartRxBuffer, 1);
	}
}

void RunReceivedCommand(void)
{
	command = uartRxBuffer[CMD_INDEX];
	params  = (uartRxBuffer + PARAM_START_INDEX);
	
	switch (command)
	{
		case 0x50: 
			ParseGcode(params, cmdLen - 1);
			break;
		
	}
	
	badCmdFlag = unknownCmdFlag  || wrongGcodeFlag ||
	             wrongGcoordFlag || wrongGspeedFlag;
	
	commandRunSuccess = !badCmdFlag;
}

uint8_t CalcCrc8(uint8_t *data, uint16_t len)
{
	uint8_t crc  = 0x00;
	uint8_t poly = 0x31;      // x^8 + x^5 + x^4 + 1

	for (uint16_t i = 0; i < len; i++)
	{
		crc ^= data[i];
		for (uint8_t b = 0; b < 8; b++)
		{
			if  (crc & 0x80) {crc = (crc << 1) ^ poly;}
			else             {crc <<= 1;}
		}
	}

	return crc;
}

void ParseGcode(uint8_t *gcode, uint8_t gcodeLen)
{
	gArgs.x = GetGcodeArg(gcode, 'X', Cnc.x);
	gArgs.y = GetGcodeArg(gcode, 'Y', Cnc.y);
	gArgs.i = GetGcodeArg(gcode, 'I', 0);
  gArgs.j = GetGcodeArg(gcode, 'J', 0);
	gArgs.f = GetGcodeArg(gcode, 'F', Cnc.feedRate);
	
	gArgs.g = (int)GetGcodeArg(gcode, 'G', -1);
	
	SetFeedRate(gArgs.f);
	
	switch(gArgs.g)
	{
		case 00:
			G00();
			break;
		
		case 01:
			G01();
			break;
				
		case 02:
			G02();
			break;
				
		case 03:
			G03();
			break;
		
		case 90:
			G90();
			break;
		
		case 91:
			G91();
			break;
		
		default:
			wrongGcodeFlag = true;
	}
}

float GetGcodeArg(uint8_t *gcode, char name, float defaultValue)
{
	char* argPtr = strchr((char*)gcode, name);
	if (argPtr == NULL)
	{
		return defaultValue;
	}
	else
	{
		return atof(argPtr + 1);
	}
}

float CalcTargetX(float x)
{
	if (Cnc.isAbsolute) 
	{
		return x;
	}
	
	return Cnc.x + x;
}

float CalcTargetY(float y)
{
	if (Cnc.isAbsolute) 
	{
		return y;
	}
	
	return Cnc.y + y;
}

void SetFeedRate(float feedRate)
{
	
}
void MoveTo(float x, float y, bool isRapid)
{
	wrongGcoordFlag = (x < 0) || (x > 330) || (y < 0) || (y > 228);
	if (wrongGcoordFlag) {return;}
	
	Cnc.targetX = x;
	Cnc.targetY = y;
	
	float xDiff = fabs(Cnc.x - x);
	float yDiff = fabs(Cnc.y - y);
	stepsQuantityX = xDiff / STEP;
	stepsQuantityY = yDiff / STEP;
}

void G00(void)
{
	float newX = CalcTargetX(gArgs.x);
	float newY = CalcTargetY(gArgs.x);
	
	MoveTo(newX, newY, true);
}

void G01(void)
{
	float newX = CalcTargetX(gArgs.x);
	float newY = CalcTargetY(gArgs.x);
	
	MoveTo(newX, newY, false);
}

void G02(void)
{
	float centerX = gArgs.x + gArgs.i;
	float centerY = gArgs.x + gArgs.j;
	
	float r;
}

void G03(void)
{
}

void G90(void)
{
	Cnc.isAbsolute = true;
}

void G91(void)
{
	Cnc.isAbsolute = false;
}