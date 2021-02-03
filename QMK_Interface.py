'''

'''

import time
import logging
import os
import math

from enum import Enum
from typing import List, Dict, Union, Optional, SupportsBytes
from dataclasses import dataclass, field


os.add_dll_directory(os.path.dirname(os.path.abspath(__file__)))  # Add the path of the HIDAPI files to the DLL search dirs
import hid

log = logging.getLogger(__name__)


class QMKInterfaceException(Exception):
    pass


class CouldNotFindKeyboard(QMKInterfaceException):
    pass


class KeyboardDisconnected(QMKInterfaceException):
    pass


class CorruptResponse(QMKInterfaceException):
    pass


class UnknownCommand(QMKInterfaceException):
    pass


class DataPacketTooLarge(QMKInterfaceException):
    pass


# For testing purposes
class SystemMembers(Enum):
    switched_out = 0
    Fluttershy = 1
    Hibiki = 2
    Luna = 3


@dataclass
class HSV:
    Hue: int
    Sat: int
    Val: int


# The following dicts hold keyboard specific data.

lily58_kb_info = {
    'layer_names': [
        'QWERTY',     # 0
        "LOWER",      # 1
        "RAISE",      # 2
        "ADJUST",     # 3
        "GAME_WASD",  # 4
        "GAME_ESDF"   # 5
    ],
    "led_num": 12,
    "led_split": [6, 6]
}


navi10_kb_info = {
    'layer_names': [
        'Base',      # 0
        "Function",  # 1
        "Media",     # 2
        "RGB"        # 3
    ],
    "led_num": 10,
    "led_split": None
}


class Commands:
    Do_Nothing = 0  # Do Nothing

    # CMDs Sent From PC TO KB  (Start at 1)
    KB_Set_Fronter = 1            # Send the current fronter to the Keyboard
    KB_Set_All_RGB_LEDs = 2
    KB_Set_RGB_LEDs = 3
    KB_Activity_Ping = 4

    # CMDs Sent To PC  (Start at 120)
    PC_Raw_Debug_Msg = 120
    PC_Debug_Msg = 121
    PC_Switch_Fronter = 122       # Use PK API To switch fronters
    PC_Notify_Layer_Change = 123  # Notification from keyboard that the current active layer has changed
    PC_Activity_Ping = 124


