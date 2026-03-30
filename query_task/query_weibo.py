import datetime
import json
import re
import time
from collections import deque

from common import util
from common.logger import log
from common.proxy import my_proxy
from query_task import QueryTask


class QueryWeibo(QueryTask):
    def __init__(self, config):
        super().__init__(config)
        self.uid_list = config.get("uid_list", [])
        log.info(f"uid_list:{self.uid_list}")
        self.cookie = config.get("cookie", "")
        self.weibo_http_error_notify_interval_seconds = 6 * 60 * 60
        self.weibo_http_error_last_notify_ts = 0

    def query(self):
        if not self.enable:
            return
        try:
            current_time = time.strftime("%H:%M", time.localtime(time.time()))
            if self.begin_time <= current_time <= self.end_time:
                my_proxy.current_proxy_ip = my_proxy.get_proxy(proxy_check_url="https://m.weibo.com")
                if self.enable_dynamic_check:
                    for uid in self.uid_list:
                        self.query_dynamic(uid)
        except Exception as e:
            log.error(f"【微博-查询任务-{self.name}】出错：{e}", exc_info=True)

    def query_dynamic(self, uid=None):
        if uid is None:
            return
        uid = str(uid)
        query_url = f"https://m.weibo.cn/api/container/getIndex?type=uid&value={uid}&containerid=107603{uid}&count=25"
        headers = self.get_headers(uid)
        if self.cookie != "":
            headers["cookie"] = self.cookie
        response = util.requests_get(query_url, f"微博-查询动态状态-{self.name}", headers=headers, use_proxy=True)
        if response is None:
            log.error(f"微博请求失败：response=None url={query_url}")
            return
        log.info(f"微博HTTP状态码: {response.status_code} url={query_url}")
        if 400 <= response.status_code < 500:
            self.notify_weibo_http_client_error(uid=uid, response=response, query_url=query_url)
            return

        # 有些情况下返回不是json，这里也要兜底
        try:
            result = response.json()
            log.info(f"微博业务返回：ok={result.get('ok')} keys={list(result.keys())}")
        except Exception as e:
            log.error(f"微博返回非JSON：{e} text={response.text[:500]}")
            return

        if "data" not in result:
            log.error(f"微博接口返回异常：keys={list(result.keys())} body={str(result)[:1200]}")
            return

        if util.check_response_is_ok(response):
            # 前面你已经 result = response.json() 了，这里直接用 result
            if not util.check_response_is_ok(response):
                log.error(f"微博接口响应不OK：status={response.status_code} text={response.text[:300]}")
                return

            log.info("check_response_is_ok")

            cards = result["data"].get("cards", [])
            if len(cards) == 0:
                super().handle_for_result_null("-1", uid, "微博", uid)
                log.info("cards为0")
                return


            # 循环遍历 cards ，剔除不满足要求的数据
            cards = [card for card in cards if
                     card.get("mblog") is not None  # 跳过不包含 mblog 的数据
                     and card["mblog"].get("isTop", None) != 1  # 跳过置顶
                     and card["mblog"].get("mblogtype", None) != 2  # 跳过置顶
                     ]
            log.info(f"cards_type={type(cards)} cards_len={len(cards) if isinstance(cards, list) else 'NA'}")

            # 跳过置顶后再判断一下，防止越界
            if len(cards) == 0:
                super().handle_for_result_null("-1", uid, "微博", uid)
                return

            card = cards[0]
            mblog = card["mblog"]
            mblog_id = mblog["id"]
            user = mblog["user"]
            screen_name = user["screen_name"]

            avatar_url = None
            try:
                avatar_url = user["avatar_hd"]
            except Exception:
                log.error(f"【微博-查询动态状态-{self.name}】头像获取发生错误，uid：{uid}")

            if self.dynamic_dict.get(uid, None) is None:
                self.dynamic_dict[uid] = deque(maxlen=self.len_of_deque)
                for index in range(self.len_of_deque):
                    if index < len(cards):
                        self.dynamic_dict[uid].appendleft(cards[index]["mblog"]["id"])
                log.info(f"【微博-查询动态状态-{self.name}】【{screen_name}】动态初始化：{self.dynamic_dict[uid]}")
                return

            if mblog_id not in self.dynamic_dict[uid]:
                previous_mblog_id = self.dynamic_dict[uid].pop()
                self.dynamic_dict[uid].append(previous_mblog_id)
                log.info(f"【微博-查询动态状态-{self.name}】【{screen_name}】上一条动态id[{previous_mblog_id}]，本条动态id[{mblog_id}]")
                self.dynamic_dict[uid].append(mblog_id)
                log.debug(self.dynamic_dict[uid])

                card_type = card["card_type"]
                if card_type not in [9]:
                    log.info(f"【微博-查询动态状态-{self.name}】【{screen_name}】动态有更新，但不在需要推送的动态类型列表中")
                    return

                # 如果动态发送日期早于昨天，则跳过（既能避免因api返回历史内容导致的误推送，也可以兼顾到前一天停止检测后产生的动态）
                created_at = time.strptime(mblog["created_at"], "%a %b %d %H:%M:%S %z %Y")
                created_at_ts = time.mktime(created_at)
                yesterday = (datetime.datetime.now() + datetime.timedelta(days=-1)).strftime("%Y-%m-%d")
                yesterday_ts = time.mktime(time.strptime(yesterday, "%Y-%m-%d"))
                if created_at_ts < yesterday_ts:
                    log.info(f"【微博-查询动态状态-{self.name}】【{screen_name}】动态有更新，但动态发送时间早于今天，可能是历史动态，不予推送")
                    return
                dynamic_time = time.strftime("%Y-%m-%d %H:%M:%S", created_at)

                content = None
                pic_url = None
                jump_url = None
                if card_type == 9:
                    text = mblog["text"]
                    text = re.sub(r"<[^>]+>", "", text)
                    content = mblog["raw_text"] if mblog.get("raw_text", None) is not None else text
  
                    # 支持多图：优先从 mblog["pics"] 取，兜底 original_pic
                    pic_url_list = []
                    pics = mblog.get("pics") or []
                    if isinstance(pics, list):
                        for p in pics:
                            if not isinstance(p, dict):
                                continue
                            # 常见字段：large.url / url
                            u = (p.get("large") or {}).get("url") or p.get("url")
                            if u:
                                pic_url_list.append(u)
  
                    if not pic_url_list:
                        u = mblog.get("original_pic")
                        if u:
                            pic_url_list = [u]
  
                    # 最多推 9 张，避免风控/消息过长
                    pic_url = pic_url_list[:9] if pic_url_list else None
                    jump_url = card["scheme"]
                log.info(f"【微博-查询动态状态-{self.name}】【{screen_name}】动态有更新，准备推送：{content[:30]}")
                self.push_for_weibo_dynamic(screen_name, mblog_id, content, pic_url, jump_url, dynamic_time, dynamic_raw_data=card, avatar_url=avatar_url)

    def notify_weibo_http_client_error(self, uid=None, response=None, query_url=None):
        if uid is None or response is None or query_url is None:
            return

        now_ts = time.time()
        last_notify_ts = self.weibo_http_error_last_notify_ts
        if now_ts - last_notify_ts < self.weibo_http_error_notify_interval_seconds:
            remain_seconds = int(self.weibo_http_error_notify_interval_seconds - (now_ts - last_notify_ts))
            log.info(
                f"【微博-查询动态状态-{self.name}】【{uid}】4xx异常已在限频窗口内，跳过告警："
                f"status={response.status_code} remain_seconds={remain_seconds}"
            )
            return

        self.weibo_http_error_last_notify_ts = now_ts
        response_text = ""
        try:
            response_text = response.text[:500]
        except Exception:
            response_text = "<无法读取响应正文>"

        title = f"【微博接口异常】{self.name}"
        content = (
            f"微博接口返回4xx状态码，请检查 Cookie、代理或请求频率。\n"
            f"同类异常 6 小时内仅提醒一次。\n"
            f"任务: {self.name}\n"
            f"UID: {uid}\n"
            f"状态码: {response.status_code}\n"
            f"URL: {query_url}\n"
            f"响应片段: {response_text}"
        )
        log.error(f"【微博-查询动态状态-{self.name}】【{uid}】4xx异常：status={response.status_code} url={query_url}")
        super().push(title, content, jump_url=query_url)

    @staticmethod
    def get_headers(uid):
        return {
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "mweibo-pwa": "1",
            "referer": f"https://m.weibo.cn/u/{uid}",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "x-requested-with": "XMLHttpRequest",
        }

    def push_for_weibo_dynamic(self, username=None, mblog_id=None, content=None, pic_url=None,
                            jump_url=None, dynamic_time=None, dynamic_raw_data=None, avatar_url=None):
        """
        微博动态提醒推送
        :param username: 博主名
        :param mblog_id: 动态id
        :param content: 动态内容
        :param pic_url: 图片地址（str 或 list[str]）
        :param jump_url: 跳转地址
        :param dynamic_time: 动态发送时间
        :param dynamic_raw_data: 动态原始数据
        :param avatar_url: 头像url
        """
        if username is None or mblog_id is None or content is None:
            log.error(f"【微博-动态提醒推送-{self.name}】缺少参数，username:[{username}]，mblog_id:[{mblog_id}]，content:[{content[:30]}]")
            return

        title = f"【{username}】发微博了"
        content = f"{content[:100] + (content[100:] and '...')}[{dynamic_time}]"

        # 兼容：Bark/Email 等通常只支持单张；NapCatQQ 支持多张（放 extend_data）
        pic_url_first = None
        pic_url_list = None

        if isinstance(pic_url, list):
            pic_url_list = [u for u in pic_url if isinstance(u, str) and u]
            if pic_url_list:
                pic_url_first = pic_url_list[0]
        elif isinstance(pic_url, str) and pic_url:
            pic_url_first = pic_url
            pic_url_list = [pic_url]

        extend_data = {
            "dynamic_raw_data": dynamic_raw_data,
            "avatar_url": avatar_url,
            "pic_url_list": pic_url_list,  # 给 NapCatQQ 多图用
        }

        # 注意：这里给其他通道传第一张图（不要传 list）
        super().push(title, content, jump_url, pic_url_first, extend_data=extend_data)
