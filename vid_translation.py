import subprocess
from moviepy.editor import VideoFileClip
import requests
from openai import OpenAI
from environ import environ

env = environ.Env()
env.read_env()

openai_api_key = env("OPENAI_API_KEY")

base_path = "content/"

# your video url here
video_url = "https://ai-textract-bucket.s3.ap-south-1.amazonaws.com/temp_rehan/Grade3EnglishComprehensionHowToListenBetter%2B(Logo)_compressed.mp4"

video_path = f"{base_path}source.mp4"

def download_video(video_url, video_path):
    print("Downloading video")
    r = requests.get(video_url, stream=True)
    with open(video_path, "wb") as file:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                file.write(chunk)

    return video_path


def separate_audio_from_video(video_path):
    print("Separating audio from video")
    video = VideoFileClip(video_path)

    audio_path = f"{base_path}extracted_audio.mp3"
    video_without_audio_path = f"{base_path}video_without_audio.mp4"
    audio = video.audio
    audio.write_audiofile(audio_path)

    video_without_audio = video.without_audio()

    video_without_audio.write_videofile(video_without_audio_path)

    return audio_path, video_without_audio_path


def transcribe_audio(audio_path):
    print("Transcribing audio")

    client = OpenAI(api_key=openai_api_key)
    audio_file = open(audio_path, "rb")
    transcript = client.audio.transcriptions.create(
        file=audio_file,
        model="whisper-1",
        response_format="text",
    )

    transcript_path = f"{base_path}transcript.txt"

    print(transcript)
    with open(transcript_path, "w") as file:
        file.write(transcript)

    return transcript, transcript_path


def translate_text(transcript):
    print("Translating transcript")
    client = OpenAI(api_key=openai_api_key)

    prompt = f"""
Translate the text that is provided into Spanish. Don't lose the context.
Text:
{transcript}
"""
    response = client.chat.completions.create(
        model="gpt-4", messages=[{"role": "user", "content": prompt}]
    )

    translated_transcript = response.choices[0].message.content
    print("Translated transcript:", response)

    translated_transcript_path = f"{base_path}translated_transcript.txt"
    with open(translated_transcript_path, "w") as file:
        file.write(translated_transcript)

    return translated_transcript, translated_transcript_path


def voiceover_translation(translated_transcript):
    print("Creating voiceover for translated transcript")
    client = OpenAI(api_key=openai_api_key)

    # make chunks of the translated transcript
    # create voiceover for each chunk and merge the audio files using ffmpeg
    text_chunks = translated_transcript.split(".")
    final_chunks = [""]
    for chunk in text_chunks:
        if not final_chunks[-1] or len(final_chunks[-1])+len(chunk)<4096:
            chunk += "."
            final_chunks[-1]+=chunk
        else:
            final_chunks.append(chunk+".")
        final_chunks

    file_names = []
    for i, chunk in enumerate(final_chunks):
        print(f"Creating voiceover for chunk {i}")
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=chunk
        )

        speech_file_path = f"{base_path}translated_audio_{i}.mp3"
        response.stream_to_file(speech_file_path)
        file_names.append(speech_file_path)

    # merge the audio files using ffmpeg
    print("Merging audio files")
    ffmpeg_command = f"ffmpeg -i 'concat:{'|'.join(file_names)}' -c copy {base_path}final_translated_audio.mp3"
    subprocess.run(ffmpeg_command, shell=True)

    return f"{base_path}translated_audio.mp3"


def main():
    download_video(video_url=video_url, video_path=video_path)
    audio_path, video_without_audio_path = separate_audio_from_video(video_path=video_path)
    transcript, transcript_path = transcribe_audio(audio_path=audio_path)
    with open("content/transcript.txt", "r") as file:
        transcript = file.read()
    translated_transcript, translated_transcript_path = translate_text(transcript=transcript)
    with open("content/translated_transcript.txt", "r") as file:
        translated_transcript = file.read()
    translated_audio_path = voiceover_translation(translated_transcript=translated_transcript)


if __name__ == "__main__":
    main()
