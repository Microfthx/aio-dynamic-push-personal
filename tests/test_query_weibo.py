import unittest

from query_task.query_weibo import QueryWeibo


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
