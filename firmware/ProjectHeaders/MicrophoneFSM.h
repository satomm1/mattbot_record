/****************************************************************************

  Header file for template Flat Sate Machine
  based on the Gen2 Events and Services Framework

 ****************************************************************************/

#ifndef FSMMicrophone_H
#define FSMMicrophone_H

// Event Definitions
#include "ES_Configure.h" /* gets us event definitions */
#include "ES_Types.h"     /* gets bool type for returns */

// typedefs for the states
// State definitions for use with the query function
typedef enum
{
  InitPState_Mic, MicRun
}MicrophoneState_t;

// Public Function Prototypes

bool InitMicrophoneFSM(uint8_t Priority);
bool PostMicrophoneFSM(ES_Event_t ThisEvent);
ES_Event_t RunMicrophoneFSM(ES_Event_t ThisEvent);
MicrophoneState_t QueryMicrophoneSM(void);

#endif /* FSMMicrophone_H */

