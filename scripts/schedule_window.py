"""Gate scheduled discovery and explicit manual runs to the main branch."""
import os


def allowed(event, ref):
    # The workflow cron owns timing. Delayed schedule events remain eligible.
    return ref == 'refs/heads/main' and event in ('schedule', 'workflow_dispatch')


def main():
    proceed = allowed(os.getenv('GITHUB_EVENT_NAME'), os.getenv('GITHUB_REF'))
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        output.write('run_sync=' + str(proceed).lower() + '\n')
    print('Sync permitted.' if proceed else 'Sync requires a scheduled or manual run on main.')


if __name__ == '__main__':
    main()
