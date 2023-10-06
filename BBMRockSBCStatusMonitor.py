#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Dependencies:
#   pip3 install psutil
#   pip3 install uptime
#
# Serial port needs to be released from console after boot
#   cd /etc/systemd/system
#   systemctl mask serial-getty@ttyS0.service
#   sync
#   reboot

import time
import sys
import psutil
import socket
import platform
import re
import uuid
import fcntl
import struct
import serial
import os


# 'serialcontrol' is a custom controller library designed to control a custom Mates Studio - Genius Project
# Normally, using Architect or Commander is recommended, however at the time of writing RockPi can't be
# configured to disable Serial console during boot and hence projects made using Architect and Commander
# environments, replies with errors preventing the RockPi to boot completely.
from serialcontrol import ROCKSBCBBMController

# Get the name of the current Wi-Fi connection.
def getSSID():
    ipaddress = os.popen("ifconfig wlan0 \
                     | grep 'inet addr' \
                     | awk -F: '{print $2}' \
                     | awk '{print $1}'").read()
    ssid = os.popen("iwconfig wlan0 \
                | grep 'ESSID' \
                | awk '{print $4}' \
                | awk -F\\\" '{print $2}'").read()
    return ssid

# Collect data specific to RockPi platform and HDD data and write it to the display
def getSystemInfo():
    BBM.sendCommandString(33, "Total number of Cores: " + str(psutil.cpu_count(logical=True),))
    BBM.sendCommandString(34, platform.release())
    BBM.sendCommandString(35, str(platform.version()))
    BBM.sendCommandString(32, str(platform.machine()))
    BBM.sendCommandString(36, "Total RAM: "+ str(round(psutil.virtual_memory().total / (1024.0 **3)))+" GB")
    hdd = psutil.disk_usage('/')
    BBM.sendCommandString(37, "Total HDD Capacity: %d GB" % (hdd.total / (2**30)))

# Collect data specific to the current network connection and write it to the display
def getNetworkInfo():
    BBM.sendCommandString(48, getSSID())
    BBM.sendCommandString(49, socket.gethostname())
    BBM.sendCommandString(50, get_interface_ipaddress('wlan0'))
    BBM.sendCommandString(51, ':'.join(re.findall('..', '%012x' % uuid.getnode())))
    iostat = psutil.net_io_counters(pernic=False)
    BBM.sendCommandString(52, str(iostat[1]) + " bytes")
    BBM.sendCommandString(53, str(iostat[0]) + " bytes")

# Calculate time elapsed since boot and output it as string
def up():
    t = int(time.clock_gettime(time.CLOCK_BOOTTIME))
    days = 0
    hours = 0
    min = 0
    out = ''
    days = int(t / 86400)
    t = t - (days * 86400)
    hours = int(t / 3600)
    t = t - (hours * 3600)
    min = int(t / 60)
    out += str(days) + 'd '
    out += str(hours) + 'h '
    out += str(min) + 'm'
    return out

# Get IP address when connected, otherwise returns 0.0.0.0
def get_interface_ipaddress(network):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        return socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915,
                                struct.pack('256s',
                                network[:14].encode('utf-8')))[20:24])  # SIOCGIFADDR
    except OSError:
        return '0.0.0.0'

# Get the current temperature of selected sensor, either cpu ("cpu_thermal") or gpu ("gpu_thermal")
def get_temp(sensor: str):
    cpu_temp = psutil.sensors_temperatures()
    cpu_temp = psutil.sensors_temperatures()[sensor]
    cpu_temp = psutil.sensors_temperatures()[sensor][0]
    return int(cpu_temp.current)

# Calculate the increment value (used for smooth ramping of gauges)
def increment(val1: int, val2: int):
    respi = 1
    respi = val2 - val1
    if abs(respi) < 10:
        if respi > 0:
            respi = 1
        else:
            respi = -1
    else:
        respi = respi / 10
    return int(respi)

