/*
 *    Copyright 2016 Nest Labs Inc. All Rights Reserved.
 *
 *    Licensed under the Apache License, Version 2.0 (the "License");
 *    you may not use this file except in compliance with the License.
 *    You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 *    Unless required by applicable law or agreed to in writing, software
 *    distributed under the License is distributed on an "AS IS" BASIS,
 *    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *    See the License for the specific language governing permissions and
 *    limitations under the License.
 */

/**
 * @file
 *   This file implements the CLI interpreter.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <openthread.h>

#include "cli_base.hpp"
#include <common/encoding.hpp>

using Thread::Encoding::BigEndian::HostSwap16;

namespace Thread {
namespace Cli {

Server *InterpreterBase::sServer;

InterpreterBase::InterpreterBase(const struct Command *aCommandTable, 
				 uint16_t aCommandTableSize) : 
    mCommands(aCommandTable), 
    mCommandsSize(aCommandTableSize)
{
}

void InterpreterBase::ProcessLine(char *aBuf, uint16_t aBufLength, 
				  Server &aServer)
{
    char *argv[kMaxArgs];
    char *cmd;
    int argc;
    char *last;

    sServer = &aServer;

    VerifyOrExit((cmd = strtok_r(aBuf, " ", &last)) != NULL, ;);

    for (argc = 0; argc < kMaxArgs; argc++)
    {
        if ((argv[argc] = strtok_r(NULL, " ", &last)) == NULL)
        {
            break;
        }
    }

    for (unsigned int i = 0; i < mCommandsSize / sizeof(struct Command); i++)
    {
        if (strcmp(cmd, mCommands[i].mName) == 0)
        {
            mCommands[i].mCommand(argc, argv);
            break;
        }
    }

exit:
    return;
}

}  // namespace Cli
}  // namespace Thread
