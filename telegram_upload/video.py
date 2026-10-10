import platform
import re
import subprocess
import tempfile
import os

from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from hachoir.core import config as hachoir_config

from telegram_upload.exceptions import ThumbVideoError


hachoir_config.quiet = True


def video_metadata(file):
    return extractMetadata(createParser(file))


def call_ffmpeg(args):
    try:
        return subprocess.Popen([get_ffmpeg_command()] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        raise ThumbVideoError('ffmpeg command is not available. Thumbnails for videos are not available!')


def get_ffmpeg_command():
    return os.environ.get('FFMPEG_COMMAND',
                          'ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg')


def get_video_size(file):
    p = call_ffmpeg([
        '-i', file,
    ])
    stdout, stderr = p.communicate()
    video_lines = re.findall(': Video: ([^\n]+)', stderr.decode('utf-8', errors='ignore'))
    if not video_lines:
        return
    matchs = re.findall("(\d{2,6})x(\d{2,6})", video_lines[0])
    if matchs:
        return [int(x) for x in matchs[0]]


def get_video_thumb(file, output=None, size=320):
    output = output or tempfile.NamedTemporaryFile(suffix='.jpg').name

    metadata = video_metadata(file)
    if metadata is None:
        return

    duration = metadata.get('duration').seconds if metadata.has('duration') else 0

    ratio = get_video_size(file)
    if ratio is None or ratio[0] <= 0 or ratio[1] <= 0:
        raise ThumbVideoError('Video ratio is not available.')

    # Never exceed Telegram's 320x320 thumbnail dimension limit.
    size = min(max(int(size), 1), 320)

    if ratio[0] >= ratio[1]:
        width, height = size, -2
    else:
        width, height = -2, size

    # Start with high JPEG quality and reduce it only if needed
    # to stay comfortably below Telegram's 200 KB limit.
    for quality in (2, 4, 6, 8, 10, 12, 15, 18, 22, 26, 31):
        p = call_ffmpeg([
            '-y',
            '-ss', str(max(0, duration // 2)),
            '-i', file,
            '-frames:v', '1',
            '-vf',
            'scale={}:{}:force_original_aspect_ratio=decrease'.format(
                width, height
            ),
            '-q:v', str(quality),
            '-f', 'image2',
            output,
        ])

        _, stderr = p.communicate()

        if p.returncode != 0:
            raise ThumbVideoError(
                'FFmpeg failed to generate video thumbnail: {}'.format(
                    stderr.decode('utf-8', errors='replace')
                )
            )

        if os.path.isfile(output) and os.path.getsize(output) <= 190 * 1024:
            return output

    raise ThumbVideoError(
        'Could not generate a thumbnail below Telegram’s size limit.'
    )
