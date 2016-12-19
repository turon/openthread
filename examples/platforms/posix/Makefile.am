#
#  Copyright (c) 2016, The OpenThread Authors.
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#  1. Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#  2. Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#  3. Neither the name of the copyright holder nor the
#     names of its contributors may be used to endorse or promote products
#     derived from this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
#  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
#  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
#  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
#  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
#  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
#  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
#  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
#  POSSIBILITY OF SUCH DAMAGE.
#

include $(abs_top_nlbuild_autotools_dir)/automake/pre.am

lib_LIBRARIES                             = libopenthread-posix.a

libopenthread_posix_a_CPPFLAGS            = \
    -fPIC                                   \
    -I$(top_srcdir)/include                 \
    -I$(top_srcdir)/examples/platforms      \
    -I$(top_srcdir)/src/core                \
    -I$(top_srcdir)/src/lib                 \
    -D_GNU_SOURCE                           \
    $(NULL)

PLATFORM_SOURCES                          = \
    alarm.c                                 \
    diag.c                                  \
    misc.c                                  \
    logging.c                               \
    radio.c                                 \
    random.c                                \
    uart-posix.c                            \
    flash.c                                 \
    spi-stubs.c                             \
    system.c                                \
    sim/alarm-sim.c                         \
    sim/platform-sim.c                      \
    sim/radio-sim.c                         \
    $(NULL)


if OPENTHREAD_BLE_HOST_NIMBLE
PLATFORM_SOURCES                         += \
    ble_nimble.c                            \
    ble_nimble_event.c                      \
    ble_stub.cpp                            \
    $(NULL)

libopenthread_posix_a_CPPFLAGS           +=                                             \
    -I$(top_srcdir)/third_party/mynewt-nimble/repo/porting/npl/linux/include            \
    -I$(top_srcdir)/third_party/mynewt-nimble/repo/porting/npl/linux/src                \
    -I$(top_srcdir)/third_party/mynewt-nimble/repo/porting/examples/linux/include       \
    -I$(top_srcdir)/third_party/mynewt-nimble/repo/porting/nimble/include               \
    -I$(top_srcdir)/third_party/mynewt-nimble/repo/nimble/include                       \
    -I$(top_srcdir)/third_party/mynewt-nimble/repo/nimble/host/include                  \
    -I$(top_srcdir)/third_party/mynewt-nimble/repo/nimble/host/src                      \
    -I$(top_srcdir)/third_party/mynewt-nimble/repo/nimble/host/services/ans/include     \
    -I$(top_srcdir)/third_party/mynewt-nimble/repo/nimble/host/services/gap/include     \
    -I$(top_srcdir)/third_party/mynewt-nimble/repo/nimble/host/services/gatt/include    \
    $(NULL)

# Do not enable -pedantic-errors
override CFLAGS      := $(filter-out -pedantic-errors,$(CFLAGS))
override CXXFLAGS    := $(filter-out -pedantic-errors,$(CXXFLAGS))

# Do not enable warnings as errors
override CFLAGS      := $(filter-out -Werror,$(CFLAGS))
override CXXFLAGS    := $(filter-out -Werror,$(CXXFLAGS))

# Do not enable strict C99 checks
override CFLAGS      := $(filter-out -std=c99,$(CFLAGS))
override CXXFLAGS    := $(filter-out -std=c99,$(CXXFLAGS))

endif # OPENTHREAD_BLE_HOST_NIMBLE


libopenthread_posix_a_SOURCES             = \
    $(PLATFORM_SOURCES)                     \
    $(NULL)

noinst_HEADERS                            = \
    platform-posix.h                        \
    platform-config.h                       \
    $(NULL)

PRETTY_FILES                              = \
    $(PLATFORM_SOURCES)                     \
    $(noinst_HEADERS)                       \
    $(NULL)

Dash                                      = -
libopenthread_posix_a_LIBADD              = \
    $(shell find $(top_builddir)/examples/platforms/utils $(Dash)type f $(Dash)name "*.o")

if OPENTHREAD_BUILD_COVERAGE
libopenthread_posix_a_CPPFLAGS           += \
    -DOPENTHREAD_ENABLE_COVERAGE            \
    $(NULL)

CLEANFILES                                = $(wildcard *.gcda *.gcno)
endif # OPENTHREAD_BUILD_COVERAGE

include $(abs_top_nlbuild_autotools_dir)/automake/post.am
