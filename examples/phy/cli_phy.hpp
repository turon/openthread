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
 *   This file contains definitions for the CLI interpreter.
 */

#ifndef CLI_PHY_HPP_
#define CLI_PHY_HPP_

#include <stdarg.h>

#include <cli/cli_base.hpp>
#include <cli/cli_server.hpp>
#include <common/timer.hpp>
#include <mac/mac.hpp>

#include <platform/radio.h>

using Thread::Timer;

namespace Thread {

/**
 * @namespace Thread::Cli
 *
 * @brief
 *   This namespace contains definitions for the CLI interpreter.
 *
 */
namespace Cli {
namespace Phy {

class PhyController 
{
public:
    enum PhyState
    {
        kStateDisabled = 0,
	kStateSleep = 1,
	kStateIdle = 2,
	kStateListen = 3,
	kStateReceive = 4,
	kStateTransmit = 5,
	kStateAckWait = 6,
    };

    PhyController();

    friend class Interpreter; 

    static void OnRxDone(void *aContext);
    static void OnTxDone(void *aContext);
    static void OnTimerFired(void *aContext);

private:
    void OnRxDone();
    void OnTxDone();
    void OnTimerFired();

    void NextOperation();
    ThreadError Receive();
    ThreadError Transmit();

    Timer mTimer;

    PhyState mState;

    uint8_t mChannel;
    uint16_t mPanId;
    uint8_t mSequence;

    uint8_t mLength;
    uint32_t mCount;
    uint32_t mPeriod;

    uint32_t mFemMode;
    uint32_t mFemBias;
    uint32_t mPowerCal;

    bool mReceive;
    uint32_t mNumReceived;
    uint32_t mNumSend;
    uint32_t mNumSent;
    uint32_t mReceiveStart;
    uint32_t mSendStart;

    bool mSleep;

    Mac::Frame mFrameTx;
    Mac::Frame mFrameRx;
};

/**
 * This class implements the CLI interpreter.
 *
 */
class Interpreter : public InterpreterBase
{
public:
    Interpreter();

private:
    enum
    {
        kMaxArgs = 8,
    };

    void Start(void);
  
    static void ProcessHelp(int argc, char *argv[]);
    static void ProcessChannel(int argc, char *argv[]);
    static void ProcessPanId(int argc, char *argv[]);

    static void ProcessCount(int argc, char *argv[]);
    static void ProcessLength(int argc, char *argv[]);
    static void ProcessPeriod(int argc, char *argv[]);

    static void ProcessState(int argc, char *argv[]);
    static void ProcessStateSleep(int argc, char *argv[]);
    static void ProcessStateIdle(int argc, char *argv[]);
    static void ProcessStateRx(int argc, char *argv[]);
    static void ProcessStateTx(int argc, char *argv[]);
    static void ProcessStateRxStop(int argc, char *argv[]);
    static void ProcessStateTxStop(int argc, char *argv[]);

    static void ProcessPowerCal(int argc, char *argv[]);
    static void ProcessFemBias(int argc, char *argv[]);
    static void ProcessFemMode(int argc, char *argv[]);
    static void ProcessGpio(int argc, char *argv[]);
    static void ProcessReset(int argc, char *argv[]);
    static void ProcessVersion(int argc, char *argv[]);

    static int Hex2Bin(const char *aHex, uint8_t *aBin, uint16_t aBinLength);
    static ThreadError ParseLong(char *argv, long &value);

    static const struct Command sCommands[];
};

}  // namespace Phy
}  // namespace Cli
}  // namespace Thread

#endif  // CLI_HPP_
