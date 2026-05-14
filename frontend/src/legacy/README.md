# Legacy Frontend Files

当前 frontend 已进入：

```text
Phase-2.7D Governance Runtime Cockpit
```

正式入口：

```jsx
frontend/main.jsx -> App2_7D.jsx
```

以下文件属于历史兼容文件：

- App.jsx

禁止继续向旧入口增加：

- governance runtime
- replay runtime
- source trace
- execution audit
- acceptance runtime

后续所有 Runtime Cockpit 修改：

```text
统一进入 App2_7D.jsx
```

---

当前原则：

- App.jsx = legacy compatibility only
- App2_7D.jsx = active runtime cockpit
