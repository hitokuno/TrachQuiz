# NFCリーダーが動かないときの復旧手順

## 症状

前日まで動いていたのに、サーバー起動時に次のようなエラーが出てNFCタグを読めなくなる。

```text
TrachQuizServer - CRITICAL - NFC Worker fatal error: ... LIBUSB_ERROR_NOT_SUPPORTED [-12]
```

サーバー自体は起動し、`Uvicorn running on http://0.0.0.0:8000` も表示されるため、エラー行を見落としやすい。

## 原因

ACR122Uに当たっているドライバーがWinUSBではなくなると、libusbがリーダーを開けずにこのエラーになる。

Windows Updateなどでメーカー製や標準のドライバーに戻されることが主な原因と考えられる。USBポートを変えたときにも起こる場合がある。

メーカー製ドライバーを更新しても直らない。WinUSBに入れ直す。

## 復旧手順

1. NFCリーダーを、いつものUSBポートに直接挿す（ハブは避ける）。
2. サーバーが起動中なら止める。
3. `zadig-2.9.exe` を起動する。
4. **Options → List All Devices** にチェックを入れる。

   ![List All Devices](public/images/ListAll.png)

5. 一覧から **ACR122U** を選ぶ。複数出る場合は下の画像と同じ項目を選ぶ。

   ![ACR122Uを選択](public/images/selectDevuice.png)

6. 右側のドライバーを **WinUSB** にして、**Install Driver**（または **Replace Driver**）をクリックする。
7. リーダーを挿し直し、サーバーを起動する。

## 復旧の確認

ログに次の行が出ればよい。ログは `log/server.log` にも記録される。

```text
TrachQuizServer - INFO - NFC Reader opened: ACS ACR122U PN532v1.6 at usb:...
```

その後、タグをかざして `UID detected:` が出ることを確認する。

## それでも直らないとき

1. `C:\Windows\System32\libusb-1.0.dll` があるか確認する。なければ [README](README.md) の手順でコピーし直す。
2. 別のUSBポートに挿し替えて、復旧手順をやり直す。
3. **Smart Card** サービスを停止して、サーバーを起動し直す。

## 再発を減らす設定

完全に防げるとは限らない。また、どちらの設定も他の機器のドライバー更新にも影響する。

### Windows Updateからドライバーを受け取らない（Windows Pro）

1. `gpedit.msc` を起動する。
2. **コンピューターの構成 → 管理用テンプレート → Windows コンポーネント → Windows Update → Windows Update から提供される更新プログラムの管理** を開く。
3. **Windows 更新プログラムにドライバーを含めない** を **有効** にする。

Windowsのバージョンによって項目の場所が異なる場合がある。

### デバイスのインストール設定を変更する（Windows Home / Pro）

1. `sysdm.cpl` を起動する。
2. **ハードウェア → デバイスのインストールの設定** を開く。
3. **いいえ（デバイスが期待どおりに機能しない可能性があります）** を選ぶ。

### イベント前の確認

ドライバーが戻っていても、サーバーの起動ログで分かる。本番前に一度サーバーを起動し、`NFC Reader opened` が出ることを確認する。Zadigをすぐ実行できるよう、`zadig-2.9.exe` は端末内に残しておく。
