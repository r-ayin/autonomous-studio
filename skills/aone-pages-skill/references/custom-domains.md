# 自定义域名参考

当用户需要使用独立域名，而不是 `https://<site-name>.io.alibaba-inc.com` 时使用本参考。

## 必要步骤

1. 在 `https://fs.alibaba-inc.com/#/ingressManage` 申请统一接入。
2. 在 Ingress 申请中：
   - 域名填写目标自定义域名。
   - `vipserver-key` 填写 `aone-pages.vipserver`。
   - 统一接入集群优先选择 `集团办公网（alibaba-work）`。
3. 在 Code 仓库中打开 `设置` -> `Pages`。
4. 设置 `自定义域名`。

## 注意事项

- 编写自定义域名文档时，不要省略统一接入申请步骤。
- 保留默认 Pages 域名作为兜底访问格式：`https://<site-name>.io.alibaba-inc.com`。
