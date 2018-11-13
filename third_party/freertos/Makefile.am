#
#    Copyright 2016 The OpenThread Authors. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#

include $(abs_top_nlbuild_autotools_dir)/automake/pre.am

FREERTOS_ROOT              = $(top_srcdir)/third_party/freertos/repo/FreeRTOS
NIMBLE_ROOT               := $(top_srcdir)/third_party/mynewt-nimble/repo

EXTRA_DIST                 = $(NULL)

lib_LIBRARIES              = libfreertos.a


FREERTOS_SRC                                         := \
    repo/FreeRTOS/Source/croutine.c                              \
    repo/FreeRTOS/Source/event_groups.c                          \
    repo/FreeRTOS/Source/list.c                                  \
    repo/FreeRTOS/Source/queue.c                                 \
    repo/FreeRTOS/Source/tasks.c                                 \
    repo/FreeRTOS/Source/timers.c                                \
    $(NULL)

#    repo/FreeRTOS/Source/portable/GCC/ARM_CM4F/port.c

if OPENTHREAD_EXAMPLES_NRF52840
FREERTOS_SRC                                         += \
    repo/FreeRTOS/Source/portable/MemMang/heap_1.c               \
    $(NULL)
endif

libfreertos_a_SOURCES                                 = \
    $(FREERTOS_SRC)                                     \
    $(NULL)

#     -I$(FREERTOS_ROOT)/Source/portable/GCC/ARM_CM4F

libfreertos_a_CPPFLAGS                                = \
    -I$(FREERTOS_ROOT)/Source/include                   \
    -I$(NIMBLE_ROOT)/porting/examples/freertos_nrf52/include  \
    -I$(NIMBLE_ROOT)/porting/examples/freertos_nrf52/portable \
    -I$(top_srcdir)/third_party/NordicSemiconductor/dependencies \
    $(NULL)


if OPENTHREAD_BUILD_COVERAGE
Dash                                          = -
CLEANFILES                                    = $(shell find $(top_builddir)/third_party/freertos $(Dash)name "*.gcda" $(Dash)o $(Dash)name "*.gcno")
endif # OPENTHREAD_BUILD_COVERAGE

include $(abs_top_nlbuild_autotools_dir)/automake/post.am