class QMKKeyboard:
    LILY58 = "lily58"
    NAVI10 = "navi10"

    def __init__(self, keyboard_type, callbacks=None):
        self.keyboard_type = keyboard_type
        if keyboard_type == self.LILY58:
            # Lily58
            self.kb_info = lily58_kb_info
            self.vendor_id = 0x04D8
            self.product_id = 0xEB2D
            self.packet_size = 32

        elif keyboard_type == self.NAVI10:
            # Navi10
            self.kb_info = navi10_kb_info
            self.vendor_id = 0xFEED
            self.product_id = 0x0000
            self.packet_size = 32

        else:
            raise ValueError(f"{keyboard_type} is not yet supported!")

        # Default Usage Page & Usage values for the HID Endpoint of most QMK devices
        # These can be overridden in your keyboard's config.h in the keyboard's main directory by redefining the values:
        # #define RAW_USAGE_PAGE 0xFF60 and #define RAW_USAGE_ID 0x61.
        self.usage_page = 0xFF60
        self.usage = 0x61

        self.qmk: Optional[hid.Device] = None
        self.connected = False
        self.callbacks = callbacks or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.disconnect()

    def __eq__(self, other):
        if isinstance(other, QMKKeyboard):
            # Todo: Use unique ID incase we ever have multiple of the same keyboard connected.
            if self.vendor_id == other.vendor_id and self.product_id == other.product_id:
                return True
        return False

    def open(self):

        # get list of HID devices connected to this computer
        enumerated_devices = hid.enumerate()
        for hid_item in enumerated_devices:
            # print(f"Device Info: {hid_item}")
            if self.vendor_id == hid_item['vendor_id'] and self.product_id == hid_item['product_id']:
                if self.usage_page == hid_item['usage_page'] and self.usage == hid_item['usage']:
                    hid_path = hid_item['path']

                    if hid_path is not None:
                        self.qmk = hid.Device(path=hid_path)
                        self.connected = True
                        return

        self.connected = False
        # return self
        raise CouldNotFindKeyboard

    def connect(self):
        try:
            self.open()
            return True
        except CouldNotFindKeyboard:
            log.warning(f"Could not find {self.keyboard_type}.")
            return False

    def disconnect(self):
        self.connected = False
        self.qmk.close()

    def construct_command_packet(self, command_type: int, command_data: List[int]):
        """
        Constructs a command packet from the command type and command data

        :param command_type:
        :param command_data:
        :return: A fully constructed Data packet
        """

        data_packet = [0, command_type, len(command_data)]  # Report ID, Command Type, Data Length
        data_packet.extend(command_data)  # Payload Data

        return data_packet

    def send_command(self, command_type: int, command_data: Optional[List[int]]) -> int:
        """
        Sends a command to a connected QMK Device.

        Raises: KeyboardDisconnected, DataPacketTooLarge

        :param command_type:
        :param command_data:
        :return: The number of bytes sent.
        """

        if command_data is None:
            command_data = [0]

        data_packet = self.construct_command_packet(command_type, command_data)
        return self.write(data_packet)

    def write(self, data_to_write: List[int]) -> int:
        """
        Sends a properly formatted command packet to the keyboard.

        Raises: KeyboardDisconnected, DataPacketTooLarge
        :param data_to_write: The command packet that should be sent to the keyboard.
        :return:
        """

        if len(data_to_write) > self.packet_size:
            raise DataPacketTooLarge(f"Data packet len: {len(data_to_write)}")

        if self.qmk is not None:
            write_data_bytes = bytes(bytearray(data_to_write))

            try:
                num_bytes_writen = self.qmk.write(write_data_bytes)
                log.debug(f"Sending data to {self.keyboard_type}: {data_to_write}")
                return num_bytes_writen
            except hid.HIDException:
                self.connected = False
                raise KeyboardDisconnected("Could not write data because the Keyboard is disconnected")
        else:
            self.connected = False
            raise KeyboardDisconnected("Could not write data because the Keyboard is disconnected")

    def read(self, timeout: int = 100, length: int = 32) -> List[int]:
        """
        Read incoming data packet from the keyboard.

        Raises: KeyboardDisconnected
        :param timeout: Default: 100
        :param length: How many bytes to read. Default: 32
        :return: The data read.
        """
        if self.qmk is not None:
            try:
                data = self.qmk.read(length, timeout)
                ret_data = list(bytearray(data))
                return ret_data
            except hid.HIDException:
                self.connected = False
                raise KeyboardDisconnected("Could not read data because the Keyboard is disconnected")
        else:
            self.connected = False
            raise KeyboardDisconnected("Could not write data because the Keyboard is disconnected")

    def send_current_fronter(self, qmk_system_id: int):
        """
        Sends the current fronter to the connected QMK keyboard

        Raises: KeyboardDisconnected, DataPacketTooLarge
        :param qmk_system_id:
        :return:
        """
        log.info(f"Sending current fronter, {SystemMembers(qmk_system_id).name}, to {self.keyboard_type}.")
        self.send_command(Commands.KB_Set_Fronter, [qmk_system_id])
        # time.sleep(0.01)
        # _read_bytes = self.read()
        # self.parse_commands(_read_bytes)

    def send_activity_ping(self):
        """
        Sends an activity ping to the connected QMK keyboard

        Raises: KeyboardDisconnected, DataPacketTooLarge
        """
        log.info(f"Sending activity ping to {self.keyboard_type}.")
        self.send_command(Commands.KB_Activity_Ping, None)

    def set_RGB_LEDs(self, led_values: List[HSV], first_led = 0):
        """
        Sends the current fronter to the connected QMK keyboard

        Raises: KeyboardDisconnected, DataPacketTooLarge
        :param led_values: List of LED values. Each Led value HSV Class
        :return:
        """
        # log.info(f"Setting new RGB Values:")
        leds_per_command = math.floor((self.packet_size - 3) / 4)
        command_data = []
        for i, hsv_data in enumerate(led_values):
            if i >= leds_per_command:
                # Send off this set of LEDs
                # log.info(f"Sending part of new RGB Values from: {first_led} to {i}")
                self.send_command(Commands.KB_Set_RGB_LEDs, command_data)

                # recursively call set_RGB_LEDs() to send of the rest of the LEDs
                self.set_RGB_LEDs(led_values[i:], first_led+i)
                return

            data_piece = [first_led+i, hsv_data.Hue, hsv_data.Sat, hsv_data.Val]
            command_data.extend(data_piece)

        # log.info(f"Sending final part of new RGB Values from: {first_led} to {first_led + len(led_values)-1}")
        self.send_command(Commands.KB_Set_RGB_LEDs, command_data)

    def parse_commands(self) -> Optional[Dict]:
        """
        Parses incoming commands from the keyboard.
        :return:
        """

        """
        * Sent (KB -> PC) HID Data Packet Format:
        * Byte 0: The Command Type
        * Byte 1: Length of Command Data
        * Byte 2-31: Command Data 
        """
        try:
            received_data = self.read()
        except KeyboardDisconnected:
            return None  # No keyboard is connected

        if len(received_data) == 0:
            return None  # No data was received

        log.info(f"{self.keyboard_type} Received: {received_data}")

        if len(received_data) < 3:
            raise CorruptResponse  # Data packet will be >= to 3 bytes

        command_id = received_data[0]
        data_length = received_data[1]
        command_data = received_data[2:]

        if command_id == Commands.Do_Nothing:
            return None

        elif command_id == Commands.PC_Raw_Debug_Msg:
            log.info(f"Raw Debug MSG Received!!!")
            log.info(f"Packet Len: {len(received_data)}. Stated Data Len {data_length}.")
            log.info(f"Data:\n {command_data}")

        elif command_id == Commands.PC_Debug_Msg:
            log.info(f"Debug MSG Received!!!")
            log.info(f"Packet Len: {len(received_data)}. Stated Data Len {data_length}.")
            log.info(f"Message:\n {bytes(command_data).decode()}")

        elif command_id == Commands.PC_Switch_Fronter:
            new_fronter_qmk_id = command_data[0]
            log.info(f"Switch Fronter CMD! Switching fronter to {SystemMembers(new_fronter_qmk_id)}")
            command_info = {'command': command_id, 'data': new_fronter_qmk_id}

            if command_id in self.callbacks:
                self.callbacks[command_id](self, new_fronter_qmk_id)

            return command_info

        elif command_id == Commands.PC_Notify_Layer_Change:
            '''
            command_data length is dependent on the compiled layer state uint size.
            valid lengths are between 1 - 4 bytes long
            '''
            # if data_length != 4:
            #     raise CorruptResponse(f"Raw Data: {received_data}")

            command_data = command_data[:data_length]

            # Convert the split up uint8's back into their original data type
            layer_mask = int.from_bytes(command_data, byteorder='little', signed=False)

            log.debug(f"Layer Mask raw: {command_data}")
            log.info("Layer Mask bin: {0:b}".format(layer_mask))
            log.debug(f"Layer Mask int: {layer_mask}")

            if command_id in self.callbacks:
                self.callbacks[command_id](self, layer_mask)

            command_info = {'command': command_id, 'data': layer_mask}
            return command_info

        elif command_id == Commands.PC_Activity_Ping:
            log.info(f"Received Activity Ping from {self.keyboard_type}")
            command_info = {'command': command_id, 'data': None}

            if command_id in self.callbacks:
                self.callbacks[command_id](self)
            return command_info

        else:
            raise UnknownCommand(f"Raw Data: {received_data}")

    # def parse_commands_old(self, received_data):
    #     log.info(f"Received: {received_data}")
    #     command_bytes_remaining = 0
    #     # command_instruction = 0
    #     for i, packet_byte in enumerate(received_data):
    #         if command_bytes_remaining > 0:  # Skip this byte because it a data byte, not instruction
    #             command_bytes_remaining -= 1
    #             continue
    #         if i == 0:
    #             if packet_byte != 2:
    #                 raise CorruptResponse
    #             continue
    #         elif i > 0:  # New command to parse
    #             if command_bytes_remaining == 0:  # We have a command instruction or end of packet.
    #                 if packet_byte == 1:  # Switch Command
    #                     command_bytes_remaining = 1
    #                     new_fronter_qmk_id = received_data[i+1]
    #                     log.info(f"Switch Fronter CMD! Switching fronter to {new_fronter_qmk_id}")
    #                 if packet_byte == 251:
    #                     return
    #                     # print(f"End Of Packet")


