// Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
// This file is part of Checkmk (https://checkmk.com). It is subject to the
// terms and conditions defined in the file COPYING, which is part of this
// source code package.

#ifndef Downtime_h
#define Downtime_h

#include "config.h"  // IWYU pragma: keep

#include <chrono>
#include <string>

#include "nagios.h"

// TODO(sp): Merge with DowntimeData
class Downtime {
public:
    unsigned long _id;
    std::string _author;
    std::string _comment;
    bool _origin_is_rule;
    std::chrono::system_clock::time_point _entry_time;
    std::chrono::system_clock::time_point _start_time;
    std::chrono::system_clock::time_point _end_time;
    bool _fixed;
    std::chrono::nanoseconds _duration;
    // --------------------------------------------------
    int _type;
    bool _is_service;
    host *_host;
    service *_service;
    unsigned long _triggered_by;
    bool _is_active;
};

#endif  // Downtime_h
