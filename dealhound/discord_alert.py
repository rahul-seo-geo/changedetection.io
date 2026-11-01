import json
import logging
import time

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

    backoffs = [1, 4, 16]
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            response = session.post(webhook, json={'content': text}, timeout=10)
            status = response.status_code
            if status == 429:
                if attempt < max_attempts:
                    retry_after = response.headers.get('Retry-After')
                    sleep_time = float(retry_after) if retry_after and str(retry_after).replace('.', '', 1).isdigit() else backoffs[attempt - 1]
                    time.sleep(sleep_time)
                    continue
            elif 500 <= status < 600:
                if attempt < max_attempts:
                    time.sleep(backoffs[attempt - 1])
                    continue
            elif 400 <= status < 500:
                response.raise_for_status()
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            if e.response is not None:
                status = e.response.status_code
                if 400 <= status < 500 and status != 429:
                    raise
            if attempt == max_attempts:
                raise
            time.sleep(backoffs[attempt - 1])
    return False