def poll_for_new_commands(_keyboards: List):
    for i in range(20):
        for _keyboard in _keyboards:
            command_info = _keyboard.parse_commands()
            if command_info == Commands.PC_Switch_Fronter:
                time.sleep(.500)
                return  # Return early to refresh current fronter on keyboards early.
        time.sleep(.500)  # 20*.5 = 10 seconds


def test_fronter_functionality():

    # ------ Front Tests ------
    current = 0
    while 1:
        if not keyboard.connected:
            keyboard.connect()

        _current_fronter = SystemMembers(current)
        # _current_fronter = SystemMembers(SR.randint(0, len(SystemMembers)-1))
        log.info(f"Current Fronter: {_current_fronter}")

        try:
            keyboard.send_current_fronter(_current_fronter.value)
        except KeyboardDisconnected:
            log.info(f"{keyboard.keyboard_type} Disconnected")

        current += 1
        if current >= 4:
            current = 0

        time.sleep(3)


def test_LED_set_functionality():

    # ------ RGB Set Tests ------
    hsv_set_info = []
    next_hue = 0
    led_num = keyboard.kb_info['led_num']
    for i in range(led_num):  # range(keyboard.kb_info['led_num']):

        hsv_set_info.append(HSV(Hue=next_hue, Sat=255, Val=255))

        next_hue += 2
        if next_hue > 255:
            next_hue = 0

    if not keyboard.connected:
        keyboard.connect()

    try:
        keyboard.set_RGB_LEDs(hsv_set_info, first_led=0)
    except KeyboardDisconnected:
        log.info(f"{keyboard.keyboard_type} Disconnected")

    while 1:
        poll_for_new_commands([keyboard])


