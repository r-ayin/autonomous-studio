const express = require('express');
const cors = require('cors');

const app = express();
const PORT = 9000;

app.use(cors());
app.use(express.json({ limit: '10mb' }));

// 健康检查（OneDay 平台探测用）
app.get('/health', (_req, res) => res.json({ status: 'ok' }));

// 在此处注册你的路由
// const myRoutes = require('./routes/my-routes');
// app.use('/api/my-routes', authMiddleware, myRoutes);

app.listen(PORT, () => {
  console.log(`Express server running on http://localhost:${PORT}`);
});
