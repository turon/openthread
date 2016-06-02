/*
 *  Copyright (c) 2016, Nest Labs, Inc.
 *  All rights reserved.
 *
 *  Redistribution and use in source and binary forms, with or without
 *  modification, are permitted provided that the following conditions are met:
 *  1. Redistributions of source code must retain the above copyright
 *     notice, this list of conditions and the following disclaimer.
 *  2. Redistributions in binary form must reproduce the above copyright
 *     notice, this list of conditions and the following disclaimer in the
 *     documentation and/or other materials provided with the distribution.
 *  3. Neither the name of the copyright holder nor the
 *     names of its contributors may be used to endorse or promote products
 *     derived from this software without specific prior written permission.
 *
 *  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 *  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 *  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 *  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 *  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 *  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 *  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 *  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 *  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 *  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 *  POSSIBILITY OF SUCH DAMAGE.
 */

/**
 * @file
 *   This file implements the CLI interpreter.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <openthread.h>

#include "cli_phy.hpp"
#include <common/encoding.hpp>
#include <common/tasklet.hpp>
#include <platform/radio.h>

using Thread::Encoding::BigEndian::HostSwap16;

namespace Thread {
namespace Cli {
namespace Phy {

static PhyController sPhyController;

static Tasklet sOnRxDoneTask(&PhyController::OnRxDone, NULL);
static Tasklet sOnTxDoneTask(&PhyController::OnTxDone, NULL);


const struct Command Interpreter::sCommands[] =
{
    { "?", &ProcessHelp },
    { "help", &ProcessHelp },

    // Phy parameters
    { "channel", &ProcessChannel },
    { "panid", &ProcessPanId },

    // Transmission test parameters
    { "count", &ProcessCount },
    { "length", &ProcessLength },
    { "period", &ProcessPeriod },

    // Control radio state
    { "state", &ProcessState },
    { "sleep", &ProcessStateSleep },
    { "idle", &ProcessStateIdle },
    { "rx", &ProcessStateRx },
    { "tx", &ProcessStateTx },
    { "rxstop", &ProcessStateRxStop },
    { "txstop", &ProcessStateTxStop },

    // Factory diagnostics
    { "powercal", &ProcessPowerCal },
    { "fembias", &ProcessFemBias },
    { "femmode", &ProcessFemMode },
    { "gpio", &ProcessGpio },
    { "reset", &ProcessReset },
    { "version", &ProcessVersion },
};


Interpreter::Interpreter() : InterpreterBase(sCommands, sizeof(sCommands))
{
}

/**
 * Sets the default panid.  
 * Note: Channel set in each packet.
 */
void Interpreter::Start(void) 
{
    PhyController *phy = &sPhyController;
    otPlatRadioEnable();
    otPlatRadioSetPanId(phy->mPanId);
}

int Interpreter::Hex2Bin(const char *aHex, uint8_t *aBin, uint16_t aBinLength)
{
    uint16_t hexLength = strlen(aHex);
    const char *hexEnd = aHex + hexLength;
    uint8_t *cur = aBin;
    uint8_t numChars = hexLength & 1;
    uint8_t byte = 0;

    if ((hexLength + 1) / 2 > aBinLength)
    {
        return -1;
    }

    while (aHex < hexEnd)
    {
        if ('A' <= *aHex && *aHex <= 'F')
        {
            byte |= 10 + (*aHex - 'A');
        }
        else if ('a' <= *aHex && *aHex <= 'f')
        {
            byte |= 10 + (*aHex - 'a');
        }
        else if ('0' <= *aHex && *aHex <= '9')
        {
            byte |= *aHex - '0';
        }
        else
        {
            return -1;
        }

        aHex++;
        numChars++;

        if (numChars >= 2)
        {
            numChars = 0;
            *cur++ = byte;
            byte = 0;
        }
        else
        {
            byte <<= 4;
        }
    }

    return cur - aBin;
}

ThreadError Interpreter::ParseLong(char *argv, long &value)
{
    char *endptr;
    value = strtol(argv, &endptr, 0);
    return (*endptr == '\0') ? kThreadError_None : kThreadError_Parse;
}

void Interpreter::ProcessHelp(int argc, char *argv[])
{
    for (unsigned int i = 0; i < sizeof(sCommands) / sizeof(sCommands[0]); i++)
    {
        sServer->OutputFormat("%s\r\n", sCommands[i].mName);
    }
}

