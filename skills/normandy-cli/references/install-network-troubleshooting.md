# 安装阶段网络异常排查

只有在 `normandy` 尚未安装、执行安装命令时持续报网络错误，并且多次重试后仍失败时，才读取这个文件。

## 进入条件

- 安装命令是：
  ```bash
  uv tool install --index-url http://artlab.alibaba-inc.com/1/pypi/simple normandy-cli
  ```
- 报错表现类似超时、`500`、连接失败、下载失败
- 持续重试仍无法通过

不要在普通业务命令报错、鉴权失败或 CLI 升级问题时误用这个排查路径。

## 连通性检查

先执行：

```bash
ping -c 3 n.alibaba-inc.com
ping -c 3 www.alibaba.com
```

## 结果判定

- `n.alibaba-inc.com` 无法 ping 通，但 `www.alibaba.com` 可以 ping 通：高度怀疑本地启用了网络代理，但没有对白名单放行 `alibaba-inc.com`
- 两个都无法 ping 通：更像是整体网络不可用，不要直接套用 `no_proxy` 方案
- `n.alibaba-inc.com` 可以 ping 通：不是这个典型代理白名单问题，返回原始报错并继续做其他网络排查

## 解决方案

当且仅当 `n.alibaba-inc.com` 不通、`www.alibaba.com` 能通时，给出或执行下面的修复：

```bash
export no_proxy=localhost,127.0.0.1,.alibaba-inc.com,.aliyun.com,10.0.0.0/8
```

如果需要持久化，追加到当前 shell 的配置文件，然后重新加载配置。

## Shell 配置文件选择

根据当前 shell 选择配置文件：

- `zsh`：优先 `~/.zshrc`
- `bash`：优先 `~/.bashrc`；如果是 macOS 登录 shell 且没有 `~/.bashrc`，再看 `~/.bash_profile`

如果用户明确要求你直接修复：

1. 先在当前会话执行一次 `export no_proxy=...`
2. 再把同一行追加到合适的 shell 配置文件
3. 最后根据当前 shell 执行一次 `source`，例如：
   ```bash
   source ~/.zshrc
   ```

只有在已经确认 shell 类型和配置文件存在时，才直接执行 `source`；否则先说明你准备使用哪个配置文件。

## 回答方式

默认给出最小闭环：

1. 两条 `ping` 检查命令
2. 一句判定逻辑
3. `export no_proxy=...`
4. 一个与当前 shell 匹配的 `source` 示例

不要把这个问题误解释成 Normandy 服务端故障，除非连通性检查不能支持代理白名单这个判断。
