/****************************************************************************
 Module
   MicrophoneFSM.c

 Revision
   1.0.1

 Description
   This a state machine for reading PCM data from an ICS-43434 mems microphone
   via I2S

 Notes

****************************************************************************/
/*----------------------------- Include Files -----------------------------*/
/* include header files for this state machine as well as any machines at the
   next lower level in the hierarchy that are sub-machines to this machine
*/
#include "ES_Configure.h"
#include "ES_Framework.h"
#include "MicrophoneFSM.h"
#include "sys/attribs.h"
#include "dsplib_dsp.h"
#include "dsplib_def.h"
#include "LedFSM.h"
#include "dbprintf.h"

// In testing mode, we output a 400 Hz signal at a 16000 Hz sample rate on SPI2
//#define TESTING
#define PRODUCTION
/*----------------------------- Module Defines ----------------------------*/

/*---------------------------- Module Functions ---------------------------*/
/* prototypes for private functions for this machine.They should be functions
   relevant to the behavior of this state machine
*/
static uint32_t reverseBits(uint32_t n);
static uint32_t swap_endianness(uint32_t value);

/*---------------------------- Module Variables ---------------------------*/
// everybody needs a state variable, you may need others as well.
// type of state variable should match htat of enum in header file
static MicrophoneState_t CurrentState;

// with the introduction of Gen2, we need a module level Priority var as well
static uint8_t MyPriority;

static uint32_t DataStoreLeft[128][2];
static uint32_t DataStoreRight[128][2];
static uint8_t StoreIndex = 0;
static uint16_t DataIndex = 0;
static bool Left = true;

static uint32_t signal_index = 0;
static int32_t signal800[40] = {0, 335950867,
663628993,974965352,1262293330,1518537519,1737387942,1913455439,2042404375,2121059399,
2147483644,2121026416,2042339221,1913359719,1737264013,1518388432,1262122757,974777493,
663428474,335742626,-210835,-336159105,-663829506,-975153201,-1262463891,-1518686591,
-1737511855,-1913551141,-2042469509,-2121092362,-2147483623,-2120993413,-2042274048,
-1913263981,-1737140067,-1518239331,-1261952172,-974589625,-663227949,-335534382};

