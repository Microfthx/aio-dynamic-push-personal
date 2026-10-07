import base64
import tempfile
import unittest
from pathlib import Path

from common.weibo_emoji import build_onebot_content_segments, load_emoji_as_base64


class WeiboEmojiSegmentsTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.emoji_root = Path(self.temporary_directory.name)
        (self.emoji_root / "允悲.png").write_bytes(b"fake-png-data")
        load_emoji_as_base64.cache_clear()

    def tearDown(self):
        load_emoji_as_base64.cache_clear()
        self.temporary_directory.cleanup()

    def test_replaces_known_emoji_and_keeps_text_order(self):
        segments = build_onebot_content_segments(
            "开头[允悲]结尾",
            emoji_root=self.emoji_root,
        )

        self.assertEqual(segments[0], {"type": "text", "data": {"text": "开头"}})
        self.assertEqual(segments[1]["type"], "image")
        self.assertEqual(
            base64.b64decode(segments[1]["data"]["file"].removeprefix("base64://")),
            b"fake-png-data",
        )
        self.assertEqual(segments[2], {"type": "text", "data": {"text": "结尾"}})

    def test_keeps_unknown_emoji_as_text(self):
        segments = build_onebot_content_segments(
            "内容[不存在的表情]",
            emoji_root=self.emoji_root,
        )

        self.assertEqual(
            segments,
            [{"type": "text", "data": {"text": "内容[不存在的表情]"}}],
        )

    def test_rejects_path_like_tokens(self):
        segments = build_onebot_content_segments(
            "内容[../允悲]",
            emoji_root=self.emoji_root,
        )

        self.assertEqual(
            segments,
            [{"type": "text", "data": {"text": "内容[../允悲]"}}],
        )


if __name__ == "__main__":
    unittest.main()
