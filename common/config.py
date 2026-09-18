import os

import yaml

from common.logger import log


class ConfigReaderForYml(object):
    def __init__(self, config_file_name="config.yml"):
        configured_path = os.environ.get("AIO_CONFIG_PATH", config_file_name)
        config_file_path = (
            configured_path
            if os.path.isabs(configured_path)
            else os.path.join(os.getcwd(), configured_path)
        )
        if not os.path.exists(config_file_path):
            raise FileNotFoundError(f"No such file: {config_file_path}")
        log.info(f"加载配置文件: {config_file_path}")
        with open(config_file_path, "r", encoding="utf-8") as file:
            self._config = yaml.safe_load(file)

    @staticmethod
    def _mask_sensitive(value):
        if isinstance(value, str):
            if len(value) <= 8:
                return "***"
            return f"{value[:4]}***{value[-4:]}"
        if isinstance(value, list):
            return [ConfigReaderForYml._mask_sensitive(item) for item in value]
        if isinstance(value, dict):
            return {
                key: ConfigReaderForYml._mask_sensitive(item)
                if any(marker in key.lower() for marker in ("cookie", "password", "secret", "token", "key"))
                else item
                for key, item in value.items()
            }
        return value

    @staticmethod
    def _summarize_list_values(config_item: dict) -> dict:
        summary = {}
        for key, value in config_item.items():
            if key in {"uid_list", "profile_id_list", "sec_uid_list", "room_id_list", "username_list", "douyin_id_list"}:
                summary[key] = value
            elif key == "target_push_name_list":
                summary[key] = value
        return summary

    def get_common_config(self) -> dict:
        result = self._config.get("common", {})
        common_summary = self._mask_sensitive(result)
        log.info(f"加载配置common(已脱敏): {common_summary}")
        return result

    def get_query_task_config(self) -> list:
        result = self._config.get("query_task", [])
        task_summaries = []
        for item in result:
            task_summaries.append({
                "name": item.get("name"),
                "type": item.get("type"),
                "enable": item.get("enable"),
                **self._summarize_list_values(item),
            })
        log.info(f"加载配置query_task(摘要): {task_summaries}")
        return result

    def get_push_channel_config(self) -> list:
        result = self._config.get("push_channel", [])
        channel_summaries = []
        for item in result:
            channel_summaries.append({
                "name": item.get("name"),
                "type": item.get("type"),
                "enable": item.get("enable"),
            })
        log.info(f"加载配置push_channel(摘要): {channel_summaries}")
        return result


global_config = ConfigReaderForYml()
