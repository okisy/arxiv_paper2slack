# Lambdaの公式Pythonベースイメージを使用
FROM public.ecr.aws/lambda/python:3.9

# アプリケーションのコードを配置するディレクトリを作成
WORKDIR /var/task

# requirements.txtをコピー
COPY requirements.txt .

# # ビルド時と実行時の両方で、Linux/amd64のプラットフォームを使用するように指定
# # これにより、ローカルのOS（macOSなど）のアーキテクチャに影響されず、
# # Lambdaの実行環境（Linux/x86_64）に合ったバイナリが生成されます。
# RUN --mount=type=cache,target=/root/.cache/pip \
#     pip install -r requirements.txt --platform linux/amd64 --only-binary :all: --target .
# 依存関係をインストール
RUN pip install -r requirements.txt --target .

# アプリケーションのコードをコピー
COPY . .

# Lambdaハンドラを設定
CMD ["lambda_function.lambda_handler"]