void Interpreter::ProcessChannel(int argc, char *argv[])
{
    ThreadError error = kThreadError_None;
    long value;

    if (argc == 0)
    {
        sServer->OutputFormat("%d\r\n", sPhyController.mChannel);
    }
    else
    {
        SuccessOrExit(error = ParseLong(argv[0], value));
	sPhyController.mChannel = value;
	// Reassert state so new channel will take.
	sPhyController.NextOperation();  
    }

    sServer->OutputFormat("Done\r\n");

exit:
    if (error) sServer->OutputFormat("Error: %d\r\n", error);
}

void Interpreter::ProcessPanId(int argc, char *argv[])
{
    ThreadError error = kThreadError_None;
    long value;

    if (argc == 0)
    {
        sServer->OutputFormat("%d\r\n", sPhyController.mPanId);
    }
    else
    {
        SuccessOrExit(error = ParseLong(argv[0], value));
        otPlatRadioSetPanId(value);
	sPhyController.mPanId = value;
    }

    sServer->OutputFormat("Done\r\n");

exit:
    if (error) sServer->OutputFormat("Error: %d\r\n", error);
}


void Interpreter::ProcessCount(int argc, char *argv[])
{
    ThreadError error = kThreadError_None;
    long value;

    if (argc == 0)
    {
        sServer->OutputFormat("%d\r\n", sPhyController.mCount);
    }
    else
    {
        SuccessOrExit(error = ParseLong(argv[0], value));
        sPhyController.mCount = value;
    }

    sServer->OutputFormat("Done\r\n");

exit:
    if (error) sServer->OutputFormat("Error: %d\r\n", error);
}
 
void Interpreter::ProcessLength(int argc, char *argv[])
{
    ThreadError error = kThreadError_None;
    long value;

    if (argc == 0)
    {
        sServer->OutputFormat("%d\r\n", sPhyController.mLength);
    }
    else
    {
        SuccessOrExit(error = ParseLong(argv[0], value));
        sPhyController.mLength = value;
    }

    sServer->OutputFormat("Done\r\n");

exit:
    if (error) sServer->OutputFormat("Error: %d\r\n", error);
}
 
void Interpreter::ProcessPeriod(int argc, char *argv[])
{
    ThreadError error = kThreadError_None;
    long value;

    if (argc == 0)
    {
        sServer->OutputFormat("%d\r\n", sPhyController.mPeriod);
    }
    else
    {
        SuccessOrExit(error = ParseLong(argv[0], value));
        sPhyController.mPeriod = value;
    }

    sServer->OutputFormat("Done\r\n");

exit:
    if (error) sServer->OutputFormat("Error: %d\r\n", error);
}

/**
 *  CLI command to get and set tx power calibration settings.
 *
 *  powercal <channel> <tx power>
 */
void Interpreter::ProcessPowerCal(int argc, char *argv[])
{
    ThreadError error = kThreadError_None;
    long value;

    if (argc == 0)
    {
        // TODO: dereference array with channel index
        sServer->OutputFormat("%d\r\n", sPhyController.mPowerCal);
    }
    else
    {
        SuccessOrExit(error = ParseLong(argv[0], value));
        sPhyController.mPowerCal = value;
    }

    sServer->OutputFormat("Warning: not implemented.\r\n");
    sServer->OutputFormat("Done\r\n");

exit:
    if (error) sServer->OutputFormat("Error: %d\r\n", error);
}

void Interpreter::ProcessFemBias(int argc, char *argv[])
{
    ThreadError error = kThreadError_None;
    long value;

    if (argc == 0)
    {
        // TODO: dereference array with channel index
        sServer->OutputFormat("%d\r\n", sPhyController.mFemBias);
    }
    else
    {
        SuccessOrExit(error = ParseLong(argv[0], value));
        sPhyController.mFemBias = value;
    }

    sServer->OutputFormat("Warning: not implemented.\r\n");
    sServer->OutputFormat("Done\r\n");

exit:
    if (error) sServer->OutputFormat("Error: %d\r\n", error);
}

void Interpreter::ProcessFemMode(int argc, char *argv[])
{
    ThreadError error = kThreadError_None;
    long value;

    if (argc == 0)
    {
        // TODO: dereference array with channel index
        sServer->OutputFormat("%d\r\n", sPhyController.mFemMode);
    }
    else
    {
        SuccessOrExit(error = ParseLong(argv[0], value));
        sPhyController.mFemMode = value;
    }

    sServer->OutputFormat("Warning: not implemented.\r\n");
    sServer->OutputFormat("Done\r\n");

exit:
    if (error) sServer->OutputFormat("Error: %d\r\n", error);
}

