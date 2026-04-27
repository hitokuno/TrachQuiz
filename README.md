# TrachQuiz (ゴミ分別クイズ)

市町村ごとのゴミ分別ルールを楽しく学べるクイズアプリです。
現在は「福島県会津若松市」のルールに対応しています。

## 特徴

- **JSONでルール管理**: `rules/` フォルダ内のJSONファイルを差し替えるだけで、他の市町村にも対応可能。
- **レスポンシブデザイン**: スマホでもPCでも快適に遊べます。

### 具体的な要件とデータソース

> 市町村ごとのルールファイルを設定することで複数の市町村に対応したい。会津若松市のルールファイルを作ってアプリを作ってください。ルールはこちら https://www.city.aizuwakamatsu.fukushima.jp/docs/2009120800017/

## 使い方

### 準備

**Windows 11 Only**

1. Pythonをインストール
   Microsoft Storeから「Python Install Manager」でインストール
   ![PythonInstallManager.png](images/PythonInstallManager.png)
2. Build Tools for Visual Studio
   1. [Build Tools for Visual Studio](https://visualstudio.microsoft.com/ja/downloads/?q=build+tools)からBuild Tools for Visual Studioをダウンロード
      ![DevTools.png](images/DevTools.png)
   2. 「C++によるデスクトップ開発」と「MSVC v143 - VS 2022 C++」にチェックを入れてインストール
      ![vs_BuildTools.png](images/vs_BuildTools.png)
3. Zadig
   1. [Zadig](http://zadig.akeo.ie/)をダウンロード
   2. NFCリーダーを接続
   3. ダウンロードしたzadig-2.9.exeを実行
   4. Options -> List All Devicesをクリック
      ![ListAll.png](images/ListAll.png)
   5. ACR122Uを選択
      ![selectDevuice.png](images/selectDevuice.png)
   6. Install Driverをクリック
4. libusb
   1. [libusb](https://libusb.info)をダウンロード (Downloads -> Latest Windows Binaries).
   2. libusb-1.0.29.7zを解凍
      [7zip](https://www.7-zip.org/download.html)など
   3. 下記ファイルをコピー
   - MS64\dll\libusb-1.0.dll → C:\Windows\System32
   - MS32\dll\libusb-1.0.dll → C:\Windows\SysWOW64

### 立ち上げ

1. ローカルサーバーを立ち上げます
   ```
   start_server.bat
   ```
2. `http://localhost:8000` にアクセスします。  
   　　画面をクリックして、サウンドを流します。

### 問題ファイル

問題ファイルはGoogle スプレッドシートで管理しています。
https://docs.google.com/spreadsheets/d/1B2DvuMOPC8roPZcZ_ojGAI1v9jsbw-REIFknZFl1NIQ/edit?usp=sharing

jsonファイルをダウンロードして、以下を更新してください。

easy.json:簡単  
normal.json:むずい

### NFCカードの登録

nfc_mapping.json を更新

## トラブルシューティング

以前動いていたのに、NFCリーダーが認識しなく(Closed)なる。
→ windows updateでドライバが元に戻った可能性があります。もう一度Zadigでドライバーをインストールしてください。

## ライセンス

MIT License
