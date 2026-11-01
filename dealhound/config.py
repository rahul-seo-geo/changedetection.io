import os
from pathlib import Path


def settings():
    return {
        'webhook': os.getenv('DEALHOUND_DISCORD_WEBHOOK', ''),
        'api_key': os.getenv('DEALHOUND_API_KEY', ''),
        'base_url': os.getenv('DEALHOUND_BASE_URL', 'http://localhost:5000').rstrip('/'),
        'data_dir': Path(os.getenv('DEALHOUND_DATA_DIR', './data')),
        'clef_base_url': os.getenv('CLEF_BASE_URL', '').rstrip('/'),
        'clef_api_key': os.getenv('CLEF_API_KEY', ''),
        'judge_model': os.getenv('DEALHOUND_JUDGE_MODEL', 'auto/cheap'),
    }