void Interpreter::ProcessGpio(int argc, char *argv[])
{
    ThreadError error = kThreadError_None;
    long value;

    if (argc == 0)
    {
        // TODO: dereference array with channel index
        sServer->OutputFormat("%d\r\n", 1);
    }
    else
    {
        SuccessOrExit(error = ParseLong(argv[0], value));
    }

    sServer->OutputFormat("Warning: not implemented.\r\n");
    sServer->OutputFormat("Done\r\n");

exit:
    if (error) sServer->OutputFormat("Error: %d\r\n", error);
}

void Interpreter::ProcessReset(int argc, char *argv[])
{
    ThreadError error = kThreadError_None;

    sServer->OutputFormat("Warning: not implemented.\r\n");
    sServer->OutputFormat("Done\r\n");

    if (error) sServer->OutputFormat("Error: %d\r\n", error);
}

void Interpreter::ProcessVersion(int argc, char *argv[])
{
    ThreadError error = kThreadError_None;
    // TODO: print chip and version
    sServer->OutputFormat("%s HW vX.X, FW vX.X\r\n", "CPU");
    sServer->OutputFormat("Done\r\n");

    if (error) sServer->OutputFormat("Error: %d\r\n", error);
}


void Interpreter::ProcessState(int argc, char *argv[])
{
    switch (sPhyController.mState)
    {
      case PhyController::kStateDisabled: 
	sServer->OutputFormat("disabled\r\n"); 
	break;
      case PhyController::kStateSleep:    
	sServer->OutputFormat("sleep\r\n");    
	break;
      case PhyController::kStateIdle:     
	sServer->OutputFormat("idle\r\n");     
	break;
      case PhyController::kStateListen:   
	sServer->OutputFormat("listen\r\n");   
	break;
      case PhyController::kStateReceive:  
	sServer->OutputFormat("rx\r\n");       
	break;
      case PhyController::kStateTransmit: 
	sServer->OutputFormat("tx\r\n");       
	break;
      case PhyController::kStateAckWait:  
	sServer->OutputFormat("ack_wait\r\n"); 
	break;
    }
    sServer->OutputFormat("Done\r\n");
}
  
void Interpreter::ProcessStateSleep(int argc, char *argv[])
{
    PhyController *phy = &sPhyController;
    phy->mSleep = true;
    phy->mReceive = false;
    phy->mNumSend = 0;
    phy->mNumSent = 0;
    phy->NextOperation();
    sServer->OutputFormat("Done\r\n");
}

void Interpreter::ProcessStateIdle(int argc, char *argv[])
{
    PhyController *phy = &sPhyController;
    phy->mSleep = false;
    phy->mReceive = false;
    phy->mNumSend = 0;
    phy->mNumSent = 0;
    phy->NextOperation();
    sServer->OutputFormat("Done\r\n");
}

void Interpreter::ProcessStateRx(int argc, char *argv[])
{
    PhyController *phy = &sPhyController;
    phy->mReceive = true;
    phy->mNumReceived = 0;
    phy->NextOperation();
    sServer->OutputFormat("Done\r\n");
}

void Interpreter::ProcessStateTx(int argc, char *argv[])
{
    PhyController *phy = &sPhyController;
    phy->mNumSend = 0;
    phy->mNumSent = 0;
    phy->mSendStart = Timer::GetNow();
    phy->mTimer.Start(phy->mPeriod);
    sServer->OutputFormat("Done\r\n");
}

void Interpreter::ProcessStateRxStop(int argc, char *argv[])
{
    // TODO: Terminate RX
    sServer->OutputFormat("Warning: not implemented.\r\n");
    sServer->OutputFormat("Done\r\n");
}

void Interpreter::ProcessStateTxStop(int argc, char *argv[])
{
    // TODO: Terminate TX
    sServer->OutputFormat("Warning: not implemented.\r\n");
    sServer->OutputFormat("Done\r\n");
}



PhyController::PhyController() : mTimer(&OnTimerFired, this)
{
    mState = kStateIdle;

    mChannel = 11;
    mPanId = 0xfffe;
    mSequence = 0;

    mLength = 16;
    mCount = 10;
    mPeriod = 100;

    mFemMode = 0;
    mFemBias = 0;
    mPowerCal = 0;

    mReceive = false;
    mNumReceived = 0;
    mNumSend = 0;
    mNumSent = 0;
    mReceiveStart = 0;
    mSendStart = 0;
}

