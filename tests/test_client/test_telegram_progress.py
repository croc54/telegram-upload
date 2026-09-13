import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram_upload.client.telegram_progress import TelegramProgressReporter


class TestTelegramProgressReporter(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = MagicMock()
        self.entity = "chat"
        self.message = MagicMock()

        self.reporter = TelegramProgressReporter(
            self.client,
            self.entity,
            "file.bin",
            1000,
        )

    async def test_start_sends_one_message(self):
        self.client.send_message = AsyncMock(return_value=self.message)

        with patch(
            "telegram_upload.client.telegram_progress.time.monotonic",
            return_value=100.0,
        ):
            result = await self.reporter.start()

        self.assertIs(self.message, result)
        self.assertIs(self.message, self.reporter.message)
        self.client.send_message.assert_awaited_once()

        args = self.client.send_message.await_args.args
        self.assertEqual(self.entity, args[0])
        self.assertIn("Uploading", args[1])
        self.assertIn("0%", args[1])

    async def test_update_is_throttled(self):
        self.client.send_message = AsyncMock(return_value=self.message)
        self.message.edit = AsyncMock()

        with patch(
            "telegram_upload.client.telegram_progress.time.monotonic",
            side_effect=[100.0, 100.5, 102.1],
        ):
            await self.reporter.start()
            await self.reporter.update(100, 1000)
            await self.reporter.update(200, 1000)

        self.assertEqual(1, self.message.edit.await_count)

    async def test_update_at_100_percent_is_not_delayed(self):
        self.client.send_message = AsyncMock(return_value=self.message)
        self.message.edit = AsyncMock()

        with patch(
            "telegram_upload.client.telegram_progress.time.monotonic",
            side_effect=[100.0, 100.1],
        ):
            await self.reporter.start()
            await self.reporter.update(1000, 1000)

        self.message.edit.assert_awaited_once()
        self.assertIn("100%", self.message.edit.await_args.args[0])

    async def test_progress_does_not_go_backwards(self):
        self.client.send_message = AsyncMock(return_value=self.message)
        self.message.edit = AsyncMock()

        with patch(
            "telegram_upload.client.telegram_progress.time.monotonic",
            side_effect=[100.0, 103.0, 106.0],
        ):
            await self.reporter.start()
            await self.reporter.update(500, 1000)
            await self.reporter.update(400, 1000)

        self.assertEqual(1, self.message.edit.await_count)

    async def test_finish_deletes_message(self):
        self.client.send_message = AsyncMock(return_value=self.message)
        self.message.delete = AsyncMock()

        await self.reporter.start()
        await self.reporter.finish()

        self.message.delete.assert_awaited_once()
        self.assertIsNone(self.reporter.message)

    async def test_fail_keeps_message(self):
        self.client.send_message = AsyncMock(return_value=self.message)
        self.message.edit = AsyncMock()

        await self.reporter.start()
        await self.reporter.fail("Network error")

        text = self.message.edit.await_args.args[0]
        self.assertIn("Upload failed", text)
        self.assertIn("Network error", text)
        self.assertIs(self.message, self.reporter.message)

    def test_format_helpers(self):
        self.assertEqual("0 B", self.reporter._format_bytes(0))
        self.assertEqual("1.00 KiB", self.reporter._format_bytes(1024))
        self.assertEqual("1.00 MiB", self.reporter._format_bytes(1024 ** 2))

        self.assertEqual("5s", self.reporter._format_duration(5))
        self.assertEqual("1m 05s", self.reporter._format_duration(65))
        self.assertEqual("1h 01m", self.reporter._format_duration(3660))
        self.assertEqual("—", self.reporter._format_duration(None))


if __name__ == "__main__":
    unittest.main()
