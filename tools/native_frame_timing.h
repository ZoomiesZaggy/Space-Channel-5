// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <algorithm>
#include <cstddef>
#include <vector>

// Presented-frame intervals, in milliseconds.
// Average FPS is the reciprocal of the mean interval.
// 1% low FPS is the reciprocal of the mean of the slowest 1% of intervals,
// rounded up and at least one interval. The input sequence is not reordered.
inline double nativeAverageFps(const double *frameMs, std::size_t count) {
 if (!count) return 0;
 double sum = 0;
 for (std::size_t i = 0; i < count; i++) sum += frameMs[i];
 if (sum <= 0) return 0;
 return static_cast<double>(count) * 1000.0 / sum;
}

inline double nativeOnePercentLowFps(const double *frameMs, std::size_t count) {
 if (!count) return 0;
 std::vector<double> ordered(frameMs, frameMs + count);
 std::sort(ordered.begin(), ordered.end());
 const std::size_t slow = std::max<std::size_t>(1, (count + 99) / 100);
 double sum = 0;
 for (std::size_t i = count - slow; i < count; i++) sum += ordered[i];
 if (sum <= 0) return 0;
 return static_cast<double>(slow) * 1000.0 / sum;
}
