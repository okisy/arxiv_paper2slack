# arxiv_paper2slack

ArxivのオープンAPIを使って論文を探して、ChatGPTに要約してもらった文章をSlackのbotに投げてもらうコードです。

ローカルで実行してみたい場合は、まず以下で[uv](https://github.com/astral-sh/uv)を使って必要なライブラリをインストールします。

```
$ uv pip install -r requirements.txt
```
* TODO: uvでpythonのバージョンを変える話と，uvのインストールの話を追記する


その後、以下で実行してください。

```
$ python paper_arxiv.py
```

クラウドで実行したい場合は[こちらのサイト](https://gammasoft.jp/blog/schdule-running-python-script-by-serverless/)を参考にしてmain.pyとrequirements.txtを使用してください。

