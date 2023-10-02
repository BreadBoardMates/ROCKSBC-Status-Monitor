import serial

# This is custom controller library designed to control a custom Mates Studio - Genius Project
# Normally, using Architect or Commander is recommended, however at the time of writing Rock SBC
# can't be configured to disable Serial console during boot and hence projects made using
# Architect and Commander environments, replies with errors preventing the Rock SBC to boot
# completely.

class RockSBCBBMController:

    def __init__(self):
        self.serial_port = serial.Serial()
        self.serial_port.port = '/dev/ttyS2'
        self.serial_port.bytesize = serial.EIGHTBITS
        self.serial_port.parity = serial.PARITY_NONE
        self.serial_port.stopbits = serial.STOPBITS_ONE
        self.serial_port.timeout = 500/1000
        self.serial_port.xonxoff = False
        self.serial_port.rtscts = False
        self.serial_port.dsrdtr = False
        self.serial_port.write_timeout = None
        self.serial_port.inter_byte_timeout = None

    def begin(self, baudrate: int):
        self.serial_port.baudrate = baudrate
        self.serial_port.open()
        
    def sendCommandString(self, messageType: int, textFormat: str):
        messageLength = len(textFormat) + 1
        chksum = messageType + (messageLength >> 8) + (messageLength & 255)
        self.__write_int16(messageType + ((chksum & 255) << 8))
        self.__write_int16(messageLength)
        text_string = textFormat
        self.__write_string(text_string)
        self.__write_int8(0)
        
    def sendCommandReset(self):
        text_string = "BBMRockSBCSTART"
        self.__write_string(text_string)
        self.__write_int8(0)
        self.__write_int8(0)
        self.__write_int8(0)
        self.__write_int8(0)
        self.__write_int8(0)
        self.__write_int8(0)
        
    def sendCommand(self, messageType: int, messageVal: int):
        chksum = messageType + (messageVal >> 8) + (messageVal & 255)
        self.__write_int16(messageType + ((chksum & 255) << 8))
        self.__write_int16(messageVal)
        
    def getCommand(self):
        if self.serial_port.inWaiting():
            command = self.serial_port.read(1)
            commandval = int.from_bytes(command, 'little')
            return commandval
        else:
            return -1

    def __write_int8(self, int8_value: int):
        self.__write_bytes(int8_value.to_bytes(1, 'little'))

    def __write_int16(self, word: int):
        self.__write_bytes(word.to_bytes(2, 'little', signed=False))
        
    def __write_string(self, string: str):
        self.__write_bytes(bytes(string, 'utf-8'))
        
    def __write_bytes(self, bytes_to_write: bytes):
        self.serial_port.write(bytes_to_write)