# Calculate the used percentage of the HDD
def get_hdd():
    hdd = psutil.disk_partitions(0)
    drive = psutil.disk_usage('/')
    percent = drive.percent
    return percent

if __name__ == '__main__':

    BBM = ROCKSBCBBMController()
    BBM.begin(115200)

    gtime = up()
    lastCpuUse = 0
    lastTemp = 0
    lastTempG = 0
    lastlTemp = 0
    lastlTempG = 0
    lastRamUse = 0
    lastHDD = 0
    lastWIPaddr = '0.0.0.0'
    lastEIPaddr = '0.0.0.0'
    lastPage = 0
    currPage = 0
    lastbytesRX = 0
    lastbytesTX = 0

    BBM.sendCommandReset()
    BBM.sendCommandString(22, gtime)
    
    lcpu = int(get_temp("cpu_thermal") * 10)
    lgpu = int(get_temp("gpu_thermal") * 10)

    IPinterval = 0
    
    getSystemInfo()
    getNetworkInfo()
    
    while True:
        reccommand = BBM.getCommand() 
        if reccommand == 200:
            BBM.sendCommandReset()
            tempTime = up()
            BBM.sendCommandString(22, tempTime)
            BBM.sendCommand(20, lastRamUse)
            BBM.sendCommand(18, lastlTemp)
            BBM.sendCommandString(24, lastEIPaddr)
            BBM.sendCommandString(23, lastWIPaddr)
            getSystemInfo()
            getNetworkInfo()
            currPage = 1
        
        if reccommand > 200:
            currPage = reccommand - 201
            
        lcpu = int(get_temp("cpu_thermal") * 10)
        lgpu = int(get_temp("gpu_thermal") * 10)
        
        cpuuse = int(psutil.cpu_percent())
        ramuse = int(psutil.virtual_memory().percent)
        hdd = get_hdd()

        if currPage == 8:
            iostat = psutil.net_io_counters(pernic=False)
            if lastbytesRX != iostat[1]:
                lastbytesRX = iostat[1]
                BBM.sendCommandString(52, str(iostat[1]) + " bytes")
            if lastbytesTX != iostat[0]:
                lastbytesTX = iostat[0]
                BBM.sendCommandString(53, str(iostat[0]) + " bytes")
        
        if cpuuse != lastCpuUse:
            lastCpuUse = lastCpuUse - increment(cpuuse, lastCpuUse)
            BBM.sendCommand(17, lastCpuUse)
    
        if lcpu != lastlTemp:
            lastlTemp = lastlTemp - increment(lcpu, lastlTemp)
            BBM.sendCommand(18, lastlTemp)
        
        if lgpu != lastlTempG:
            lastlTempG = lastlTempG - increment(lgpu, lastlTempG)
            BBM.sendCommand(19, lastlTempG)
        
        if ramuse != lastRamUse:
            lastRamUse = lastRamUse - increment(ramuse, lastRamUse)
            BBM.sendCommand(20, lastRamUse)
        
        if hdd != lastHDD:
            lastHDD = lastHDD - increment(hdd, lastHDD)
            BBM.sendCommand(21, lastHDD)

        if IPinterval > 20:
            tempIPaddr = get_interface_ipaddress('eth0')
            if tempIPaddr != lastEIPaddr:
                BBM.sendCommandString(24, tempEIPaddr)
                lastEIPaddr = tempIPaddr
            tempIPaddr = get_interface_ipaddress('wlan0')
            if tempIPaddr != lastWIPaddr:
                BBM.sendCommandString(23, tempIPaddr)
                lastWIPaddr = tempIPaddr
                getNetworkInfo()
            IPinterval = 0

        IPinterval = IPinterval + 1
        time.sleep(0.060)

        tempTime = up()
        if tempTime != gtime:
            BBM.sendCommandString(22, gtime)
            gtime = tempTime
        refresh = 0
        time.sleep(0.040)
