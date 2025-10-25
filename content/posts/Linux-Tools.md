---
date: 2020-04-27 20:10:35
draft: false
slug: SAR Linux-Tools
categories:
- performance
tags:
- linux
- tool
title: SAR Linux Tools
name: yc0
---
# System Activity Reporter Tool Summary

`sar` is an abbreviation for **System Activity Reporter** and is described as a powerful tool for diagnosing system bottlenecks. It works by continuously sampling the current system state and calculating data and ratios to provide a comprehensive report on the system's operational status.

## Key Characteristics

* **Comprehensive:** Considered one of the most comprehensive performance analysis tools on Linux, reporting on up to 14 major aspects of system activity.
* **Low Overhead:** The process of collecting data and storing results in a file requires very little system load.
* **Wide Scope:** Can report on file I/O, system calls, CPU efficiency, memory usage, process activity, inter-process communication (IPC), and more.

***

## Usage Modes

`sar` primarily supports two ways of viewing system data:

1.  **Tracing Past Data (Default):** It can retrieve historical data, typically starting from the beginning of the current day. Older reports are stored in log files under `/var/log/sysstat/` (e.g., `sa28`), which can be viewed using the `-f` option (e.g., `sar -f /var/log/sysstat/sa28`).
2.  **Periodically Viewing Current Data:** It can be used to monitor real-time system activity over a specified interval and count.

***

## Core Monitoring Metrics (Examples)

The tool uses specific options to display different categories of system statistics:

| Command | Metric | Description of Key Fields |
| :--- | :--- | :--- |
| `sar -u` | **CPU Utilization** | Shows `%user`, `%system`, `%iowait` (CPU idle waiting for I/O), and `%idle`. |
| `sar -q` | **Average Load** | Reports `runq-sz` (run queue length/waiting processes) and average loads (`ldavg-1`, `ldavg-5`, `ldavg-15`). |
| `sar -r` | **Memory Usage** | Displays `kbmemfree`, `kbmemused`, `%memused`, `kbbuffers`, and `kbcached`. |
| `sar -W` | **Paging/Swap Activity** | Monitors page-in (`pswpin/s`) and page-out (`pswpout/s`) rates, which are key indicators of memory shortages. |

***

## Diagnosing System Bottlenecks

`sar` reports are often combined to effectively pinpoint the cause of poor performance:

* **CPU Bottleneck:** Use `sar -u` and `sar -q`.
* **Memory Bottleneck:** Use `sar -B`, `sar -r`, and `sar -W`.
* **I/O Bottleneck:** Use `sar -b`, `sar -u`, and `sar -d`.

***

## Installation and Setup

The `sar` tool is part of the **`sysstat`** package.

1.  **Installation:** Install the package using a system package manager (e.g., `apt-get install sysstat` on Debian/Ubuntu systems).
2.  **Enabling Data Collection:** Edit the configuration file, typically located at `/etc/default/sysstat`, and set `ENABLED="true"`.
3.  **Starting the Service:** Start the performance data collection service (e.g., `/etc/init.d/sysstat start`).

***

## General Parameters

The tool offers many parameters to customize the report output, including:

* `-A`: Summarizes all available reports.
* `-b`: Reports I/O and buffer usage.
* `-d`: Reports disk usage.
* `-r`: Reports memory usage.
* `-u`: Reports CPU utilization.
* `-q`: Reports run queue and load average.
* `-W`: Reports system swap activity.
# Reference

https://linuxtools-rst.readthedocs.io/zh_CN/latest/tool/sar.html