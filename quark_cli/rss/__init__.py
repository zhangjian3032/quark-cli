"""
RSS 订阅模块

提供 Feed 拉取、规则匹配、动作执行的完整 RSS 订阅引擎。

动作类型:
  - auto_save: 提取夸克链接 → 转存到网盘
  - torrent:   推送 torrent/magnet → qBittorrent
  - notify:    飞书 Bot 通知
  - log:       仅记录到历史
"""
