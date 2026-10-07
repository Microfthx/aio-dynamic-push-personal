import unittest

from query_task.query_weibo import QueryWeibo


class CleanWeiboHtmlTest(unittest.TestCase):
    def test_preserves_custom_emoji_alt_text(self):
        value = (
            '早上好<span class="url-icon">'
            '<img src="emoji.png" alt="[太阳]"></span>'
            '<img alt=\'[抱一抱]\' src="emoji-2.png">'
        )

        self.assertEqual(QueryWeibo.clean_weibo_html(value), "早上好[太阳][抱一抱]")

    def test_preserves_native_emoji_and_decodes_alt_entities(self):
        value = '开心😀<img alt="&#91;允悲&#93;" src="emoji.png">'

        self.assertEqual(QueryWeibo.clean_weibo_html(value), "开心😀[允悲]")

    def test_discards_non_emoji_images_without_alt_text(self):
        self.assertEqual(QueryWeibo.clean_weibo_html('<img src="photo.jpg">'), "")


class RetweetedWeiboUrlTest(unittest.TestCase):
    def test_returns_original_weibo_url_for_retweet(self):
        mblog = {"retweeted_status": {"id": "1234567890"}}

        self.assertEqual(
            QueryWeibo.get_retweeted_weibo_url(mblog),
            "https://m.weibo.cn/detail/1234567890",
        )

    def test_falls_back_to_idstr(self):
        mblog = {"retweeted_status": {"idstr": "9876543210"}}

        self.assertEqual(
            QueryWeibo.get_retweeted_weibo_url(mblog),
            "https://m.weibo.cn/detail/9876543210",
        )

    def test_returns_none_for_original_or_incomplete_weibo(self):
        self.assertIsNone(QueryWeibo.get_retweeted_weibo_url({}))
        self.assertIsNone(QueryWeibo.get_retweeted_weibo_url({"retweeted_status": {}}))


if __name__ == "__main__":
    unittest.main()