/*------------------------------ Module Code ------------------------------*/
/****************************************************************************
 Function
     InitMicrophoneFSM

 Parameters
     uint8_t : the priority of this service

 Returns
     bool, false if error in initialization, true otherwise

 Description
     Saves away the priority, sets up the initial transition and does any
     other required initialization for this state machine
 Notes

 Author
     Matthew Sato, 10/18/24
****************************************************************************/
bool InitMicrophoneFSM(uint8_t Priority)
{
  ES_Event_t ThisEvent;

  MyPriority = Priority;
  // put us into the Initial PseudoState
  CurrentState = InitPState_Mic;
  
  // ************************** Auxiliary Pins ****************************** //
//  TRISBCLR = _TRISB_TRISB10_MASK | _TRISB_TRISB11_MASK;
//  LATBbits.LATB10 = 0;
//  LATBbits.LATB11 = 0;
  
  // ****************************** SPI1 ************************************ //
 
  // ******
  // Setup Inputs/Outputs and map to function
  // ******
  TRISACLR = _TRISA_TRISA7_MASK; // SS1 Digital Output
  RPA7R = 0b00011; // Map RA7 -> SS1

  TRISASET = _TRISA_TRISA0_MASK; // SDI1 Input
  ANSELACLR = _ANSELA_ANSA0_MASK; // SDI1 Digital
  SDI1R = 0b0000; // Map SDI1 -> RA0
  
  TRISACLR = _TRISA_TRISA11_MASK; // SDO1 Output
  ANSELACLR = _ANSELA_ANSA11_MASK; // SDO1 Digital
  RPA11R = 0b00011; // Map RA11 -> SDO1
  
  TRISBCLR = _TRISB_TRISB7_MASK; // SCK1 Output
  ANSELBCLR = _ANSELB_ANSB7_MASK; // SCK1 Digital
    
  // ******
  // Stop SPI Module, Clear Registers, and other basic setup
  // ******
  SPI1CONbits.ON = 0;
  SPI1CON2 = 0;
  SPI1BRG = 9; // 60 MHz clock -> 3 MHz baud rate
  while (SPI1STATbits.SPIRBE == 0) {
      uint32_t data = SPI1BUF; // Empty the receive buffer
  }
  SPI1CONbits.ENHBUF = 1; // Use the enhanced buffer
  SPI1STATbits.SPIROV = 0; // Clear receive overflow bit
  
  // ******
  // Setup SPI1 Interrupts
  // ******
  INTCONbits.MVEC = 1; // Use multivector mode
  PRISSbits.PRI7SS = 0b0111; // Priority 7 interrupt use shadow set 7
  PRISSbits.PRI6SS = 0b0110; // Priority 6 interrupt use shadow set 6
  IFS1CLR = _IFS1_SPI1RXIF_MASK | _IFS1_SPI1EIF_MASK; // Clear receive interrupt
  IPC8bits.SPI1EIP = 6;
  IPC8bits.SPI1EIS = 2;
  IPC9bits.SPI1RXIP = 7; // Receive interrupt Priority
  IPC9bits.SPI1RXIS = 2; // Receive interrupt subpriority
  IEC1SET = _IEC1_SPI1RXIE_MASK | _IEC1_SPI1EIE_MASK; // Enable receive interrupt
  __builtin_enable_interrupts(); // Global enable interrupts
    
  // ******
  // Setup Control Register 2
  // ******
  SPI1CON2bits.AUDEN = 1; // Enable audio support
  SPI1CON2bits.AUDMONO = 0; // Stereo audio
  SPI1CON2bits.AUDMOD = 0b00; // I2S mode
  SPI1CON2bits.IGNROV = 1; // A ROV is not a critical error; during ROV data in the FIFO is not overwritten by receive data
  SPI1CON2bits.IGNTUR = 1; 
  SPI1CON2bits.SPIROVEN = 1; // Receive overflow generates error events
  SPI1CON2bits.SPITUREN = 0; // Transmit Underrun Does Not Generates Error Events
  SPI1CON2bits.SPISGNEXT = 1; // Data from RX FIFO is sign extended: Data from Mic is 2's complement so want this
  
  // ******
  // Setup control register
  // ******
  SPI1CONbits.MSSEN = 1; // USe SS Pin
  SPI1CONbits.MCLKSEL = 0; // Use PBCLK2 FOr SPI1 and SPI2
  SPI1CONbits.DISSDO = 1; // SDO1 not used by module
  SPI1CONbits.MODE32 = 1; // 24-bit Data, 32-bit FIFO, 32-bit Channel/64-bit Frame
  SPI1CONbits.MODE16 = 1;
  SPI1CONbits.SMP = 0; // Input data sampled at middle of data output time
  SPI1CONbits.CKE = 0; // Serial output data changes on transition from idle clock state to active clock state
  SPI1CONbits.CKP = 1; // Default for I2S Mode
  SPI1CONbits.MSTEN = 1; // Host mode
  SPI1CONbits.DISSDI = 0; // SDI1 is used
  SPI1CONbits.SRXISEL = 0b11; // Interrupt is generated when the buffer is full
  
  
  // ****************************** SPI2 ************************************ //
  
  // ******
  // Setup Inputs/Outputs and map to function
  // ******
  TRISBSET = _TRISB_TRISB6_MASK; // SCK2 as Digital Input
  SCK2R = 0b0000; // SCK2 -> B6
   
  TRISDSET = _TRISD_TRISD8_MASK; // SS2 as Digital Input
  SS2R = 0b0111; // SS2 -> D8 
  
  TRISBSET = _TRISB_TRISB10_MASK;
//  SS2R = 0b0011; // SS2 -> B10 
  
  TRISBCLR = _TRISB_TRISB5_MASK; // SDO2 as Digital Output
  RPB5R = 0b00100; // B5 -> SDO2
  
  // B8 only Input, don't need to set TRIS
  SDI2R = 0100; // SDI2 -> B8
  
  // ******
  // Stop SPI Module, Clear Registers, and other basic setup
  // ******
  SPI2CONbits.ON = 0; // Turn SPI2 Off
  SPI2CON2 = 0; // Reset audio configuration register
  uint32_t rData = SPI2BUF; // Clear the receive buffer
  SPI2CONbits.ENHBUF = 1; // Use Enhanced Buffer Mode
  
  // No Interrupts Used for SPI2
  
  // ******
  // Setup Control Register 2
  // ******
  SPI2STATbits.SPIROV = 0; // Clear receive overflow bit
  SPI2CON2bits.AUDEN = 1; // Enable Audio protocol
  SPI2CON2bits.AUDMOD = 00; // I2S Mode
  SPI2CON2bits.AUDMONO = 0; // Audio data is stereo
  SPI2CON2bits.IGNTUR = 1; // A TUR is not a critical error and zeros are transmitted until the SPIxTXB is not empty
  
  // ******
  // Setup control register
  // ******
  SPI2CONbits.MSTEN = 0; // Client mode
  SPI2CONbits.CKP = 1; // Idle state for clock is a high level; active state is a low level (Default)
  SPI2CONbits.MODE32 = 1; // 32-bit Data, 32-bit FIFO, 32-bit Channel/64-bit Frame
  SPI2CONbits.MODE16 = 0;
  SPI2CONbits.DISSDI = 1; // SDI pin is not used by the SPI module (pin is controlled by PORT function) 
  SPI2CONbits.DISSDO = 0; // SDO2 pin is controlled by the module
  SPI2CONbits.SSEN = 1; // SS2 pin used for Client mode
  SPI2CONbits.CKE = 1; // Serial output data changes on transition from active clock state to Idle clock state
    
  // post the initial transition event
  ThisEvent.EventType = ES_INIT;
  if (ES_PostToService(MyPriority, ThisEvent) == true)
  {
    return true;
  }
  else
  {
    return false;
  }
}

