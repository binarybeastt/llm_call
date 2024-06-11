# Standard library imports
import logging
import os
import sys

# Third-party imports
from fastapi import FastAPI
from vocode.streaming.models.telephony import TwilioConfig
from pyngrok import ngrok
from vocode.streaming.telephony.config_manager.redis_config_manager import (
    RedisConfigManager,
)
from vocode.helpers import create_streaming_microphone_input_and_speaker_output
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.telephony.server.base import (
    TwilioInboundCallConfig,
    TelephonyServer,
)
from dotenv import load_dotenv
from vocode.streaming.models.synthesizer import StreamElementsSynthesizerConfig, AzureSynthesizerConfig
from vocode.streaming.models.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.streaming.models.transcriber import DeepgramTranscriberConfig, PunctuationEndpointingConfig
from vocode.streaming.models.transcriber.deepgram_transcriber import DeepgramTranscriber

async def main():
    microphone_input, speaker_output = create_streaming_microphone_input_and_speaker_output(
        use_default_devices=True,
    )
# Local application/library specific imports
from speller_agent import (
    SpellerAgentFactory,
    SpellerAgentConfig,
)

# if running from python, this will load the local .env
# docker-compose will load the .env file by itself
load_dotenv()

app = FastAPI(docs_url=None)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

config_manager = RedisConfigManager(
    logger=logger,
)

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

# SYNTH_CONFIG = StreamElementsSynthesizerConfig.from_telephone_output_device()
SYNTH_CONFIG = AzureSynthesizer(AzureSynthesizerConfig.from_telephone_output_device())
TRANS_CONFIG = DeepgramTranscriber(DeepgramTranscriberConfig.from_input_device(endpointing_config=PunctuationEndpointingConfig()))
agent_config=ChatGPTAgentConfig(
                initial_message=BaseMessage(text="What up"),
                prompt_preamble="Have a pleasant conversation about life",
                generate_responses=True,
)
twilio_config=TwilioConfig(
                account_sid=os.environ["TWILIO_ACCOUNT_SID"],
                auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            )
telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    inbound_call_configs=[
        TwilioInboundCallConfig(
            url="/inbound_call",
            agent_config=agent_config,
            # uncomment this to use the speller agent instead
            # agent_config=SpellerAgentConfig(
            #     initial_message=BaseMessage(text="im a speller agent, say something to me and ill spell it out for you"),
            #     generate_responses=False,
            # ),
            twilio_config=twilio_config,
            synthesizer_config=SYNTH_CONFIG,
            transcriber_config=TRANS_CONFIG
        )
    ],
    logger=logger,
)

app.include_router(telephony_server.get_router())