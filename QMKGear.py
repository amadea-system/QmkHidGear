"""

"""

import json
import time
import logging

from typing import List, Dict, Optional
from dataclasses import dataclass

from QMK_Interface import QMKKeyboard, KeyboardDisconnected, Commands
from utils.pluralKit import System, MembersAlreadyFronting
import utils.pluralKit as pk_lib  #TODO: Do This better

# https://stackoverflow.com/questions/56695061/is-there-any-way-to-disable-the-notification-sound-on-win10toast-python-library
from QuietWin10Toast import ToastNotifier


log = logging.getLogger(__name__)
toaster = ToastNotifier()

amadea_system_map: Optional['AmadeaSystemMap'] = None
keyboards = []


@dataclass
class SystemMemberMap:
    name: str
    pk_id: str
    qmk_id: int


class AmadeaSystemMap:

    def __init__(self, system_id: str, members: List[SystemMemberMap]):

        self.system_id = system_id
        self.members = members

    @staticmethod
    def from_config(_config: Dict):

        sys_mems = []
        for member in _config['system_members']:
            sys_mems.append(SystemMemberMap(**member))

        return AmadeaSystemMap(config['system_id'], sys_mems)

    def get_qmkid_by_pkid(self, pk_id:str):
        for member in self.members:
            if member.pk_id == pk_id:
                return member.qmk_id
        raise KeyError

    def get_pkid_by_qmkid(self, qmk_id:int):
        for member in self.members:
            if member.qmk_id == qmk_id:
                return member.pk_id
        raise KeyError

    def get_member_by_qmkid(self, qmk_id: int) -> Optional['SystemMemberMap']:
        for member in self.members:
            if member.qmk_id == qmk_id:
                return member
        return None


def handle_layer_change(qmk: QMKKeyboard, layer_state):

    # toaster.show_toast(f"{qmk.keyboard_type} Layer Change",
    #                    f"Layer #{layer_state}",
    #                    icon_path=None,
    #                    duration=3,
    #                    threaded=True)
    print(f"layer callback: {layer_state} from {qmk.keyboard_type}")


def handle_switch_fronter(qmk: QMKKeyboard, qmk_member_id):

    member = amadea_system_map.get_member_by_qmkid(qmk_member_id)

    try:
        status = pk_amadea.set_fronters([member.pk_id])
    except MembersAlreadyFronting:
        status = False
        toaster.show_toast(f"{member.name} was already in front!.",
                           f"{member.name} was already in front!",
                           icon_path=None,
                           duration=5,
                           threaded=True)

    if status:
        toaster.show_toast(f"{member.name} Has Switched In.",
                           f"Telling PK that {member.name} is now the current fronter!!!",
                           icon_path=None,
                           duration=5,
                           threaded=True)

        print(f"PK Switch callback: {qmk_member_id} from {qmk.keyboard_type}")
    else:
        print(f"Switch Failed!!!")


def handle_activity_ping(pinging_qmk: QMKKeyboard):
    """
    Sends a pong to all keyboards except the keyboard that sent the ping.
    Uses the global var 'Keyboards'
    """

    log.info(f"Activity ping callback: from {pinging_qmk.keyboard_type}")
    # TODO: Have this callback be part of a class that holds 'Keyboards' so we dont have to use a Global.

    # We got an activity ping from a device. Send pong to all other connected QMK devices.
    for _keyboard in keyboards:
        if _keyboard != pinging_qmk:
            try:
                _keyboard.send_activity_ping()
            except KeyboardDisconnected:
                pass


def send_current_fronter(_keyboards: List[QMKKeyboard]):
    """Sends the current fronter to all keyboards in passed _keyboards"""
    for _keyboard in _keyboards:
        try:
            _keyboard.send_current_fronter(fronters_qmk_id)
        except KeyboardDisconnected:
            pass


def poll_for_new_commands(_keyboards: List):
    for i in range(20):
        for _keyboard in _keyboards:
            command_info = _keyboard.parse_commands()
            if command_info == Commands.PC_Switch_Fronter:
                time.sleep(.500)
                return  # Return early to refresh current fronter on keyboards early.
        time.sleep(.500)  # 20*.5 = 10 seconds


def poll_for_new_commands_fast(_keyboards: List):

    for _keyboard in _keyboards:
        command_info = _keyboard.parse_commands()
        if command_info == Commands.PC_Switch_Fronter:
            # time.sleep(.500)
            return  # Return early to refresh current fronter on keyboards early.


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")

    # load config file.
    with open('config.json') as json_data_file:
        config = json.load(json_data_file)

    pk_lib.pk_gateway_base_url = config['pk_gateway_url']  # TODO: Do This better

    amadea_system_map = AmadeaSystemMap.from_config(config)
    pk_amadea = System.get_by_hid(config['system_id'], config['pk_token'])

    command_callbacks = {
        Commands.PC_Notify_Layer_Change: handle_layer_change,
        Commands.PC_Switch_Fronter: handle_switch_fronter,
        Commands.PC_Activity_Ping: handle_activity_ping,
    }

    lily = QMKKeyboard(QMKKeyboard.LILY58, command_callbacks)
    navi = QMKKeyboard(QMKKeyboard.NAVI10, command_callbacks)

    keyboards.extend([lily, navi])

    log.info(f"QMKGear Started!")

    count = 0
    while 1:

        # try reconnecting to any keyboards that got disconnected
        for keyboard in keyboards:
            if not keyboard.connected:
                keyboard.connect()

        # get the current fronter from PK API
        try:
            amadea_front = pk_amadea.cached_fronters()
        except Exception as e:
            log.info(e)
            time.sleep(5)
            continue

        if len(amadea_front.members) > 0:
            fronters_qmk_id = amadea_system_map.get_qmkid_by_pkid(amadea_front.members[0].hid)
            # log.info(f"Sending {amadea_front.members[0].name} as the current fronter.")
        else:
            # No one is in front
            fronters_qmk_id = 0
            # log.info(f"Sending Switched Out as the current fronter.")

        # --- Send New Data To Connected Keyboards --
        send_current_fronter(keyboards)

        # -- Check for new incoming commands packets --
        poll_for_new_commands_fast(keyboards)
        time.sleep(0.5)




