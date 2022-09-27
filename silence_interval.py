import pyaudio
import asyncio
import sys
import websockets
import json
import beepy
import shutil
import argparse

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 8000

terminal_size = shutil.get_terminal_size()

audio_queue = asyncio.Queue()

def callback(input_data, frame_count, time_info, status_flag):
    audio_queue.put_nowait(input_data)
    return (input_data, pyaudio.paContinue)

async def run(key, silence_interval):
    async with websockets.connect(
        'wss://api.deepgram.com/v1/listen?endpointing=true&interim_results=true&encoding=linear16&sample_rate=16000&channels=1',
        extra_headers={
            'Authorization': 'Token {}'.format(key)
        }
    ) as ws:
        async def microphone():
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format = FORMAT,
                channels = CHANNELS,
                rate = RATE,
                input = True,
                frames_per_buffer = CHUNK,
                stream_callback = callback
            )

            stream.start_stream()

            while stream.is_active():
                await asyncio.sleep(0.1)

            stream.stop_stream()
            stream.close()

        async def sender(ws):
            try:
                while True:
                    data = await audio_queue.get()
                    await ws.send(data)
            except Exception as e:
                print('Error while sending: '.format(str(e)))
                raise

        async def receiver(ws):
            transcript = ''
            last_word_end = 0.0
            should_beep = False

            async for message in ws:
                message = json.loads(message)

                transcript_cursor = message['start'] + message['duration']

                # if there are any words in the message
                if len(message['channel']['alternatives'][0]['words']) > 0:
                    # handle transcript printing for final messages
                    if message['is_final']:
                        if len(transcript):
                            transcript += ' '
                        transcript += message['channel']['alternatives'][0]['transcript']
                        print(transcript)
                        # overwrite the line regardless of length
                        # https://stackoverflow.com/a/47170056
                        print('\033[{}A'.format(len(transcript) // int(terminal_size.columns) + 1), end='')

                    # if the last word in a previous message is silence_interval seconds
                    # older than the first word in this message (and if that last word hasn't already triggered a beep)
                    current_word_begin = message['channel']['alternatives'][0]['words'][0]['start']
                    if current_word_begin - last_word_end >= silence_interval and last_word_end != 0.0:
                        should_beep = True

                    last_word_end = message['channel']['alternatives'][0]['words'][-1]['end']
                else:
                    # if there were no words in this message, check if the the last word
                    # in a previous message is silence_interval or more seconds older
                    # than the timestamp at the end of this message (if that last word hasn't already triggered a beep)
                    if transcript_cursor - last_word_end >= silence_interval and last_word_end != 0.0:
                        last_word_end = 0.0
                        should_beep = True

                if should_beep:
                    beepy.beep(sound=1)
                    should_beep = False
                    # we set/mark last_word_end to 0.0 to indicate that this last word has already triggered a beep
                    last_word_end = 0.0
                    transcript = ''
                    print('')

        await asyncio.wait([
            asyncio.ensure_future(microphone()),
            asyncio.ensure_future(sender(ws)),
            asyncio.ensure_future(receiver(ws))
        ])

def parse_args():
    """ Parses the command-line arguments.
    """
    parser = argparse.ArgumentParser(description='Submits data to the real-time streaming endpoint.')
    parser.add_argument('-k', '--key', required=True, help='YOUR_DEEPGRAM_API_KEY (authorization)')
    parser.add_argument('-s', '--silence', required=False, help='A float representing the number of seconds of silence to wait before playing a beep. Defaults to 2.0.', default=2.0)
    return parser.parse_args()

def main():
    args = parse_args()

    loop = asyncio.get_event_loop()
    asyncio.get_event_loop().run_until_complete(run(args.key, float(args.silence)))

if __name__ == '__main__':
    sys.exit(main() or 0)
