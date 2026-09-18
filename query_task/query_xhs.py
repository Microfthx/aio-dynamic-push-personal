import json
import html as html_lib
import re
import time
from collections import deque
from pathlib import Path

from bs4 import BeautifulSoup

from common import util
from common.logger import log
from common.proxy import my_proxy
from query_task import QueryTask


class QueryXhs(QueryTask):
    def __init__(self, config):
        super().__init__(config)
        self.profile_id_list = config.get("profile_id_list", [])
        self.cookie = config.get("cookie", "")

    def query(self):
        if not self.enable:
            return
        try:
            current_time = time.strftime("%H:%M", time.localtime(time.time()))
            if self.begin_time <= current_time <= self.end_time:
                my_proxy.current_proxy_ip = my_proxy.get_proxy(proxy_check_url="https://www.xiaohongshu.com/")
                if self.enable_dynamic_check:
                    for profile_id in self.profile_id_list:
                        self.query_dynamic(profile_id)
        except Exception as e:
            log.error(f"【小红书-查询任务-{self.name}】出错：{e}", exc_info=True)

    def query_dynamic(self, profile_id=None):
        if profile_id is None:
            return
        query_url = f"https://www.xiaohongshu.com/user/profile/{profile_id}?exSource="
        headers = self.get_headers()
        if self.cookie != "":
            headers["cookie"] = self.cookie
        response = util.requests_get(query_url, f"小红书-查询动态状态-{self.name}", headers=headers, use_proxy=True)
        if util.check_response_is_ok(response):
            html_text = response.text
            self._log_response_summary(
                response=response,
                html_text=html_text,
                module_name=f"小红书-查询动态状态-{self.name}",
                target_id=profile_id,
            )
            result = self._extract_initial_state(html_text, f"小红书-查询动态状态-{self.name}", profile_id)

            if result is None:
                self._dump_debug_html(profile_id, html_text, reason="missing_initial_state")
                log.warning(f"【小红书-查询动态状态-{self.name}】本次响应缺少状态数据，跳过检测，profile_id：{profile_id}")
            else:
                user_info = self._extract_user_info(result, profile_id, html_text=html_text)
                if user_info is None:
                    return

                user_name = user_info["user_name"]
                user_desc = user_info["user_desc"]
                avatar_url = user_info["avatar_url"]
                notes = user_info["notes"]

                if user_name == profile_id:
                    self._dump_debug_html(profile_id, html_text, user_name=user_name, user_desc=user_desc, reason="missing_user_name")

                if len(notes) == 0:
                    super().handle_for_result_null("-1", profile_id, "小红书", user_name)
                    return

                # 循环遍历 notes ，剔除不满足要求的数据
                notes = [note for note in notes if
                         note.get("noteCard") is not None  # 跳过不包含 noteCard 的数据
                         and (note["noteCard"].get("interactInfo") is None or note["noteCard"]["interactInfo"].get("sticky") is not True)  # 跳过置顶
                         ]

                # 跳过置顶后再判断一下，防止越界
                if len(notes) == 0:
                    super().handle_for_result_null("-1", profile_id, "小红书", user_name)
                    return

                note = notes[0]
                note_card = note.get("noteCard") or {}
                note_title = note_card.get("displayTitle")
                if note_title is None:
                    log.error(f"【小红书-查询动态状态-{self.name}】笔记标题缺失，profile_id：{profile_id}，user_name：{user_name}")
                    return

                if self.dynamic_dict.get(profile_id, None) is None:
                    self.dynamic_dict[profile_id] = deque(maxlen=self.len_of_deque)
                    for index in range(self.len_of_deque):
                        if index < len(notes):
                            current_note_card = notes[index].get("noteCard") or {}
                            current_title = current_note_card.get("displayTitle")
                            if current_title is not None:
                                self.dynamic_dict[profile_id].appendleft(current_title)
                    log.info(f"【小红书-查询动态状态-{self.name}】【{user_name}】动态初始化：{self.dynamic_dict[profile_id]}")
                    return

                if note_title not in self.dynamic_dict[profile_id]:
                    previous_note_title = self.dynamic_dict[profile_id].pop()
                    self.dynamic_dict[profile_id].append(previous_note_title)
                    log.info(f"【小红书-查询动态状态-{self.name}】【{user_name}】上一条动态标题[{previous_note_title}]，本条动态标题[{note_title}]")
                    self.dynamic_dict[profile_id].append(note_title)
                    log.debug(self.dynamic_dict[profile_id])

                    note_desc = ''
                    dynamic_time = '无法获取内容，请打开小红书查看详情'

                    content = f"【{note_title}】{note_desc}"
                    pic_url = self._extract_cover_url(note_card, profile_id, user_name)
                    if pic_url is None:
                        log.error(f"【小红书-查询动态状态-{self.name}】封面获取失败，profile_id：{profile_id}，user_name：{user_name}")
                        return
                    jump_url = f"https://www.xiaohongshu.com/user/profile/{profile_id}"
                    log.info(f"【小红书-查询动态状态-{self.name}】【{user_name}】动态有更新，准备推送：{content[:30]}")
                    self.push_for_xhs_dynamic(
                        user_name,
                        note_title,
                        content,
                        pic_url,
                        jump_url,
                        dynamic_time,
                        dynamic_raw_data=note,
                        avatar_url=avatar_url,
                        user_desc=user_desc,
                    )

    def get_note_detail(self, note_id=None):
        if note_id is None:
            return None
        query_url = f"https://www.xiaohongshu.com/explore/{note_id}"
        headers = self.get_headers()
        response = util.requests_get(query_url, f"小红书-查询动态明细-{self.name}", headers=headers, use_proxy=True)
        if util.check_response_is_ok(response):
            html_text = response.text
            self._log_response_summary(
                response=response,
                html_text=html_text,
                module_name=f"小红书-查询动态明细-{self.name}",
                target_id=note_id,
            )
            result = self._extract_initial_state(html_text, f"小红书-查询动态明细-{self.name}", note_id)

            if result is None:
                log.warning(f"【小红书-查询动态明细-{self.name}】本次响应缺少状态数据，跳过检测，note_id：{note_id}")
            else:
                note = result["note"]
                if note is None:
                    return None
                return note["noteDetailMap"][note["firstNoteId"]]["note"]

    @staticmethod
    def _extract_initial_state(html_text=None, module_name=None, target_id=None):
        if html_text is None:
            return None

        soup = BeautifulSoup(html_text, "html.parser")
        scripts = soup.find_all("script")
        for script in scripts:
            script_text = script.string or script.get_text()
            if not script_text or "window.__INITIAL_STATE__" not in script_text:
                continue

            raw_json = QueryXhs._extract_json_after_assignment(script_text, "window.__INITIAL_STATE__")
            if raw_json is None:
                continue

            try:
                return json.loads(raw_json.replace("undefined", "null"))
            except Exception as e:
                log.error(f"【{module_name}】json解析错误，target_id：{target_id}，error：{e}")
                return None

        log.warning(f"【{module_name}】未找到 window.__INITIAL_STATE__，target_id：{target_id}")
        return None

    @staticmethod
    def _extract_json_after_assignment(script_text=None, variable_name=None):
        if not script_text or not variable_name:
            return None

        start = script_text.find(variable_name)
        if start < 0:
            return None

        equals_index = script_text.find("=", start + len(variable_name))
        if equals_index < 0:
            return None

        json_start = script_text.find("{", equals_index + 1)
        if json_start < 0:
            return None

        in_string = False
        escaped = False
        depth = 0
        for index in range(json_start, len(script_text)):
            char = script_text[index]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return script_text[json_start:index + 1]
        return None

    @staticmethod
    def _log_response_summary(response=None, html_text=None, module_name=None, target_id=None):
        if response is None or html_text is None:
            return

        head = html_text[:500].replace("\n", "\\n").replace("\r", "\\r")
        markers = {
            "initial_state": "window.__INITIAL_STATE__" in html_text,
            "user_name": "user-name" in html_text,
            "basicInfo": "basicInfo" in html_text,
            "userPageData": "userPageData" in html_text,
            "verify": "verify" in html_text.lower(),
            "login": "login" in html_text.lower(),
            "403": "403" in html_text,
        }
        log.info(
            f"【{module_name}】响应摘要，target_id：{target_id}，"
            f"status={getattr(response, 'status_code', None)}，url={getattr(response, 'url', None)}，"
            f"len={len(html_text)}，markers={markers}，head={head}"
        )

    def _extract_user_info(self, result=None, profile_id=None, html_text=None):
        if result is None:
            return None

        def pick_field(*candidates):
            for value, source in candidates:
                if value not in (None, ""):
                    return value, source
            return None, None

        user = result.get("user")
        if not isinstance(user, dict):
            log.error(f"【小红书-查询动态状态-{self.name}】用户数据缺失，profile_id：{profile_id}，keys：{list(result.keys())}")
            return None

        user_page_data = user.get("userPageData")
        if not isinstance(user_page_data, dict):
            user_page_data = {}

        basic_info = user_page_data.get("basicInfo")
        if not isinstance(basic_info, dict):
            basic_info = {}

        user_info = user.get("userInfo")
        if not isinstance(user_info, dict):
            user_info = {}

        user_name, user_name_source = pick_field(
            (basic_info.get("nickname"), "basicInfo.nickname"),
            (user_page_data.get("nickname"), "userPageData.nickname"),
            (user_info.get("nickname"), "userInfo.nickname"),
            (user_info.get("nickName"), "userInfo.nickName"),
            (user_info.get("name"), "userInfo.name"),
            (user_info.get("screenName"), "userInfo.screenName"),
            (user.get("nickname"), "user.nickname"),
            (basic_info.get("name"), "basicInfo.name"),
            (basic_info.get("userName"), "basicInfo.userName"),
            (profile_id, "profile_id"),
        )

        avatar_url, avatar_source = pick_field(
            (basic_info.get("images"), "basicInfo.images"),
            (user_page_data.get("images"), "userPageData.images"),
            (user_info.get("avatar"), "userInfo.avatar"),
            (user_info.get("avatarUrl"), "userInfo.avatarUrl"),
            (user_info.get("images"), "userInfo.images"),
            (user.get("images"), "user.images"),
        )

        user_desc, desc_source = pick_field(
            (basic_info.get("desc"), "basicInfo.desc"),
            (user_info.get("desc"), "userInfo.desc"),
            (user_page_data.get("desc"), "userPageData.desc"),
            (user.get("desc"), "user.desc"),
        )

        if user_name == profile_id and html_text:
            profile_name, profile_name_source = self._extract_profile_text_info(html_text)
            if profile_name:
                user_name, user_name_source = profile_name, profile_name_source

            profile_desc = self._extract_profile_desc_text(html_text)
            if profile_desc:
                user_desc, desc_source = profile_desc, "html.user-desc"

        if user_name == profile_id:
            log.info(
                f"【小红书-查询动态状态-{self.name}】未解析到昵称，profile_id：{profile_id}，"
                f"userPageData keys：{list(user_page_data.keys())}，userInfo keys：{list(user_info.keys())}"
            )
        else:
            log.info(
                f"【小红书-查询动态状态-{self.name}】用户信息解析成功，profile_id：{profile_id}，"
                f"nickname[{user_name}]<-{user_name_source}，"
                f"desc[{user_desc}]<-{desc_source}，"
                f"avatar_source={avatar_source}"
            )

        notes_container = user.get("notes")
        if isinstance(notes_container, list) and len(notes_container) > 0 and isinstance(notes_container[0], list):
            notes = notes_container[0]
        elif isinstance(notes_container, list):
            notes = notes_container
        else:
            log.error(
                f"【小红书-查询动态状态-{self.name}】notes结构异常，profile_id：{profile_id}，"
                f"notes_type：{type(notes_container)}"
            )
            notes = []

        return {
            "user_name": user_name,
            "user_desc": user_desc,
            "avatar_url": avatar_url,
            "notes": notes,
        }

    def _dump_debug_html(self, profile_id=None, html_text=None, user_name=None, user_desc=None, reason=None):
        if not html_text:
            return

        debug_dir = Path(__file__).resolve().parents[1] / "docs"
        debug_dir.mkdir(parents=True, exist_ok=True)
        debug_path = debug_dir / f"xhs_debug_{profile_id}.html"
        try:
            debug_path.write_text(html_text, encoding="utf-8")
            log.info(
                f"【小红书-查询动态状态-{self.name}】已落盘调试HTML：{debug_path}，"
                f"reason={reason}，"
                f"contains_user_name={'user-name' in html_text}，contains_basicInfo={'basicInfo' in html_text}，"
                f"contains_userPageData={'userPageData' in html_text}，user_desc={user_desc}"
            )
        except Exception as e:
            log.error(f"【小红书-查询动态状态-{self.name}】落盘调试HTML失败，profile_id：{profile_id}，error：{e}")

    @staticmethod
    def _extract_profile_text_info(html_text=None):
        if not html_text:
            return None, None

        patterns = [
            (r'<div class="user-name"[^>]*>\s*([^<\n]+?)\s*(?:<!---->)?\s*</div>', "html.user-name"),
            (r'<span class="user-name"[^>]*>\s*([^<\n]+?)\s*(?:<!---->)?\s*</span>', "html.user-name"),
            (r'<h1[^>]*class="[^"]*user-name[^"]*"[^>]*>\s*([^<\n]+?)\s*</h1>', "html.user-name"),
        ]
        for pattern, source in patterns:
            match = re.search(pattern, html_text, re.S)
            if match:
                value = html_lib.unescape(match.group(1)).strip()
                if value:
                    return value, source
        return None, None

    @staticmethod
    def _extract_profile_desc_text(html_text=None):
        if not html_text:
            return None

        patterns = [
            r'<div class="user-desc"[^>]*>\s*([^<]+(?:<br\s*/?>[^<]+)*)\s*</div>',
            r'<div class="user-desc"[^>]*>\s*([\s\S]*?)\s*</div>',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_text, re.S)
            if match:
                value = html_lib.unescape(match.group(1))
                value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
                value = re.sub(r"<!--.*?-->", "", value, flags=re.S)
                value = re.sub(r"<[^>]+>", "", value).strip()
                if value:
                    return value
        return None

    @staticmethod
    def _extract_cover_url(note_card=None, profile_id=None, user_name=None):
        if not isinstance(note_card, dict):
            return None
        cover = note_card.get("cover")
        if not isinstance(cover, dict):
            return None
        info_list = cover.get("infoList")
        if not isinstance(info_list, list) or len(info_list) == 0:
            return None
        for item in reversed(info_list):
            if isinstance(item, dict) and item.get("url"):
                return item["url"]
        return None

    @staticmethod
    def get_headers():
        return {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "sec-ch-ua": "'Google Chrome';v='119', 'Chromium';v='119', 'Not?A_Brand';v='24'",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "'macOS'",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1"
        }

    def push_for_xhs_dynamic(
        self,
        username=None,
        note_title=None,
        content=None,
        pic_url=None,
        jump_url=None,
        dynamic_time=None,
        dynamic_raw_data=None,
        avatar_url=None,
        user_desc=None,
    ):
        """
        小红书动态提醒推送
        :param username: 博主名
        :param note_title: 笔记标题
        :param content: 动态内容
        :param pic_url: 图片地址
        :param jump_url: 跳转地址
        :param dynamic_time: 动态发送时间
        :param dynamic_raw_data: 动态原始数据
        :param avatar_url: 头像url
        """
        if username is None or note_title is None or content is None:
            log.error(f"【小红书-动态提醒推送-{self.name}】缺少参数，username:[{username}]，note_title:[{note_title}]，content:[{content[:30]}]")
            return
        title = f"【小红书】【{username}】发动态了"
        content = f"{content[:100] + (content[100:] and '...')}[{dynamic_time}]"
        extend_data = {
            'dynamic_raw_data': dynamic_raw_data,
            'avatar_url': avatar_url,
            'user_desc': user_desc,
        }
        super().push(title, content, jump_url, pic_url, extend_data=extend_data)
