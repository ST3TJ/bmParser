"""
version: 1.1.2
time spent: 4 hrs 31 mins

TODO:
@ Improve resolver
@ Add image dumps ( 00 FF FF, etc.)

@ Add auto mode generation
@ Refactore code
@ Make filters more flexible
"""

import re
import os
from enum import Enum
from libs.CMode import Mode


class InputFileType(Enum):
    DUMP = "dump"  # .txt file with hex data
    IMAGE = "image"  # .bmp file
    INVALID = "invalid"  # invalid file type


class FilterType(Enum):
    MAJORITY_ONES = "1 prevails"
    MAJORITY_ZEROS = "0 prevails"
    UNIFORM = "Uniform"


# комментарии не выравниваются, слава великому RUFF
SETTINGS = {
    # I/O settings
    "path": "dumps/dump4.txt",  # Path to input file
    "generate_file": False,  # Generate output file from dump or not
    "output_file": "output.bmp",  # Output file name
    # Analysis settings
    "type": None,
    "filter": [  # Filters to apply
        FilterType.MAJORITY_ZEROS,
    ],
}

# LSB modes
CONFIGS = [
    Mode(),
    Mode(0b1, ignore_padding=True),
    Mode(0b11, ignore_padding=True),
    Mode(0b11),
    Mode(0b11111111, only_padding=True),
]


class MessageResolver:
    def __init__(self, lsb: list[int]):
        if isinstance(lsb, list):
            self.lsb = "".join(str(b) for b in lsb)
        else:
            self.lsb = lsb

    def _chunks(self, size: int = 8):
        return [self.lsb[i : i + size] for i in range(0, len(self.lsb), size)]

    def _ASCII(self) -> tuple[str, str]:
        try:
            chunks = self._chunks()
            bytes_list = [int(chunk, 2) for chunk in chunks]
            try:
                return bytes(bytes_list).decode("utf-8"), "utf-8"
            except UnicodeDecodeError:
                return bytes(bytes_list).decode("cp1251", errors="ignore"), "cp1251"
        except ValueError:
            return "", "ascii"

    def _straight(self) -> tuple[str, str]:
        try:
            chunks = self._chunks()
            char_list = [chr(int(chunk, 2)) for chunk in chunks]
            return "".join(char_list), "ascii"
        except ValueError:
            return "", "ascii"

    def resolve(self) -> tuple[str, str]:
        if len(self.lsb) % 8 == 0:
            return self._ASCII()
        else:
            return self._straight()


# Refactore this in future
def get_file_type(path: str) -> InputFileType:
    if path.endswith(".txt"):
        return InputFileType.DUMP
    elif path.endswith(".bmp"):
        return InputFileType.IMAGE
    else:
        return InputFileType.INVALID


def parse_dump_data(dump: str) -> list[str]:
    return re.findall(r"[0-9A-Fa-f]{2}", dump)


def little_endian(data: list[str]) -> int:
    return int("".join(data[::-1]), 16)


def concat(data: list[str]) -> str:
    return "".join(chr(int(x, 16)) for x in data)


def find_file(path):
    for root, _, files in os.walk(os.getcwd()):
        for file in files:
            if path in file:
                return os.path.join(root, file)
    return ""


def load_file(path: str, mode: str) -> list[str]:
    if not os.path.exists(path):
        valid_path = find_file(path)
        if not valid_path:
            raise FileNotFoundError(f"File {path} not found")
        return load_file(valid_path, mode)
    else:
        with open(path, mode) as f:
            return f.read()


def save_file(path: str, data: str) -> None:
    try:
        with open(path, "wb") as f:
            bytes_data = bytes.fromhex("".join(data))
            f.write(bytes_data)
    except FileNotFoundError:
        print(f"File {path} not found")
    except Exception as e:
        print(f"Failed to save file {path}: {e}")


# Шайтан функция с шайтан математикой
def LSB(pixel_data: list[str], width: int, height: int, bpp: int, mode: Mode):
    bytes_per_pixel = bpp // 8
    row_bytes = ((bytes_per_pixel * width + 3) // 4) * 4
    actual_row_bytes = width * bytes_per_pixel
    result = []

    for y in range(height):
        row_start = y * row_bytes
        row_end = row_start + row_bytes
        row = pixel_data[row_start:row_end]

        if mode.only_padding:
            row_to_process = row[actual_row_bytes:]
        elif mode.ignore_padding:
            row_to_process = row[:actual_row_bytes]
        else:
            row_to_process = row

        for byte_hex in row_to_process:
            byte_value = int(byte_hex, 16)
            masked_value = byte_value & mode.mask
            for b in range(7, -1, -1):
                if mode.mask & (1 << b):
                    bit = (masked_value >> b) & 1
                    result.append(bit)

    return result


def analyze(lsb: list[int], mode: Mode) -> str:
    if not lsb:
        return "LSB пустой"

    ones = sum(lsb)
    zeros = len(lsb) - ones
    ones_ratio = ones / len(lsb)
    analyze_result = (
        FilterType.UNIFORM.value
        if 0.45 <= ones_ratio <= 0.55
        else FilterType.MAJORITY_ONES.value
        if ones_ratio > 0.55
        else FilterType.MAJORITY_ZEROS.value
    )

    for filter_type in SETTINGS["filter"]:
        if analyze_result == filter_type.value:
            return ""

    res = [
        f"Mode: {mode}",
        f"total: {len(lsb)} | 1: {ones} | 0: {zeros}",
        analyze_result,
    ]

    msg, encoding = MessageResolver(lsb).resolve()
    res.append(f"Message ({encoding}): {msg}" if msg else "No message")

    return "\n".join(res)


def process_dump_data(data: list[str]) -> None:
    signature = concat(data[0:2])
    file_size = little_endian(data[2:6])
    dib_header_size = little_endian(data[14:18])
    width = little_endian(data[18:22])
    height = little_endian(data[22:26])
    bpp = little_endian(data[28:30])

    if signature != "BM":
        raise ValueError("Invalid signature")
    if file_size != len(data):
        raise ValueError("Invalid file size")
    if dib_header_size not in (40, 108, 124):
        raise ValueError("Unsupported DIB header size")
    if width <= 0 or height <= 0:
        raise ValueError("Invalid image dimensions")
    if bpp not in (1, 4, 8, 16, 24, 32):
        raise ValueError("Unsupported bits per pixel")

    pixel_offset = little_endian(data[10:14])

    for mode in CONFIGS:
        lsb = LSB(data[pixel_offset:], width, height, bpp, mode)
        result = analyze(lsb, mode)
        if result:
            print(result, end="\n\n")


class Handle:
    @staticmethod
    def init():
        if not SETTINGS["path"]:
            print("Path to input file is not specified")
            exit(1)

        file_type = get_file_type(SETTINGS["path"])
        if file_type == InputFileType.INVALID:
            print(f"Invalid file type: {SETTINGS['path']}")
            exit(1)

        SETTINGS["type"] = file_type

    @staticmethod
    def dump(hex_string: list[str] = None):
        if not hex_string:
            data = load_file(SETTINGS["path"], "r")
            hex_string = parse_dump_data(data)

        process_dump_data(hex_string)

        if not SETTINGS["generate_file"]:
            return

        save_file(SETTINGS["output_file"], hex_string)

    @staticmethod
    def image():
        file_path = SETTINGS["path"]
        binary_data = load_file(file_path, "rb")
        hex_string = binary_data.hex(" ").split(" ")

        Handle.dump(hex_string)


def main():
    Handle.init()
    getattr(Handle, SETTINGS["type"].value)()


if __name__ == "__main__":
    main()
