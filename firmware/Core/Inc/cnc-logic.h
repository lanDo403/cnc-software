#include "main.h"
#include "stdbool.h"

#define UART_RX_BUFFER_SIZE 257
#define DEVICE_ADDR 1

#define SIGN_END_INDEX         1
#define LEN_INDEX              2
#define SQN_INDEX              3
#define ADDR_INDEX             4
#define CMD_INDEX              5
#define PARAM_START_INDEX      6

#define STEP 0.01

typedef struct
{
	bool wrongSign;
	bool wrongLen;
	bool wrongSqn;
	bool wrongAddr;
	bool wrongCrc;
	bool packageTooBig;
	bool badPackage;

	bool unknownCmd;
	bool wrongGcode;
	bool wrongGcoord;
	bool wrongGspeed;
	bool badCmd;
	
} error_struct;

typedef struct 
{
	float x;   
	float y;   
  float targetX;        
  float targetY;        
  float feedRate;
	bool  isAbsolute;
	
} cnc_struct;

typedef struct
{
	float x;
	float y;
	float i;
	float j;
	float f;
	int   g;
	
} gArgs_struct;

void InitDevice(void);
void MainLogic(void);
void StartUartReceive(void);
void ReceiveUart(void);
void ReportError(void);
void ReportRxSuccess(void);
void ReportCommandRunSuccess(void);
void ClearError(void);
uint8_t CalcCrc8(uint8_t *data, uint16_t len);

void  RunReceivedCommand(void);
void  ParseGcode(uint8_t* gcode, uint8_t  len);
float GetGcodeArg(uint8_t *gcode, char name, float defaultValue);
float CalcTargetX(float x);
float CalcTargetY(float y);
void  SetFeedRate(float feedRate);
void  MoveTo(float x, float y, bool isRapid);

void G00(void);
void G01(void);
void G02(void);
void G03(void);
void G90(void);
void G91(void);