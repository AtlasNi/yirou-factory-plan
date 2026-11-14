# 依柔工厂方案：个人账号分发

统一技能来源：https://github.com/AtlasNi/yirou-factory-plan 。本目录为该私有GitHub仓库的发布源码；仓库权限由维护者管理。

维护者修改原始技能或刷新工厂资源后，执行工作区中的 `python skill-maintenance/export_yirou_plugin.py`。脚本同步内容；内容改变时自动递增补丁版本，再将本目录提交并推送至统一仓库。只修改本机文件不会更新他人的安装副本。

使用者有仓库读取权限后，一次性添加安装来源：

```text
codex plugin marketplace add https://github.com/AtlasNi/yirou-factory-plan.git
```

然后在桌面应用插件目录中安装“依柔工厂方案”。私有仓库需要使用者有相应GitHub访问权限。后续刷新来源使用：

```text
codex plugin marketplace upgrade yirou-factory
```

客户端刷新安装内容后开启新任务。各个人客户端的刷新机制由其版本决定；本目录没有安装定时任务，也不能保证即时推送。若需要无人值守定时同步，须在各使用者自己的电脑另行配置，不能由维护者本机替其他电脑完成。

分发版包含工厂数据快照和10张配件图片，没有作者的GitHub凭证、站点ID或工作簿文件。可不依赖作者的本地Excel先用内置资源生成方案；AI图和在线发布仍需要使用者自己的可用工具和权限。首次公开发布由新使用者确认其自己的偏好。