/****************************************************************************
 Function
     PostMicrophoneFSM

 Parameters
     EF_Event_t ThisEvent , the event to post to the queue

 Returns
     boolean False if the Enqueue operation failed, True otherwise

 Description
     Posts an event to this state machine's queue
 Notes

 Author
     Matthew Sato, , 10/18/24
****************************************************************************/
bool PostMicrophoneFSM(ES_Event_t ThisEvent)
{
  return ES_PostToService(MyPriority, ThisEvent);
}

/****************************************************************************
 Function
    RunMicrophoneFSM

 Parameters
   ES_Event_t : the event to process

 Returns
   ES_Event_t, ES_NO_EVENT if no error ES_ERROR otherwise

 Description
   Just turns on the SPI modules after eveything is initialized
 Notes
 Author
   Matthew Sato, , 10/18/24
****************************************************************************/
ES_Event_t RunMicrophoneFSM(ES_Event_t ThisEvent)
{
  ES_Event_t ReturnEvent;
  ReturnEvent.EventType = ES_NO_EVENT; // assume no errors

  switch (CurrentState)
  {
    case InitPState_Mic: 
    {
      if (ThisEvent.EventType == ES_INIT)
      {
        CurrentState = MicRun;
        SPI2CONbits.ON = 1; // Turn SPI2 on
        SPI1CONbits.ON = 1; // Turn SPI1 on
      }
    }
    break;

    case MicRun:  
    {
      switch (ThisEvent.EventType)
      {
        case ES_TIMEOUT:
        {
          CurrentState = MicRun; 
        }
        break;

        default:
          ;
      }
    }
    break;
    
    default:
      ;
  }  
  return ReturnEvent;
}

