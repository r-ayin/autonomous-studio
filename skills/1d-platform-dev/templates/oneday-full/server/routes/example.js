const express = require('express');
const router = express.Router();

// 示例路由，替换为你的业务逻辑
router.get('/ping', (_req, res) => {
  res.json({ message: 'pong', timestamp: new Date().toISOString() });
});

module.exports = router;
