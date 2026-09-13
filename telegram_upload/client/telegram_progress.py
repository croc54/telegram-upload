import time
from typing import Optional


class TelegramProgressReporter:
    """Render upload progress in a Telegram message."""

    UPDATE_INTERVAL = 2.0

    def __init__(
        self,
        client,
        entity,
        file_name: str,
        file_size: int,
        update_interval: float = UPDATE_INTERVAL,
    ):
        self.client = client
        self.entity = entity
        self.file_name = file_name
        self.file_size = file_size
        self.update_interval = update_interval

        self.message = None
        self.started_at: Optional[float] = None
        self.last_update_at: Optional[float] = None
        self.last_current = 0

    async def start(self):
        """Send the initial progress message."""
        self.started_at = time.monotonic()
        self.last_update_at = self.started_at
        self.last_current = 0

        self.message = await self.client.send_message(
            self.entity,
            self._format(0, now=self.started_at),
            parse_mode='html',
        )
        return self.message

    async def update(self, current: int, total: int):
        """Update the progress message when the throttle allows it."""
        if self.message is None:
            return

        if current < self.last_current:
            return

        self.last_current = current

        now = time.monotonic()
        if current < total and now - self.last_update_at < self.update_interval:
            return

        await self.message.edit(
            self._format(current, total, now),
            parse_mode='html',
        )
        self.last_update_at = now

    async def finish(self):
        """Remove the progress message after a successful upload."""
        if self.message is None:
            return

        await self.message.delete()
        self.message = None

    async def fail(self, error):
        """Leave a useful failure message in the chat."""
        if self.message is None:
            return

        text = (
            "❌ <b>Upload failed</b>\n\n"
            f"<code>{self.file_name}</code>\n"
            f"{error}"
        )
        await self.message.edit(text, parse_mode='html')

    def _format(
        self,
        current: int,
        total: Optional[int] = None,
        now: Optional[float] = None,
    ) -> str:
        if total is None:
            total = self.file_size

        if now is None:
            now = time.monotonic()

        total = max(total, 1)
        current = max(0, min(current, total))

        percentage = current * 100 / total
        elapsed = max(now - (self.started_at or now), 0.0)

        if elapsed > 0 and current > 0:
            speed = current / elapsed
        else:
            speed = 0.0

        remaining = total - current
        eta = remaining / speed if speed > 0 else None

        return (
            "📤 <b>Uploading</b>\n\n"
            f"<code>{self.file_name}</code>\n"
            f"{self._progress_bar(percentage)} {percentage:.0f}%\n"
            f"{self._format_bytes(current)} / {self._format_bytes(total)}\n"
            f"{self._format_speed(speed)}"
            f" • ETA {self._format_duration(eta)}"
        )

    @staticmethod
    def _progress_bar(percentage: float, width: int = 20) -> str:
        filled = round(width * percentage / 100)
        return "█" * filled + "░" * (width - filled)

    @staticmethod
    def _format_bytes(value: float) -> str:
        value = float(value)
        units = ("B", "KiB", "MiB", "GiB", "TiB")

        for unit in units:
            if value < 1024 or unit == units[-1]:
                if unit == "B":
                    return f"{value:.0f} {unit}"
                return f"{value:.2f} {unit}"
            value /= 1024

        return f"{value:.2f} TiB"

    @staticmethod
    def _format_speed(value: float) -> str:
        return f"{TelegramProgressReporter._format_bytes(value)}/s"

    @staticmethod
    def _format_duration(seconds: Optional[float]) -> str:
        if seconds is None:
            return "—"

        seconds = max(0, int(seconds))

        if seconds < 60:
            return f"{seconds}s"

        minutes, seconds = divmod(seconds, 60)

        if minutes < 60:
            return f"{minutes}m {seconds:02d}s"

        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes:02d}m"
