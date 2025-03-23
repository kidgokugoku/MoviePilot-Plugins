from typing import List, Dict, Any
from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType
from apscheduler.triggers.cron import CronTrigger
from app.modules.transmission import Transmission


class TrManager(_PluginBase):
    # 插件名称
    plugin_name = "TR做种管理"
    # 插件描述
    plugin_desc = "定时恢复TR下载器中已完成的暂停种子,删除未完成种子。"
    # 插件图标
    plugin_icon = "Transmission_A.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "kidgokugoku"
    # 作者主页
    author_url = "https://github.com/kidgokugoku/MoviePilot-Plugins"
    # 插件配置项ID前缀
    plugin_config_prefix = "trmanager_"
    # 加载顺序
    plugin_order = 1
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    _cron = None
    _notify = False
    _tr = None
    _delete_incomplete = False

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
            self._notify = config.get("notify")
            self._cron = config.get("cron")
            self._delete_incomplete = config.get("delete_incomplete")
            self._tr = Transmission()

    def get_state(self) -> bool:
        return True if self._enabled and self._cron else False

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务
        """
        if self.get_state():
            return [
                {
                    "id": "TrManager",
                    "name": "TR做种管理服务",
                    "trigger": CronTrigger.from_crontab(self._cron),
                    "func": self.manage_torrents,
                    "kwargs": {},
                }
            ]
        return []

    def get_form(self) -> List[dict]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "notify",
                                            "label": "发送通知",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "cron",
                                            "label": "执行周期",
                                            "placeholder": "0 */1 * * *",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "delete_incomplete",
                                            "label": "删除未完成种子",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                ],
            }
        ]

    def manage_torrents(self):
        """
        管理种子
        """
        if not self._enabled or not self._tr:
            return

        logger.info("开始TR做种管理...")

        # 获取所有种子
        all_torrents = self.get_all_torrents()
        if not all_torrents:
            return

        # 统计数据
        resumed_count = 0
        deleted_count = 0

        for torrent in all_torrents:
            # 处理已完成的暂停种子
            if (
                torrent.get("progress") == 100
                and torrent.get("state") == "stopped"
            ):
                if self._tr.start_torrents(ids=[torrent.get("id")]):
                    resumed_count += 1
                    logger.info(f"已恢复种子: {torrent.get("name")}")

            # 处理未完成种子
            elif self._delete_incomplete and torrent.get("progress") < 100:
                if self._tr.delete_torrents(
                    delete_file=True, ids=[torrent.get("id")]
                ):
                    deleted_count += 1
                    logger.info(f"已删除未完成种子: {torrent.get("name")}")

        # 发送通知
        if self._notify:
            self.post_message(
                mtype=NotificationType.SiteMessage,
                title="【TR做种管理任务执行完成】",
                text=f"共恢复 {resumed_count} 个暂停种子\n"
                f"共删除 {deleted_count} 个未完成种子",
            )

        logger.info("TR做种管理执行完成")

    def get_all_torrents(self):
        """
        获取所有种子
        """
        torrents, error = self._tr.get_torrents()
        if error:
            logger.error(f"获取TR种子失败: {error}")
            if self._notify:
                self.post_message(
                    mtype=NotificationType.SiteMessage,
                    title="【TR做种管理】",
                    text="获取TR种子失败，请检查TR配置",
                )
            return []

        if not torrents:
            logger.warning("TR没有种子")
            if self._notify:
                self.post_message(
                    mtype=NotificationType.SiteMessage,
                    title="【TR做种管理】",
                    text="TR中没有种子",
                )
            return []

        return torrents
