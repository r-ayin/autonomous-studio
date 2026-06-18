const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');

module.exports = {
  mode: 'development',
  entry: './src/index.jsx',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'bundle.js',
    publicPath: '/',
  },
  module: {
    rules: [
      {
        test: /\.jsx?$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: ['@babel/preset-env', '@babel/preset-react'],
          },
        },
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader'],
      },
    ],
  },
  resolve: { extensions: ['.js', '.jsx'] },
  devServer: {
    port: 3019,
    allowedHosts: ['all', '.alibaba-inc.com'],
    client: { overlay: false },
    historyApiFallback: {
      index: '/index.html',
      rewrites: [{ from: /^\/_p\/\d+\//, to: '/index.html' }],
    },
  },
  plugins: [new HtmlWebpackPlugin({ template: './index.html', inject: 'body' })],
};
