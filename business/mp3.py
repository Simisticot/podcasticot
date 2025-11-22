import logging
import math

import requests

logger = logging.getLogger(__name__)

MP3_BITRATES_TABLE = [
    0,
    32,
    40,
    48,
    56,
    64,
    80,
    96,
    112,
    128,
    160,
    192,
    224,
    256,
    320,
    0,
]


class UnexpectedBitrate(Exception): ...


class FirstFrameNotFound(Exception): ...


def guess_mp3_duration_in_seconds(url: str) -> int:
    response = requests.get(url, stream=True)
    response.raise_for_status()
    full_size = int(response.headers["Content-Length"])

    chunk_size = 100000
    # /!\ chunking this way can split the first frame in the wrong spot and lengthen our search
    for chunk_index, chunk in enumerate(response.iter_content(chunk_size=chunk_size)):
        for i in range(len(chunk) - 4):
            if chunk[i] == 0xFF and (chunk[i + 1] & 0xE0) == 0xE0:
                # /!\ could be at the edge of our chunk here
                frame_chunk = chunk[i : i + 200]
                if b"Xing" in frame_chunk or b"VBRI" in frame_chunk:
                    logger.info("This is probably VBR")

                read_before_first_frame = i + (chunk_index * chunk_size)
                bitrate_index = chunk[i + 2] >> 4
                # not 0-15 because we don't want zeros
                if not 1 <= bitrate_index <= 14:
                    raise UnexpectedBitrate()
                bitrate_kbps = MP3_BITRATES_TABLE[bitrate_index]
                logger.info(f"episode is {bitrate_kbps} kbps")
                audio_bytes = full_size - read_before_first_frame
                bitrate_bps = bitrate_kbps * 1000
                bytes_per_sec = bitrate_bps / 8
                response.close()
                logger.info(f"Downloaded {read_before_first_frame} before first frame")
                return math.floor(audio_bytes / bytes_per_sec)

    response.close()
    raise FirstFrameNotFound()
