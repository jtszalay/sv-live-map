from pathlib import Path
from io import BytesIO
from typing import TYPE_CHECKING
from threading import Thread

from ..nxreader.nxreader import SocketError
import struct
import binascii
import sys
from PIL import Image

if TYPE_CHECKING:
    from ..window.application import Application


class Autohost:

    def __init__(self, master):
        self.hosted_raids = 0
        self.log = ""
        self.raid_pokemon = ""
        self.extra_info = ""
        self.master = master
        self.automation_thread: Thread = None
        self.host_raid = False
        import pdb;pdb.set_trace

    def start_automation(self):
        self.host_raid = True
        self.automation_thread = Thread(
            target=self.start_bot,
        )
        self.automation_thread.start()

    def stop_automation(self):
        if self.automation_thread:
            self.host_raid = False
            self.automation_thread = None


    def start_bot(self):
        try:
            while self.host_raid:
                if self.master.reader:
                    current_raid_count = self.get_raid_count()
                    print(f"There are {current_raid_count} raids.")
                    self.master.reader.pause(1.5)
                    connected = self.connect()
                    if not self.host_raid or not connected:
                        break
                    self.setup_raid()
                    if not self.host_raid:
                        break
                    self.hosted_raids += 1
                    print(f"{self.hosted_raids = }")
                    self.raid_execution()
                    if not self.host_raid:
                        break
                    self.quit_game()
                    if not self.host_raid:
                        break
                    self.enter_game()
                else:
                    self.master.connection_error("Not connected to switch.")
                    self.host_raid = False
        except (TimeoutError, struct.error, binascii.Error, SocketError) as error:
            self.stop_automation()
            # self.send_webhook_log(f"Exception: <@{self.exception_ping_entry.get()}> ``{error}``")
            raise error
        self.host_raid = False
        sys.exit()


    def is_on_overworld(self):
        on_overworld = self.master.reader.read_pointer("[[[main+43A7848]+348]+10]+D8]+28", 1)
        return int.from_bytes(on_overworld) == 17

    def is_connected(self):
        connected = self.master.reader.read_pointer("[main+437E280]+30", 1)
        return int.from_bytes(connected) == 1

    def read_users(self):
        ...

    def get_raid_code(self):
        data = self.master.reader.read_pointer("[[[[[[main+437DEC0]+98]+00]+10]+30]+10]+1A9", 6)
        print(f"Raid Code: {data.decode()}")

    def get_raid_count(self):
        raid_block_data = self.master.reader.read_raid_block_data()
        return len(raid_block_data.raids)

    def screenshot(self):
        ...
        # screen = self.master.reader.pixel_peek()
        # print(f"{screen}")
        
        # image = Image.open(BytesIO(screen))
        # image.save(Path("raid.jpg"), "JPEG")

    # # IMAGE PROCESSING

    # def cropScreenshot():
    #     image = Image.open(Path("Autoraid.Windows/Core/image.jpg"))
    #     cropped = image.crop((180, 360, 650, 630))
    #     cropped.save(Path("Autoraid.Windows/Core/image.jpg"))

    def connect(self):
        print("Connecting online...")
        ready = False
        while ready is not True:
            self.master.reader.pause(1)
            ready = self.is_on_overworld()
        self.master.reader.pause(3)
        self.master.reader.click("X")
        self.master.reader.pause(5)
        self.master.reader.click("L")
        connected = False
        wait = 0
        while connected is not True:
            self.master.reader.pause(2)
            connected = self.is_connected()
            if wait > 30:
                return False
            wait += 2
        self.master.reader.pause(5)
        self.master.reader.click("A")
        self.master.reader.pause(0.2)
        self.master.reader.click("A")
        self.master.reader.pause(1.3)
        self.master.reader.click("B")
        self.master.reader.pause(0.2)
        self.master.reader.click("B")
        self.master.reader.pause(1.3)
        return True

    def setup_raid(self):
        print("Entering Raid")
        readyForRaid = False
        while readyForRaid is not True:
            self.master.reader.pause(0.5)
            self.master.reader.click("B")
            readyForRaid = self.is_connected() and self.is_on_overworld()
            self.master.reader.pause(2)
            self.master.reader.click("A")
            self.master.reader.pause(3)
            self.master.reader.click("A")
            self.master.reader.pause(2)
            self.master.reader.click("A")
            self.master.reader.pause(10)
            self.read_users()
            self.get_raid_code()
            self.screenshot()
            self.master.reader.pause(60)
            self.read_users()
            print("Starting Raid")
            self.master.reader.click("A")
            self.master.reader.pause(3)
            self.master.reader.click("A")
    
    def raid_execution(self):
        inRaid = True
        while inRaid:
            self.master.reader.click("A")
            self.master.reader.pause(0.2)
            self.master.reader.click("A")
            self.master.reader.pause(1.3)
            self.master.reader.click("A")
            self.master.reader.pause(0.2)
            self.master.reader.click("A")
            self.master.reader.pause(1.3)
            self.master.reader.click("A")
            self.master.reader.pause(0.2)
            self.master.reader.click("A")
            self.master.reader.pause(1.3)  # Mashing A-button
            self.master.reader.click("B")
            self.master.reader.pause(0.2)
            self.master.reader.click("B")
            self.master.reader.pause(1.3)
            self.master.reader.click("B")
            self.master.reader.pause(0.2)
            self.master.reader.click("B")
            self.master.reader.pause(1.3)
            self.master.reader.click("B")
            self.master.reader.pause(0.2)
            self.master.reader.click("B")  # Mashing B-button (in case the raid is lost it goes back to overworld)
            self.master.reader.pause(1.3)
            inRaid = not self.is_on_overworld()
            self.master.reader.pause(5)
        print("Raid Finished!")
        self.master.reader.pause(5)

    def quit_game(self):
        print("Quitting the game")
        self.master.reader.click("B")
        self.master.reader.pause(0.2)
        self.master.reader.click("HOME")
        self.master.reader.pause(0.8)
        self.master.reader.click("X")
        self.master.reader.pause(0.2)
        self.master.reader.click("X")
        self.master.reader.pause(0.4)
        self.master.reader.click("A")
        self.master.reader.pause(0.2)
        self.master.reader.click("A")
        self.master.reader.pause(3)

    def enter_game(self):
        print("Restarting the game")
        self.master.reader.click("A")
        self.master.reader.pause(0.2)
        self.master.reader.click("A")
        self.master.reader.pause(1.3)
        self.master.reader.click("A")
        self.master.reader.pause(0.2)
        self.master.reader.click("A")
        self.master.reader.pause(1.3)
        self.master.reader.pause(16)
        self.master.reader.click("A")
        self.master.reader.pause(1.3)
        self.master.reader.click("A")
        self.master.reader.pause(1.3)

