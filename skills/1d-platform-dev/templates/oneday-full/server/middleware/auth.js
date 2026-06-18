const { expressjwt: jwt } = require('express-jwt');
const jwksRsa = require('jwks-rsa');

// OneDay 平台 JWT 鉴权中间件（使用平台公钥自动验签）
const authMiddleware = jwt({
  secret: jwksRsa.expressJwtSecret({
    cache: true,
    rateLimit: true,
    jwksRequestsPerMinute: 3,
    jwksUri: 'https://1d.alibaba-inc.com/.well-known/jwks.json',
  }),
  algorithms: ['RS256'],
});

module.exports = authMiddleware;
