import pyaudio
import asyncio
import sys
import websockets
import time
import json
import argparse
import beepy

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 8000

audio_queue = asyncio.Queue()

def callback(input_data, frame_count, time_info, status_flag):
    audio_queue.put_nowait(input_data)
    return (input_data, pyaudio.paContinue)

async def run(key):
    clock_cursor = 0.
    audio_cursor = 0.
    transcript_cursor = 0.

    extra_headers={
        'Authorization': 'Token {}'.format('key')
    }
    try:
        async with websockets.connect('wss://api.deepgram.com/v1/listen'):
            print('success')
    except Exception as e:
        print(e.headers)


def parse_args():
    """ Parses the command-line arguments.
    """
    parser = argparse.ArgumentParser(description='Submits data to the real-time streaming endpoint.')
    parser.add_argument('-k', '--key', required=True, help='YOUR_DEEPGRAM_API_KEY (authorization)')
    return parser.parse_args()

def main():
    args = parse_args()

    asyncio.run(run(args.key))

if __name__ == '__main__':
    sys.exit(main() or 0)
