import argparse
import logging
import time

from . import config, feeds, judge, manifest, provision

logger = logging.getLogger(__name__)


def loop(settings, items):
    logger.info('Starting dealhound loop')
    provision.provision(items, settings)
    while True:
        try:
            ingested = feeds.ingest(items, settings)
            logger.info(f'Ingested {ingested} candidates')
        except Exception:
            logger.exception('Error during ingest')
        try:
            judged = judge.judge(settings, items)
            logger.info(f'Judged {judged} candidates')
        except Exception:
            logger.exception('Error during judge')
        time.sleep(600)


def main():
    parser = argparse.ArgumentParser(description='Dealhound discount watcher sidecar')
    parser.add_argument('--manifest', default=str(manifest.DEFAULT_MANIFEST))
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('provision', 'ingest', 'judge', 'loop'):
        commands.add_parser(command)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    settings = config.settings()
    items = manifest.load(args.manifest)
    if args.command == 'provision':
        print(f'Watches changed: {provision.provision(items, settings)}')
    elif args.command == 'ingest':
        print(f'Candidates ingested: {feeds.ingest(items, settings)}')
    elif args.command == 'judge':
        print(f'Candidates judged: {judge.judge(settings, items)}')
    elif args.command == 'loop':
        loop(settings, items)


if __name__ == '__main__':
    main()
