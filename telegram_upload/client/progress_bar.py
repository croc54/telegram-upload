import click


def get_progress_bar(action, file, length):
    print(f'{action} "{file}"')
    bar = click.progressbar(
        length=length,
        fill_char=click.style('■', fg='green'),
        empty_char=click.style('□', fg='white')
    )
    last_current = 0

    def progress(current, total):
        nonlocal last_current
        if current < last_current:
            return
        bar.pos = 0
        bar.update(current)
        last_current = current
    return progress, bar
