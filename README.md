# arxiv_paper2slack

## 概要
ArxivのオープンAPIを使って論文を探して、ChatGPTに要約してもらった文章をSlackのbotに投げてもらうコードです。

## ローカルでの環境構築
ローカルで実行してみたい場合は、まず以下で[uv](https://github.com/astral-sh/uv)を使って必要なライブラリをインストールします。

```
$ uv pip install -r requirements.txt
```


その後、以下で実行してください。

```
$ python lambda_function.py
```

## 環境構築関連（AWS）

### ECRへのDockerイメージのプッシュとLambdaでの設定 🚀

このセクションでは、作成したDockerイメージをAmazon ECRにプッシュし、Lambda関数としてデプロイする手順を説明します。

-----

### 1\. ECRへのイメージプッシュ

まず、ローカルでビルドしたDockerイメージをAmazon ECR (Elastic Container Registry) にアップロードします。

#### a. Dockerイメージのビルド

以下のコマンドを実行して、Lambdaの実行環境である`linux/amd64`アーキテクチャに合わせたイメージをビルドします。

```bash
docker build --platform linux/amd64 -t arxiv-notifier .
```

  - **補足**: `docker build`コマンドに`--platform linux/amd64`フラグを追加することで、ローカル環境（例：M1/M2 Mac）のアーキテクチャに関係なく、Lambdaで動作する正しいバイナリが生成されます。

#### b. ECRへの認証とタグ付け

AWS CLIを使ってDockerをECRに認証させ、イメージにタグを付けます。

```bash
# 認証情報を設定（初回のみ）
aws configure

# ECRにDockerクライアントを認証
aws ecr get-login-password --region <your-region> | docker login --username AWS --password-stdin <your-aws-account-id>.dkr.ecr.<your-region>.amazonaws.com

# イメージにタグを付ける
docker tag arxiv-notifier:latest <your-aws-account-id>.dkr.ecr.<your-region>.amazonaws.com/arxiv-notifier:latest
```

  - **補足**: `aws configure`でAWSのアクセスキーとリージョンを設定しておかないと、認証コマンドは失敗します。

#### c. ECRへのプッシュ

タグ付けしたイメージをECRにプッシュします。

```bash
docker push <your-aws-account-id>.dkr.ecr.<your-region>.amazonaws.com/arxiv-notifier:latest
```

-----

### 2\. AWS Lambdaでの設定

ECRにイメージをプッシュしたら、Lambdaコンソールで関数を作成します。

#### a. Lambda関数の作成

  - AWS Lambdaコンソールで「**関数の作成**」をクリックします。
  - 「**コンテナイメージ**」を選択し、関数名を入力します。
  - 「**コンテナイメージの参照**」をクリックし、ECRにプッシュしたイメージを選択して「**作成**」します。

#### b. 環境変数の設定

日本語の文字（例：論文のタイトル）を扱う場合、文字コード関連のエラーを防ぐために環境変数を設定します。

  - Lambda関数の「**設定**」タブの「**環境変数**」セクションで、「**編集**」をクリックします。
  - 以下のキーと値を追加します。
      - **キー**: `LANG`
      - **値**: `C.UTF-8`

#### c. 実行時間の延長

デフォルトのタイムアウト時間では処理が完了しない場合があります。

  - Lambda関数の「**設定**」タブの「**一般設定**」セクションで、「**編集**」をクリックします。
  - 「**タイムアウト**」を任意の値（例：1分以上）に設定します。

-----

### 3\. 定期実行の設定（オプション）

Lambda関数を定期的に実行したい場合は、Amazon EventBridge（旧CloudWatch Events）でスケジュールルールを設定します。

  - Amazon EventBridgeのコンソールで「**ルールを作成**」をクリックします。
  - スケジュールを設定し、ターゲットとして作成したLambda関数を選択します。