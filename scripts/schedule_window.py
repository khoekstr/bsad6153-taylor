"""Allow only the agreed four-day scheduled trial; manual runs remain explicit."""
from datetime import datetime, timezone
import os

START = datetime(2026, 11, 13, tzinfo=timezone.utc)
END = datetime(2026, 11, 17, tzinfo=timezone.utc)


def allowed(event, ref, now):
    if ref != 'refs/heads/main':
        return False
    if event == 'workflow_dispatch':
        return True
    return event == 'schedule' and START <= now < END


def main():
    proceed = allowed(os.getenv('GITHUB_EVENT_NAME'), os.getenv('GITHUB_REF'),
                      datetime.now(timezone.utc))
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        output.write('run_sync=' + str(proceed).lower() + '\n')
    print('Sync permitted.' if proceed else 'No sync: branch validation or outside the four-day trial.')


if __name__ == '__main__':
    main()
