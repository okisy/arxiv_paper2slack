# Lambdaの公式Pythonベースイメージを使用
FROM public.ecr.aws/lambda/python:3.12

# アプリケーションのコードを配置するディレクトリを作成
WORKDIR /var/task

# requirements.txtをコピー
COPY requirements.txt .

# 依存関係をインストール
RUN pip install -r requirements.txt --target .

# アプリケーションのコードをコピー
COPY . .

# Lambdaハンドラを設定
CMD ["lambda_function.lambda_handler"]