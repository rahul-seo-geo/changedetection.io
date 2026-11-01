import argparse
import logging

from . import config, feeds, judge, manifest, provision


def main():
    parser = argparse.ArgumentParser(description='Dealhound discount watcher sidecar')
    parser.add_argument('--manifest', default=str(manifest.DEFAULT_MANIFEST))
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('provision', 'ingest', 'judge'):
        commands.add_parser(command)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    settings = config.settings()
    items = manifest.load(args.manifest)
    if args.command == 'provision':
        print(f'Watches changed: {provision.provision(items, settings)}')
    elif args.command == 'ingest':
        print(f'Candidates ingested: {feeds.ingest(items, settings)}')
    else:
        print(f'Candidates judged: {judge.judge(settings)}')


if __name__ == '__main__':
    main()
