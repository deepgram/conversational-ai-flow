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
        'wss://api.deepgram.com/v1/listen?interim_results=true&encoding=linear16&sample_rate=16000&channels=1', 
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
                print(f'Error while sending: {str(e)}')
                raise

        async def receiver(ws):
            transcript = ''
            last_word_end = 0.0
            should_beep = False
            is_silence = False

            async for message in ws:
                print(is_silence)
                message = json.loads(message)

                transcript_cursor = message['start'] + message['duration']

                # if there are any words in the message, prepare to check
                # for a long enough silence
                if len(message['channel']['alternatives'][0]['words']) > 0:
                    is_silence = False
                    
                    # handle transcript printing for final messages
                    if message['is_final']:
                        if len(transcript):
                            transcript += ' '
                        transcript += message['channel']['alternatives'][0]['transcript']
                        print(transcript)
                        # overwrite the line regardless of length
                        # https://stackoverflow.com/a/47170056
                        print("\033[{}A".format(len(transcript) // int(terminal_size.columns) + 1), end='')


                    # if there is more than 1 word in the message, 
                    # look to see if there is a gap of silence_interval seconds 
                    # between any of the words
                    if len(message['channel']['alternatives'][0]['words']) > 1:
                        previous_word_end = message['channel']['alternatives'][0]['words'][0]['end']
                        
                        for word in message['channel']['alternatives'][0]['words']:
                            current_word_start = word['start']
                            if current_word_start - previous_word_end >= silence_interval:
                                should_beep = True

                            previous_word_end = word['end']

                    # if the last word in a previous message is silence_interval seconds
                    # older than the first word in this message
                    current_word_begin = message['channel']['alternatives'][0]['words'][0]['start']
                    if current_word_begin - last_word_end >= silence_interval and last_word_end != 0:
                        should_beep = True
                    
                    last_word_end = message['channel']['alternatives'][0]['words'][-1]['end']
                        
                # if there were no words in this message, check if the the last word
                # in a previous message is silence_interval or more seconds older 
                # than the timestamp at the end of this message
                elif transcript_cursor - last_word_end >= silence_interval and last_word_end != 0 and not is_silence:
                    last_word_end = 0
                    should_beep = True
                    is_silence = True

                if should_beep:
                    beepy.beep(sound=1)
                    should_beep = False
                    is_silence = True
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

    asyncio.run(run(args.key, float(args.silence)))

if __name__ == '__main__':
    sys.exit(main() or 0)
