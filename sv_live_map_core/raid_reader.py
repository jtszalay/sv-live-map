"""Subclass of NXReader with functions specifically for raids"""

import contextlib
import socket
import io
import struct
from typing import Type
import bytechomp
from PIL import Image
from sv_live_map_core.nxreader import NXReader
from sv_live_map_core.sv_enums import StarLevel, StoryProgress, Game
from sv_live_map_core.raid_enemy_table_array import RaidEnemyTableArray
from sv_live_map_core.delivery_raid_priority_array import DeliveryRaidPriorityArray
from sv_live_map_core.raid_block import RaidBlock, process_raid_block
from sv_live_map_core.rng import SCXorshift32

class RaidReader(NXReader):
    """Subclass of NXReader with functions specifically for raids"""
    RAID_BINARY_SIZES = (0x3128, 0x3058, 0x4400, 0x5A78, 0x6690, 0x4FB0)
    RAID_PRIORITY_PTR = ("[[[[main+43A7798]+08]+2C0]+10]+88", 0x58)
    # https://github.com/Manu098vm/SVResearches/blob/master/RAM%20Pointers/RAM%20Pointers.txt
    RAID_BLOCK_PTR = ("[[main+43A77C8]+160]+40", 0xC98) # ty skylink!
    SAVE_BLOCK_PTR = "[[[main+4385F30]+80]+8]"
    DIFFICULTY_FLAG_LOCATIONS = (0x2BF20, 0x1F400, 0x1B640, 0x13EC0)

    def __init__(
        self,
        ip_address: str = None,
        port: int = 6000,
        usb_connection: bool = False,
        read_safety: bool = False,
        raid_enemy_table_arrays: tuple[RaidEnemyTableArray, 7] = None,
    ):
        super().__init__(ip_address, port, usb_connection)
        self.read_safety = read_safety
        self.raid_enemy_table_arrays: tuple[RaidEnemyTableArray, 7] = \
            raid_enemy_table_arrays or self.read_raid_enemy_table_arrays()
        # TODO: cache
        self.delivery_raid_priority: tuple[int] = self.read_delivery_raid_priority()
        self.story_progress: StoryProgress = self.read_story_progess()
        self.game_version: Game = self.read_game_version()

    def read_delivery_raid_priority(self) -> tuple[int]:
        """Read the delivery priority flatbuffer from memory"""
        delivery_raid_priority_array = DeliveryRaidPriorityArray(
            self.read_pointer(*self.RAID_PRIORITY_PTR)
        )
        if len(delivery_raid_priority_array.delivery_raid_prioritys) == 0:
            return (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        return delivery_raid_priority_array \
            .delivery_raid_prioritys[0] \
            .delivery_group_id \
            .group_counts

    @staticmethod
    def raid_binary_ptr(star_level: StarLevel) -> tuple[str, int]:
        """Get a pointer to the raid flatbuffer binary in memory"""
        if star_level == StarLevel.EVENT:
            return ("[[[[[[main+4384A50]+30]+288]+290]+280]+28]+414", 0x7530)
        return (
            # TODO: find a more stable pointer for scarlet and violet
            f"[[[[[[[[main+43A78D8]+C0]+E8]]+10]+4A8]+{0xD0 + star_level * 0xB0:X}]+1E8]",
            RaidReader.RAID_BINARY_SIZES[star_level]
        )

    def read_story_progess(self) -> StoryProgress:
        """Read and decrypt story progress from save blocks"""
        # each key remains constant and SCXorshift32(difficulty_{n}_key).next() can be precomputed
        # for the sake of showing how to decrypt it this is not done
        progress = StoryProgress.SIX_STAR_UNLOCKED
        for offset in reversed(self.DIFFICULTY_FLAG_LOCATIONS):
            if self.read_save_block_bool(offset):
                return progress
            progress -= 1
        return StoryProgress.DEFAULT

    @staticmethod
    def _decrypt_save_block(key: int, block: bytearray) -> bytearray:
        rng = SCXorshift32(key)
        for i, byte in enumerate(block):
            block[i] = byte ^ rng.next()
        return block

    def read_save_block_struct(self, offset: int, struct: Type):
        """Read decrypted save block of bytechomp struct at offset"""
        reader = bytechomp.Reader[struct](bytechomp.ByteOrder.LITTLE).allocate()
        reader.feed(self.read_save_block(offset, reader.__struct.size))
        assert reader.is_complete(), "Invalid data size"
        return reader.build()

    def read_save_block_int(self, offset: int) -> int:
        """Read decrypted save block u32 at offset"""
        return int.from_bytes(self.read_save_block(offset, 5)[1:], 'little')

    def read_save_block_bool(self, offset: int) -> int:
        """Read decrypted save block boolean at offset"""
        return int.from_bytes(self.read_save_block(offset, 1), 'little') == 2

    def read_save_block(self, offset: int, size: int) -> bytearray:
        """Read decrypted save block at offset"""
        key = self.read_pointer_int(f"{self.SAVE_BLOCK_PTR}+{offset:X}", 4)
        block = bytearray(self.read_pointer(f"[{self.SAVE_BLOCK_PTR}+{offset + 8:X}]", size))
        return self._decrypt_save_block(key, block)

    def read_save_block_object(self, offset: int) -> bytearray:
        """Read decrypted save block object at offset"""
        key = self.read_pointer_int(f"{self.SAVE_BLOCK_PTR}+{offset:X}", 4)
        header = bytearray(self.read_pointer(f"[{self.SAVE_BLOCK_PTR}+{offset + 8:X}]", 5))
        header = self._decrypt_save_block(key, header)
        # discard type byte
        size = int.from_bytes(header[1:], 'little')
        full_object = bytearray(
            self.read_pointer(
                f"[{self.SAVE_BLOCK_PTR}+{offset + 8:X}]",
                5 + size
            )
        )
        # discard type and size bytes
        return self._decrypt_save_block(key, full_object)[5:]

    def read_trainer_icon(self) -> Image:
        """Read trainer icon as PIL image"""
        # thanks NPO! https://github.com/NPO-197
        def build_dxt1_header(width, height):
            """Build DXT1 header"""
            return b'\x44\x44\x53\x20\x7C\x00\x00\x00\x07\x10\x08\x00' \
                + struct.pack("<II", height, width) \
                + b'\x00\x7E\x09\x00\x00\x00\x00\x00\x01\x00\x00\x00' \
                b'\x49\x4D\x41\x47\x45\x4D\x41\x47\x49\x43\x4B\x00' \
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x20\x00\x00\x00' \
                b'\x04\x00\x00\x00\x44\x58\x54\x31\x00\x00\x00\x00' \
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
                b'\x00\x00\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00' \
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        return Image.open(
            io.BytesIO(
                build_dxt1_header(
                    self.read_save_block_int(0x1a3c0),
                    self.read_save_block_int(0x1da0)
                ) + self.read_save_block_object(0x273e0)
            )
        )

    def read_game_version(self) -> Game:
        """Read game version"""
        return Game.from_game_id(self.read_main_int(0x4385FD0, 4))

    def read_raid_enemy_table_arrays(self) -> tuple[RaidEnemyTableArray, 7]:
        """Read all raid flatbuffer binaries from memory"""
        return (
            RaidEnemyTableArray(
                self.read_pointer(*self.raid_binary_ptr(StarLevel.ONE_STAR))
            ),
            RaidEnemyTableArray(
                self.read_pointer(*self.raid_binary_ptr(StarLevel.TWO_STAR))
            ),
            RaidEnemyTableArray(
                self.read_pointer(*self.raid_binary_ptr(StarLevel.THREE_STAR))
            ),
            RaidEnemyTableArray(
                self.read_pointer(*self.raid_binary_ptr(StarLevel.FOUR_STAR))
            ),
            RaidEnemyTableArray(
                self.read_pointer(*self.raid_binary_ptr(StarLevel.FIVE_STAR))
            ),
            RaidEnemyTableArray(
                self.read_pointer(*self.raid_binary_ptr(StarLevel.SIX_STAR))
            ),
            RaidEnemyTableArray(
                self.read_pointer(*self.raid_binary_ptr(StarLevel.EVENT))
            ),
        )

    def read_raid_block_data(self) -> RaidBlock:
        """Read raid block data from memory and process"""
        raid_block = process_raid_block(self.read_pointer(*self.RAID_BLOCK_PTR))
        raid_block.initialize_data(
            self.raid_enemy_table_arrays,
            self.story_progress,
            self.game_version,
            self.delivery_raid_priority
        )
        return raid_block

    def check_if_data_avaiable(self):
        """Check if data is avaiable to be read from socket"""
        try:
            self.socket.recv(1, socket.MSG_PEEK)
            return True
        except TimeoutError:
            return False

    def clear_all_data(self):
        """Clear all data waiting to be read"""
        with contextlib.suppress(TimeoutError):
            while self.check_if_data_avaiable():
                self.socket.recv(0x8000)

    def read(self, address, size):
        if self.read_safety and not self.usb_connection:
            self.clear_all_data()
        return super().read(address, size)

    def read_absolute(self, address, size):
        if self.read_safety and not self.usb_connection:
            self.clear_all_data()
        return super().read_absolute(address, size)

    def read_main(self, address, size):
        if self.read_safety and not self.usb_connection:
            self.clear_all_data()
        return super().read_main(address, size)

    def read_pointer(self, pointer, size):
        if self.read_safety and not self.usb_connection:
            self.clear_all_data()
        return super().read_pointer(pointer, size)
