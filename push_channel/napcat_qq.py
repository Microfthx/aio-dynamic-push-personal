import json

from common import util
from common.logger import log
from . import PushChannel


class NapCatQQ(PushChannel):
    """
    Author: https://github.com/YingChengxi
    See: https://github.com/nfe-w/aio-dynamic-push/issues/50
    """

    def __init__(self, config):
        super().__init__(config)
        self.api_url = str(config.get("api_url", ""))
        self.token = str(config.get("token", ""))
        _user_id = config.get("user_id", None)
        self.user_id = str(_user_id) if _user_id else None
        _group_id = config.get("group_id", None)
        self.group_id = str(_group_id) if _group_id else None
        _at_qq = config.get("at_qq", None)
        self.at_qq = str(_at_qq) if _at_qq else None
        if not self.api_url or (not self.user_id and not self.group_id):
            log.error(f"【推送_{self.name}】配置不完整，推送功能将无法正常使用")
        if self.user_id and self.group_id:
            log.error(f"【推送_{self.name}】配置错误，不能同时设置 user_id 和 group_id")
        if self.user_id and self.at_qq:
            log.warning(f"【推送_{self.name}】当前为私聊(user_id)场景，at_qq 将被忽略")

    def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        message = [{
            "type": "text",
            "data": {"text": f"{title}\n\n{content}"}
        }]

        # 多图支持：优先从 extend_data["pic_url_list"] 取，其次兼容 pic_url=str/list
        pic_list = []
        if isinstance(extend_data, dict):
            lst = extend_data.get("pic_url_list")
            if isinstance(lst, list):
                pic_list = [u for u in lst if isinstance(u, str) and u]

        if not pic_list:
            if isinstance(pic_url, str) and pic_url:
                pic_list = [pic_url]
            elif isinstance(pic_url, list):
                pic_list = [u for u in pic_url if isinstance(u, str) and u]

        # 最多 9 张
        pic_list = pic_list[:9]

        for u in pic_list:
            message.append({"type": "text", "data": {"text": "\n"}})
            # NapCat/OneBot 多实现对 url 更稳，file 兜底
            message.append({"type": "image", "data": {"url": u, "file": u}})

        if jump_url:
            message.append({
                "type": "text",
                "data": {"text": f"\n\n原文: {jump_url}"}
            })

        # at 仅在群聊中有效，私聊场景直接忽略避免不必要失败
        if self.at_qq and self.group_id:
            message.append({
                "type": "text",
                "data": {"text": "\n\n"}
            })
            message.append({
                "type": "at",
                "data": {
                    "qq": f"{self.at_qq}",
                }
            })

        payload = {
            "user_id": self.user_id,
            "group_id": self.group_id,
            "message": message
        }
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        api_endpoint = f"{self.api_url.rstrip('/')}/send_msg"

        try:
            response = util.requests_post(
                api_endpoint,
                self.name,
                headers=headers,
                data=json.dumps(payload)
            )

            if util.check_response_is_ok(response):
                resp_data = response.json()
                if resp_data.get("status") == "ok" and resp_data.get("retcode") == 0:
                    log.info(f"【推送_{self.name}】消息发送成功")
                    return True
                else:
                    error_msg = resp_data.get("message", "未知错误")
                    log.error(f"【推送_{self.name}】API返回错误: {error_msg}")
            else:
                if response is None:
                    log.error(f"【推送_{self.name}】请求失败，未收到响应（可能超时或连接异常）")
                else:
                    log.error(f"【推送_{self.name}】请求失败，状态码: {response.status_code}")

        except Exception as e:
            log.error(f"【推送_{self.name}】发送消息时出现异常: {str(e)}")
            return False

        return False