void PhyController::OnTimerFired(void *context)
{
    PhyController *obj = reinterpret_cast<PhyController *>(context);
    obj->OnTimerFired();
}

void PhyController::OnTimerFired()
{
    mNumSend++;
    NextOperation();

    if (mNumSend < mCount)
    {
        mTimer.Start(mPeriod);
    }
}

void PhyController::NextOperation()
{
    if (Transmit() != kThreadError_None)
    {
        Receive();
    }
}

ThreadError PhyController::Transmit()
{
    ThreadError error = kThreadError_None;

    VerifyOrExit(mNumSent < mNumSend, error = kThreadError_Error);
    SuccessOrExit(error = otPlatRadioIdle());

    mFrameTx.SetChannel(mChannel);
    mFrameTx.InitMacHeader(Mac::Frame::kFcfFrameData | 
			   Mac::Frame::kFcfDstAddrShort |
			   Mac::Frame::kFcfSrcAddrNone, 
			   Mac::Frame::kSecNone);
    mFrameTx.SetSequence(mSequence++);
    mFrameTx.SetDstPanId(mPanId);
    mFrameTx.SetDstAddr(Mac::kShortAddrBroadcast);
    mFrameTx.SetLength(mLength);

    int count;
    count = 0;

    for (uint8_t *payload = mFrameTx.GetPayload(); 
	 payload < mFrameTx.GetFooter(); payload++)
    {
        *payload = count++;
    }

    SuccessOrExit(error = otPlatRadioTransmit((RadioPacket*)&mFrameTx));
    mState = PhyController::kStateTransmit;

exit:
    return error;
}

ThreadError PhyController::Receive()
{
    ThreadError error = kThreadError_None;

    SuccessOrExit(error = otPlatRadioIdle());

    if (mSleep)
    {
        SuccessOrExit(error = otPlatRadioSleep());
	mState = PhyController::kStateSleep;
	InterpreterBase::sServer->OutputFormat("state = sleep\r\n");
    }
    else if (mReceive)
    {
        mFrameRx.SetChannel(mChannel);
        SuccessOrExit(error = otPlatRadioReceive((RadioPacket*)&mFrameRx));
	mState = PhyController::kStateReceive;
	InterpreterBase::sServer->OutputFormat("state = receive\r\n");
    }
    else
    {
	mState = PhyController::kStateIdle;
        InterpreterBase::sServer->OutputFormat("state = idle\r\n");
    }

exit:
    return error;
}


void PhyController::OnTxDone(void *aContext)
{
    sPhyController.OnTxDone();
}

void PhyController::OnTxDone(void)
{
    ThreadError error;
    bool rxPending;

    error = otPlatRadioHandleTransmitDone(&rxPending);

    VerifyOrExit(error == kThreadError_None, ;);
    mState = PhyController::kStateIdle;
    mNumSent++;

    InterpreterBase::sServer->OutputFormat("%u: sent(count=%u)\r\n", 
					   Timer::GetNow() - mSendStart, 
					   mNumSent);

exit:
    if (error) {
      InterpreterBase::sServer->OutputFormat("Error: phy.OnTxDone %d\r\n", error);
    }
    NextOperation();
}


void PhyController::OnRxDone(void *aContext)
{
    sPhyController.OnRxDone();
}

void PhyController::OnRxDone(void)
{
    ThreadError error;

    error = otPlatRadioHandleReceiveDone();
    VerifyOrExit(error == kThreadError_None, ;);

    if (mNumReceived == 0)
    {
        mReceiveStart = Timer::GetNow();
    }

    mNumReceived++;

    InterpreterBase::sServer->OutputFormat(
                     "%d: received(count=%d,length=%d,rssi=%d)\r\n",
		     Timer::GetNow() - mReceiveStart, 
		     mNumReceived, mFrameRx.GetLength(), mFrameRx.GetPower());

exit:
    if (error) {
      InterpreterBase::sServer->OutputFormat("Error: phy.OnRxDone %d\r\n", error);
    }
    NextOperation();
}


extern "C" void otPlatRadioSignalReceiveDone(void)
{
    sOnRxDoneTask.Post();
}

extern "C" void otPlatRadioSignalTransmitDone(void)
{
    sOnTxDoneTask.Post();
}


}  // namespace Phy
}  // namespace Cli
}  // namespace Thread
