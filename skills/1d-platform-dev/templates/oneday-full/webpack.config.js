const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');

module.exports = {
  mode: 'development',
  entry: './src/index.tsx',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'bundle.js',
    publicPath: '/',
  },
  module: {
    rules: [
      {
        test: /\.(ts|tsx)$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: [
              ['@babel/preset-react', { development: true }],
              '@babel/preset-env',
              '@babel/preset-typescript',
            ],
          },
        },
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader', 'postcss-loader'],
      },
    ],
  },
  resolve: {
    extensions: ['.ts', '.tsx', '.js', '.jsx'],
    alias: { '@': path.resolve(__dirname, 'src') },
    fallback: { canvas: false, path: false, fs: false, stream: false },
  },
  devServer: {
    port: 3019,
    allowedHosts: ['all', '.alibaba-inc.com'],
    client: { overlay: false },
    historyApiFallback: {
      index: '/index.html',
      rewrites: [{ from: /^\/_p\/\d+\//, to: '/index.html' }],
    },
    proxy: [
      {
        context: ['/api', '/health'],
        target: 'http://localhost:9000',
        changeOrigin: true,
      },
    ],
  },
  plugins: [new HtmlWebpackPlugin({ template: './index.html', inject: 'body' })],
};