def test_LED_set_functionality_two():

    # ------ RGB Set Tests ------
    next_hue = 0
    led_num = keyboard.kb_info['led_num']
    for i in range(led_num):  # range(keyboard.kb_info['led_num']):

        try:
            keyboard.set_RGB_LEDs([HSV(Hue=next_hue, Sat=255, Val=255)], first_led=i)
        except KeyboardDisconnected:
            log.info(f"{keyboard.keyboard_type} Disconnected")

        next_hue += 30
        if next_hue > 255:
            next_hue = 0

        if not keyboard.connected:
            keyboard.connect()

        # poll_for_new_commands([keyboard])
        time.sleep(1.5)


    print("Nyaaaaaa!!!!!")
    while 1:
        poll_for_new_commands([keyboard])


def chasing_rainbow_leds(start_hue = 0):

    # ------ chasing rainbow leds ------
    num_of_leds = keyboard.kb_info['led_num']
    hsv_set_info = []
    count = 0
    next_starting_hue = start_hue

    while 1:
        next_hue = next_starting_hue
        hsv_set_info.clear()
        if not keyboard.connected:
            keyboard.connect()

        for i in range(num_of_leds):  # range(keyboard.kb_info['led_num']):

            hsv_set_info.append(HSV(Hue=next_hue, Sat=255, Val=255))

            next_hue += 10
            next_hue = overflow_int8(next_hue)
            # if next_hue > 255:
            #     next_hue = 0

        try:
            # print(hsv_set_info)
            keyboard.set_RGB_LEDs(hsv_set_info, first_led=0)
        except KeyboardDisconnected:
            log.info(f"{keyboard.keyboard_type} Disconnected")

        command_info = keyboard.parse_commands()
        next_starting_hue += 10
        next_starting_hue = overflow_int8(next_starting_hue)
        # if next_starting_hue > 255:
        #     next_starting_hue = 0

        time.sleep(0.005)  #0.0166666667

        # if count % 10:
            # poll_for_new_commands([keyboard])


def overflow_int8(uint8):
    if uint8 > 255:
        return uint8-255
    return uint8


if __name__ == '__main__':

    from random import SystemRandom
    SR = SystemRandom()

    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")

    keyboard = QMKKeyboard(QMKKeyboard.LILY58)
    # keyboard = QMKKeyboard(QMKKeyboard.NAVI10)

    if not keyboard.connected:
        keyboard.connect()

    log.info(f'Device manufacturer: {keyboard.qmk.manufacturer}')
    log.info(f'Product: {keyboard.qmk.product}')


    # test_LED_set_functionality()
    # test_fronter_functionality()
    # test_LED_set_functionality_two()

    chasing_rainbow_leds()

    print("Nyaaaaaa!!!!!")


