# SKLive2
Super-Kamiokande 3D Live on Raspberry Pi

<p align="center">
  <img src="sklive_demo2.gif">
</p>

## Description
東京大学宇宙線研究所が公開している[リアルタイムデータ](https://www-sk.icrr.u-tokyo.ac.jp/realtimemonitor/)を解析し、スーパーカミオカンデ内部の PMT（光電子増倍管）配置に合わせてイベントをプロットします。
<br>Raspberry Pi & 5インチモニタ の構成で科学インテリアになります
## Features
* 10秒ごとに最新データを自動取得。
* 待機中もタッチ操作で 3D 円柱を自由に回転可能。

## Requirements
* Raspberry Pi 4 / 5
* DSI タッチモニター (5inch 480x800を使用)
* Python 3.10+
* 依存ライブラリ: `pandas`, `numpy`, `matplotlib`, `requests`, `Pillow`
* [ライブラリ一覧 libs.txt](libs.txt)

## Installation
```bash
pip install -r libs.txt  # ライブラリインストール
python sklive2.py  # 実行
```

## Technical Challenges (開発のポイント)
### 1. PMT座標の抽出
ソースとなる配信データは数値(CSV)ではなく、[平面のgif画像](https://www-sk.icrr.u-tokyo.ac.jp/realtimemonitor/skev.gif)です。
<img width="564" height="325" src="skev_sample.gif">
難点として、配信されるgif画像サイズは日によって変わるようで、PMTの画像上の(x,y)座標も固定ではありません。<br>
そのため、プログラム開始時に、```cv2.connectedComponentsWithStats()```で座標マップを取得し、plots2.csvにリストを作ることを実施しました。<br>
