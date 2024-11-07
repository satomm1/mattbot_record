/****************************************************************************
 Module
   LedFSM.c

 Revision
   1.0.1

 Description
   This is a template file for implementing flat state machines under the
   Gen2 Events and Services Framework.

 Notes

 History
 When           Who     What/Why
 -------------- ---     --------
 01/15/12 11:12 jec      revisions for Gen2 framework
 11/07/11 11:26 jec      made the queue static
 10/30/11 17:59 jec      fixed references to CurrentEvent in RunTemplateSM()
 10/23/11 18:20 jec      began conversion from SMTemplate.c (02/20/07 rev)
****************************************************************************/
/*----------------------------- Include Files -----------------------------*/
/* include header files for this state machine as well as any machines at the
   next lower level in the hierarchy that are sub-machines to this machine
*/
#include "ES_Configure.h"
#include "ES_Framework.h"
#include "LedFSM.h"
#include "dbprintf.h"

/*----------------------------- Module Defines ----------------------------*/

/*---------------------------- Module Functions ---------------------------*/
/* prototypes for private functions for this machine.They should be functions
   relevant to the behavior of this state machine
*/

/*---------------------------- Module Variables ---------------------------*/
// everybody needs a state variable, you may need others as well.
// type of state variable should match htat of enum in header file
static LedState_t CurrentState;
static bool RightPulse = false;
static bool LeftPulse = false;

// with the introduction of Gen2, we need a module level Priority var as well
static uint8_t MyPriority;

/*------------------------------ Module Code ------------------------------*/
/****************************************************************************
 Function
     InitLedFSM

 Parameters
     uint8_t : the priorty of this service

 Returns
     bool, false if error in initialization, true otherwise

 Description
     Saves away the priority, sets up the initial transition and does any
     other required initialization for this state machine
 Notes

 Author
     J. Edward Carryer, 10/23/11, 18:55
****************************************************************************/
bool InitLedFSM(uint8_t Priority)
{
  ES_Event_t ThisEvent;

  MyPriority = Priority;
  
  // Set LED pins to digital outputs
  TRISBCLR = _TRISB_TRISB9_MASK;
  ANSELBCLR = _ANSELB_ANSB9_MASK;
  
  TRISCCLR = _TRISC_TRISC6_MASK;
  
  // put us into the Initial PseudoState
  CurrentState = InitPState_Led;
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
     PostLedFSM

 Parameters
     EF_Event_t ThisEvent , the event to post to the queue

 Returns
     boolean False if the Enqueue operation failed, True otherwise

 Description
     Posts an event to this state machine's queue
 Notes

 Author
     J. Edward Carryer, 10/23/11, 19:25
****************************************************************************/
bool PostLedFSM(ES_Event_t ThisEvent)
{
  return ES_PostToService(MyPriority, ThisEvent);
}

/****************************************************************************
 Function
    RunLedFSM

 Parameters
   ES_Event_t : the event to process

 Returns
   ES_Event_t, ES_NO_EVENT if no error ES_ERROR otherwise

 Description
   add your description here
 Notes
   uses nested switch/case to implement the machine.
 Author
   J. Edward Carryer, 01/15/12, 15:23
****************************************************************************/
ES_Event_t RunLedFSM(ES_Event_t ThisEvent)
{
  ES_Event_t ReturnEvent;
  ReturnEvent.EventType = ES_NO_EVENT; // assume no errors

  switch (CurrentState)
  {      
    case InitPState_Led:     
    {
      if (ThisEvent.EventType == ES_INIT)  
      {
        // Turn LEDs off
        LATBbits.LATB9 = 0;
        LATCbits.LATC6 = 0;
          
        CurrentState = Led_off;
        
      } 
    }
    break;

    case Led_off:      
    {
      switch (ThisEvent.EventType)
      {
        case EV_LED_ON: 
        {   
          LATBbits.LATB9 = 1;
          LATCbits.LATC6 = 1;
          CurrentState = Led_on;  
        }
        break;
        
        case EV_START_LEFT_PULSE: 
        {   
//            DB_printf("Start Left Pulse\r\n");
          LeftPulse = true;
          LATCbits.LATC6 = 1;
          CurrentState = Led_pulse_on;  
          ES_Timer_InitTimer(LED_TIMER, 250);
        }
        break;
        
        case EV_START_RIGHT_PULSE: 
        {   
//            DB_printf("Start Right Pulse\r\n");
          RightPulse = true;
          LATBbits.LATB9 = 1;
          CurrentState = Led_pulse_on;  
          ES_Timer_InitTimer(LED_TIMER, 250);
        }
        break;
        
        case ES_TIMEOUT:
        {
//            DB_printf("Start Pulses\r\n");
            if (RightPulse) {
                LATBbits.LATB9 = 1;
                CurrentState = Led_pulse_on; 
                ES_Timer_InitTimer(LED_TIMER, 250);
            }
            
            if (LeftPulse) {
                LATCbits.LATC6 = 1;
                CurrentState = Led_pulse_on;  
                ES_Timer_InitTimer(LED_TIMER, 250);
            }
        }
        break;

        default:
          ;
      }  
    }
    break;
    
    case Led_on:      
    {
      switch (ThisEvent.EventType)
      {
        case EV_LED_OFF: 
        {   
          LATBbits.LATB9 = 0;
          LATCbits.LATC6 = 0;
          CurrentState = Led_off;
        }
        break;

        default:
          ;
      }  
    }
    break;
    
    case Led_pulse_on:      
    {
      switch (ThisEvent.EventType)
      {
        case ES_TIMEOUT: 
        {   
          LATBbits.LATB9 = 0;
          LATCbits.LATC6 = 0;
          CurrentState = Led_off;          
          ES_Timer_InitTimer(LED_TIMER, 10000);
//          DB_printf("Stop Pulses\r\n");
        }
        break;
        
        case EV_START_LEFT_PULSE: 
        {   
          LeftPulse = true;
          LATCbits.LATC6 = 1;
        }
        break;
        
        case EV_START_RIGHT_PULSE: 
        {   
          RightPulse = true;
          LATBbits.LATB9 = 1;
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
     QueryLedSM

 Parameters
     None

 Returns
     LedState_t The current state of the Led state machine

 Description
     returns the current state of the Led state machine
 Notes

 Author
     J. Edward Carryer, 10/23/11, 19:21
****************************************************************************/
LedState_t QueryLedFSM(void)
{
  return CurrentState;
}

/***************************************************************************
 private functions
 ***************************************************************************/

