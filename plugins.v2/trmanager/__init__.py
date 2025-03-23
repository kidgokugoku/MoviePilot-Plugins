from typing import List, Dict, Any, Optional, Tuple
from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType, ServiceInfo
from apscheduler.triggers.cron import CronTrigger
from app.helper.downloader import DownloaderHelper
from app.modules.transmission import Transmission


class TrManager(_PluginBase):
    # 插件名称
    plugin_name = "TR做种管理"
    # 插件描述
    plugin_desc = "定时恢复TR下载器中已完成的暂停种子,删除未完成种子。"
    # 插件图标
    plugin_icon = "Transmission_A.png"
    # 插件版本
    plugin_version = "2.1.0"
    # 插件作者
    plugin_author = "kidgokugoku"
    # 作者主页
    author_url = "https://github.com/kidgokugoku/MoviePilot-Plugins"
    # 插件配置项ID前缀
    plugin_config_prefix = "trmanager_"
    # 加载顺序
    plugin_order = 99
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    _cron = None
    _notify = False
    _tr_name = None
    _tr = None
    _delete_incomplete = False
    _onlyonce = False
    downloader_helper = None

    def init_plugin(self, config: dict = None):
        self.downloader_helper = DownloaderHelper()
        if config:
            self._enabled = config.get("enabled")
            self._notify = config.get("notify")
            self._cron = config.get("cron")
            self._tr_name = config.get("tr_name")
            self._delete_incomplete = config.get("delete_incomplete")
            self._onlyonce = config.get("onlyonce")

            # 初始化下载器
            if self._tr_name:
                service = self.service_info(self._tr_name)
                if service and service.instance:
                    self._tr = service.instance

            # 如果启用了立即运行
            if self._enabled and self._onlyonce and self._tr:
                self.manage_torrents()
                # 运行后重置该标志
                self._onlyonce = False

    def service_info(self, name: str) -> Optional[ServiceInfo]:
        """
        获取下载器服务信息
        """
        if not name:
            logger.warning("尚未配置下载器，请检查配置")
            return None

        service = self.downloader_helper.get_service(name)
        if not service or not service.instance:
            logger.warning(f"获取下载器 {name} 实例失败，请检查配置")
            return None

        if service.instance.is_inactive():
            logger.warning(f"下载器 {name} 未连接，请检查配置")
            return None

        return service

    def get_state(self) -> bool:
        return True if self._enabled and self._cron and self._tr else False

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

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

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        downloader_options = [
            {"title": config.name, "value": config.name}
            for config in self.downloader_helper.get_configs().values()
        ]

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
                                            "model": "onlyonce",
                                            "label": "立即运行一次",
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
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "tr_name",
                                            "label": "Transmission下载器",
                                            "items": downloader_options,
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                ],
            }
        ], {
            "enabled": False,
            "notify": False,
            "cron": "0 */1 * * *",
            "delete_incomplete": False,
            "tr_name": "",
            "onlyonce": False,
        }

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

            # 处理未完成种子
            elif self._delete_incomplete and torrent.get("progress") == 0:
                if self._tr.delete_torrents(
                    delete_file=True, ids=[torrent.get("id")]
                ):
                    deleted_count += 1

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

            return []

        return torrents

    def get_page(self) -> List[dict]:
        pass

    def stop_service(self):
        """
        退出插件
        """
        pass
