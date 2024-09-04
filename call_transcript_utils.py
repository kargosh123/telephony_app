import os
import re
from typing import Optional

CALL_TRANSCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "call_transcripts")


def add_transcript(conversation_id: str, transcript: str) -> None:
    transcript_path = os.path.join(CALL_TRANSCRIPTS_DIR, "{}.txt".format(conversation_id))
    with open(transcript_path, "a") as f:
        f.write(transcript)


def get_transcript(conversation_id: str) -> Optional[str]:
    transcript_path = os.path.join(CALL_TRANSCRIPTS_DIR, "{}.txt".format(conversation_id))
    if os.path.exists(transcript_path):
        with open(transcript_path, "r") as f:
            return f.read()
    return None

def get_phone_number(word: str) -> Optional[str]:
    # Convert transcribed numbers to actual numbers
    num_dict = {
        'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
        'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'
    }
    words = word.split()
    number =''
    for num in words:
        # Remove punctuations
        num = re.sub(r'[^\w\s]','',num)
        if num in num_dict:
            number += num_dict[num]
    return number

def parse_transcript(conversation_id: str) -> Optional[str]:
    # Returns the phone number to send the verification text to and the verification message
    transcript = get_transcript(conversation_id).split('\n')

    # Find which line contains the phone number
    phone_number = None
    for line in transcript:
        if line.startswith("HUMAN:") and 'phone number' in line:
            phone_number = get_phone_number(line[line.index('phone number') + len('phone number'):].lower())

    # Find which line contains the verification message
    verification_message = ""
    for j in range(len(transcript)):
        if transcript[j].startswith('BOT:') and "your appointment" in transcript[j].lower():
            verification_message = transcript[j][len("BOT: "):]
            verification_message += transcript[j + 1][len("BOT: "):]


    return phone_number, verification_message


def delete_transcript(conversation_id: str) -> bool:
    transcript_path = os.path.join(CALL_TRANSCRIPTS_DIR, "{}.txt".format(conversation_id))
    if os.path.exists(transcript_path):
        os.remove(transcript_path)
        return True
    return False
