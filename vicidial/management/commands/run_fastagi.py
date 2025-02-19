import re
import time
import logging
from pystrix.agi import FastAGIServer
from django.core.management.base import BaseCommand
from pystrix.agi.core import SetExtension,StreamFile,Hangup, SetVariable, GetVariable, SetPriority
# Configure logging
from connection_app.enums import SalesOrderInvoiceEnum, SalesOrderStatusEnum
from connection_app.models import CustomerProfile, SalesOrder
from teams.models import SDMSUser, UserProfile
from vicidial.functions import transfer_in_out1005_to_delivery_boy, fetch_numbers_delivery_boys

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('FastAGI')

TRANSFER_NUMBER = " "
# Define the sound file paths as constants
NO_SALE_SOUND = "/usr/share/asterisk/custom_sounds/no_sale"
DEFAULT_MESSAGE_SOUND = "/usr/share/asterisk/custom_sounds/custom_message"

# Function to handle incoming AGI requests
def _play_sound_and_end_call(agi, sound_file):
    """Helper function to play a sound and end the call."""
    try:
        agi.execute(StreamFile(sound_file))
    except Exception as e:
        logger.error(f"Error playing sound file {sound_file}: {e}")
    finally:
        agi.execute(SetExtension("5"))
        agi.execute(SetPriority(1))

def handle_commercial_call(agi, args, kwargs, match, path):
    """Handles the incoming AGI request."""
    try:
        agi.AGI_RESULT = TRANSFER_NUMBER
        # Access AGI environment (just as an example, we print the caller ID)
        caller_id = agi.get_environment().get('agi_callerid', 'Unknown')
        logger.info(f"Handling call from: {caller_id} and full details : {agi}")

        set_call = fetch_numbers_delivery_boys(caller_id)

        if set_call is None:
            logger.info("No call set up, playing default message.")
            _play_sound_and_end_call(agi, DEFAULT_MESSAGE_SOUND)

        elif set_call == "no_sale":
            logger.info("No sale identified, playing 'no sale' message.")
            _play_sound_and_end_call(agi, NO_SALE_SOUND)

        elif set_call.isdigit() and len(set_call) == 10:
            agi.execute(SetVariable("AGI_RESULT", set_call))

            # Verify variable was set
            result = agi.execute(GetVariable('AGI_RESULT'))
            logger.info(f"Set TRANSFER_NUMBER to: {result}")

            logger.info(f"Call from {caller_id} processed successfully.")

    except Exception as e:
        logger.error(f"Error handling commercial call: {e}")
        agi.execute(Hangup())

# Create and configure the FastAGI server
def start_fastagi_server():
    """Starts the FastAGI server."""
    try:
        logger.info("Starting FastAGI server on port 3055...")
        server = FastAGIServer(
            interface="0.0.0.0",  # Bind to localhost
            port=3055,              # Listening on port 8001
            daemon_threads=True     # Allow server to run in the background
        )

        # Register the handler for commercial_call
        server.register_script_handler(re.compile('commercial_call'), handle_commercial_call)

        # Start the server
        server.serve_forever()
        logger.info("FastAGI server is now running.")

    except Exception as e:
        logger.error(f"Error starting FastAGI server: {e}")


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        start_fastagi_server()
