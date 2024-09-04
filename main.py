# Standard library imports
import os
import sys
import typing


from dotenv import load_dotenv

# Third-party imports
from fastapi import FastAPI
from loguru import logger
from pyngrok import ngrok

# Local application/library specific imports
from speller_agent import SpellerAgentFactory

from vocode.logging import configure_pretty_logging
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.telephony import TwilioConfig
from vocode.streaming.telephony.config_manager.redis_config_manager import RedisConfigManager
from vocode.streaming.telephony.server.base import TelephonyServer, TwilioInboundCallConfig
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
)
from vocode.streaming.models.audio import AudioEncoding
from vocode.streaming.models.events import Event, EventType
from vocode.streaming.models.transcript import TranscriptCompleteEvent
from vocode.streaming.utils import events_manager

from call_transcript_utils import add_transcript, parse_transcript
from twilio.rest import Client


# if running from python, this will load the local .env
# docker-compose will load the .env file by itself
load_dotenv()

configure_pretty_logging()

app = FastAPI(docs_url=None)

config_manager = RedisConfigManager()

BASE_URL = os.getenv("BASE_URL")

if not BASE_URL:
    ngrok_auth = os.environ.get("NGROK_AUTH_TOKEN")
    if ngrok_auth is not None:
        ngrok.set_auth_token(ngrok_auth)
    port = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else 3000

    # Open a ngrok tunnel to the dev server
    BASE_URL = ngrok.connect(port).public_url.replace("https://", "")
    logger.info('ngrok tunnel "{}" -> "http://127.0.0.1:{}"'.format(BASE_URL, port))

if not BASE_URL:
    raise ValueError("BASE_URL must be set in environment if not using pyngrok")

class EventsManager(events_manager.EventsManager):
    def __init__(self):
        super().__init__(subscriptions=[EventType.TRANSCRIPT_COMPLETE])

    async def handle_event(self, event: Event):
        if event.type == EventType.TRANSCRIPT_COMPLETE:
            transcript_complete_event = typing.cast(TranscriptCompleteEvent, event)
            add_transcript(
                transcript_complete_event.conversation_id,
                transcript_complete_event.transcript.to_string(),
            )

            # Get the phone number to send the verification text to and the verification message
            phone_number, message = parse_transcript(transcript_complete_event.conversation_id)
            logger.info(phone_number)
            logger.info(message)
            if phone_number and message:
                # Hardcode the phone number to send the verification text to for testing
                hard_check = os.environ["TO_PHONE"]
                if hard_check:
                    if len(phone_number) < len(hard_check):
                        phone_number = hard_check
                # Adjust the phone number to match the necessary Twilio format
                if "+1" not in phone_number: 
                    phone_number = "+1" + phone_number

                account_sid = os.environ["TWILIO_ACCOUNT_SID"]
                auth_token = os.environ["TWILIO_AUTH_TOKEN"]
                client = Client(account_sid, auth_token)
                message = client.messages.create(
                    from_=os.environ["FROM_PHONE"],
                    body=message,
                    to=phone_number
                    )

telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    events_manager=EventsManager(),
    inbound_call_configs=[
        TwilioInboundCallConfig(
            url="/inbound_call",
            transcriber_config=DeepgramTranscriberConfig.from_telephone_input_device(
                endpointing_config=PunctuationEndpointingConfig(),
                api_key=os.environ["DEEPGRAM_API_KEY"],
            ),
            agent_config=ChatGPTAgentConfig(
                allowed_idle_time_seconds=900,
                num_check_human_present_times=100,
                openai_api_key=os.environ["OPENAI_API_KEY"],
                initial_message=BaseMessage(text="Hello, please provide your name and date of birth!"),
                prompt_preamble="""The AI is an agent who is setting up a patient appointment. If the patient does not provide the information in the following order, keep reasking the same step:
                1. Ask their name and date of birth. The date of the birth should have a day, month, and year.
                2. Ask their payer name and insurance ID. 
                3. Ask if they have a referral.
                3a. If they do have a referral, ask for the physician name.
                4. Ask what is the main medical reason they are coming in.
                5. Ask for their address and phone number. The phone number should have nine digits.
                6. Ask for their email. The email should have an @ symbol.
                After these steps, suggest random doctor names and times after today's date.
                Then you can hang up.
                You can only ask one question at a time. 
                Repeat the exact same question if you don't get all details.
                """,
            ),
        synthesizer_config=ElevenLabsSynthesizerConfig(
            sampling_rate=8000,
            audio_encoding=AudioEncoding.MULAW,
            api_key=os.environ["ELEVEN_LABS_API_KEY"],
            voice_name=os.environ["ELEVEN_LABS_VOICE_ID"],
        ),
            twilio_config=TwilioConfig(
                account_sid=os.environ["TWILIO_ACCOUNT_SID"],
                auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            ),
        )
    ],
    agent_factory=SpellerAgentFactory(),
)

app.include_router(telephony_server.get_router())
