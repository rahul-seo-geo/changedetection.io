import json
import logging

import requests

logger = logging.getLogger(__name__)


def alert(candidate, webhook, session=None):
    if not webhook:
        logger.warning('Discord webhook not configured; skipping alert')
        return False
    session = session or requests
    price = candidate.get('price')
    signal = f'Parsed title price: AUD ${price:.2f} (unverified).' if price is not None else 'No price found in the title.'
    text = (f"Dealhound matched {candidate['matched_item']} from {candidate['feed_source']}. "
            f"{signal} View deal: {candidate['link']}\n```json\n{json.dumps(candidate, ensure_ascii=False)}\n```")
    response = session.post(webhook, json={'content': text}, timeout=20)
    response.raise_for_status()
    return True
