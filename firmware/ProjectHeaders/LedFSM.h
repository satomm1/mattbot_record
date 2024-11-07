/****************************************************************************

  Header file for LED Flat Sate Machine
  based on the Gen2 Events and Services Framework

 ****************************************************************************/

#ifndef FSMLed_H
#define FSMLed_H

// Event Definitions
#include "ES_Configure.h" /* gets us event definitions */
#include "ES_Types.h"     /* gets bool type for returns */

// typedefs for the states
// State definitions for use with the query function
typedef enum
{
  InitPState_Led, Led_off, Led_on, Led_pulse_on, Led_pulse_off
}LedState_t;

// Public Function Prototypes

bool InitLedFSM(uint8_t Priority);
bool PostLedFSM(ES_Event_t ThisEvent);
ES_Event_t RunLedFSM(ES_Event_t ThisEvent);
LedState_t QueryLedSM(void);

#endif /* FSMLed_H */