/****************************************************************************
 Function
     QueryMicrophoneSM

 Parameters
     None

 Returns
     MicrophoneState_t The current state of the Microphone state machine

 Description
     returns the current state of the Microphone state machine
 Notes

 Author
     Matthew Sato, 10/18/24
****************************************************************************/
MicrophoneState_t QueryMicrophoneFSM(void)
{
  return CurrentState;
}

/***************************************************************************
 private functions
 ***************************************************************************/

/****************************************************************************
 Function
     swap_endianness

 Parameters
     uint32_t value: the value to swap endianness

 Returns
     uint32t_t: value, but with its endianness swapped

 Description
     Changes from Little Endian->Big Endian, or Big Endian->Little Endian
 Notes

 Author
     Matthew Sato, 10/18/24
****************************************************************************/
uint32_t swap_endianness(uint32_t value) {
  value = ((value << 8) & 0xFF00FF00) | ((value >> 8) & 0x00FF00FF);
  value = ((value << 16) & 0xFFFF0000) | ((value >> 16) & 0x0000FFFF);
  return value;
}

void __ISR(_SPI1_FAULT_VECTOR, IPL6SRS) SPI1FaultHandler(void)
{
    DB_printf("Receive Error\r\n");
    SPI1STATbits.SPIROV = 0;
    IFS1CLR = _IFS1_SPI1EIF_MASK;
}


void __ISR(_SPI1_RX_VECTOR, IPL7SRS) SPI1RXHandler(void)
{
    static uint32_t data1;
    static uint32_t data2;
    static uint32_t data3;
    static uint32_t data4;
    static bool received_left = false;
    static bool received_right = false;
    static uint32_t print_index = 0;
        
    data1 = SPI1BUF;
    data2 = SPI1BUF;
    data3 = SPI1BUF;
    data4 = SPI1BUF;
    DataStoreLeft[DataIndex][StoreIndex] = data1;
    DataStoreRight[DataIndex][StoreIndex] = data2;
    
    SPI1STATbits.SPIROV = 0 ;
    
    if (SPI2STATbits.TXBUFELM < 3) {
//         LATBbits.LATB10 = 1;
#ifdef TESTING
        SPI2BUF = signal800[signal_index];
        SPI2BUF = signal800[signal_index];
        signal_index += 1;
        if (signal_index == 40){
            signal_index = 0;
        }
#endif
#ifdef PRODUCTION
        SPI2BUF = data1;
        SPI2BUF = data2;
#endif
//        LATBbits.LATB10 = 0;
    }
    
    if (!received_left && DataStoreLeft[DataIndex][StoreIndex]) {
        received_left = true;
        ES_Event_t NewEvent = {EV_START_LEFT_PULSE, 0};
        PostLedFSM(NewEvent);
    }
    
    if (!received_right &&DataStoreRight[DataIndex][StoreIndex]) {
        received_right = true;
        ES_Event_t NewEvent = {EV_START_RIGHT_PULSE, 0};
        PostLedFSM(NewEvent);
    }
    
    // Increment the indices
    DataIndex++;
    if (DataIndex == 128) {
        DataIndex = 0;

        StoreIndex++;
        if (StoreIndex == 2) {
            StoreIndex = 0;
        }
    }  
    
    DataStoreLeft[DataIndex][StoreIndex] = data3;
    DataStoreRight[DataIndex][StoreIndex] = data4;
    
    if (SPI2STATbits.TXBUFELM < 3) {
#ifdef TESTING
        SPI2BUF = signal800[signal_index];
        SPI2BUF = signal800[signal_index];
        signal_index += 1;
        if (signal_index == 40){
            signal_index = 0;
        }
#endif
#ifdef PRODUCTION
        SPI2BUF = data3;
        SPI2BUF = data4;
#endif
    }
    
    // Clear interrupt flag
    IFS1CLR = _IFS1_SPI1RXIF_MASK;
}