import asyncio
import json
import os
import subprocess
import threading
import websockets

# 本番用のエンドポイント
PROD_URL = "wss://api.p2pquake.net/v2/ws"

# パス設定（環境に合わせて調整してください）
VOICE_PATH = "/usr/share/hts-voice/mei/mei_normal.htsvoice"
DIC_PATH = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
CHIME_PATH = "./Emergency_Alert01-2.mp3"
FIXED_ALERT_PATH = "./fixed_alert.wav"

# ==========================================
# ★【本番設定】通知したい地域と最低震度の設定
# ==========================================
# 気象庁の区分名（例: "京都府南部", "大阪府北部", "神奈川県東部" など）を指定してください。
TARGET_AREA = "京都府南部"
# 5弱 = 45 / 5強 = 50 / 6弱 = 55 / 6強 = 60 / 7 = 70
MIN_SCALE = 45


def init_fixed_audio():
    """起動時に固定音声ファイルがあるか確認し、なければ生成する"""
    if not os.path.exists(FIXED_ALERT_PATH):
        print(
            f"固定音声ファイル ({FIXED_ALERT_PATH}) が見つからないため、生成します..."
        )
        fixed_text = "緊急地震速報です。強い揺れに警戒してください。"
        cmd = f'echo "{fixed_text}" | open_jtalk -x {DIC_PATH} -m {VOICE_PATH} -ow {FIXED_ALERT_PATH}'
        subprocess.run(cmd, shell=True)
        print("固定音声ファイルの生成が完了しました。")


def scale_to_str(scale_int):
    """P2P地震情報の震度コードを日本語の文字列に変換する"""
    scale_map = {
        10: "1",
        20: "2",
        30: "3",
        40: "4",
        45: "5弱",
        50: "5強",
        55: "6弱",
        60: "6強",
        70: "7",
    }
    return scale_map.get(scale_int, "不明")


def play_alert_sequence(dynamic_text):
    """チャイム、固定音声、動的音声を順番に綺麗に繋げて再生する（別スレッドで実行）"""
    print(f"【再生シーケンス開始】詳細: {dynamic_text}")

    # 1. チャイムと固定音声を即座に連続再生
    cmd_fixed = f"mpg123 -q {CHIME_PATH} && aplay -q {FIXED_ALERT_PATH}"
    proc_fixed = subprocess.Popen(cmd_fixed, shell=True)

    # 2. 裏で動的テキストをWAVに変換
    tmp_wav = "/tmp/dynamic_alert.wav"
    cmd_gen = f'echo "{dynamic_text}" | open_jtalk -x {DIC_PATH} -m {VOICE_PATH} -ow {tmp_wav}'
    subprocess.run(cmd_gen, shell=True)

    # 3. チャイム＋固定音声の再生完了を待つ
    proc_fixed.wait()

    # 4. 続けて動的音声を再生
    if os.path.exists(tmp_wav):
        subprocess.run(f"aplay -q {tmp_wav}", shell=True)


def check_and_alert(data):
    """ターゲット地域が含まれており、かつ設定した震度以上か判定する"""
    earthquake = data.get("earthquake", {})
    areas = earthquake.get("areas", [])

    is_target_hit = False
    area_max_scale = 0

    # 警報対象のエリアをループして、ターゲット地域を探す
    for area in areas:
        if area.get("name") == TARGET_AREA:
            area_max_scale = area.get("maxScale", 0)
            # 設定した震度（例: 5弱＝45）以上か判定
            if area_max_scale >= MIN_SCALE:
                is_target_hit = True
                break

    if is_target_hit:
        print(
            f"【条件一致】{TARGET_AREA} で予想震度 {scale_to_str(area_max_scale)} を検知！再生を開始します。"
        )

        hypocenter = earthquake.get("hypocenter", {})
        place = hypocenter.get("name", "不明な震源")
        max_scale = scale_to_str(earthquake.get("maxScale", 0))

        # 読み上げる詳細文章
        dynamic_text = f"震源地は、{place}付近。全体の最大震度は、{max_scale}の予想です。"

        # メインループを止めないよう別スレッドで再生
        threading.Thread(target=play_alert_sequence, args=(dynamic_text,)).start()
    else:
        print(
            f"【条件不一致】緊急地震速報を受信しましたが、{TARGET_AREA} が対象外、または震度{scale_to_str(MIN_SCALE)}未満のためスルーします。"
        )


async def monitor_production():
    print(f"本番サーバー ({PROD_URL}) に接続します...")

    async with websockets.connect(PROD_URL) as websocket:
        print("本番サーバーに接続成功。緊急地震速報（警報）の受信待機中...")

        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)

                code = data.get("code")

                # 本番は554（緊急地震速報 警報）のみに反応させる
                if code == 554:
                    msg_time = data.get("time", "不明")
                    print(
                        f"[{msg_time}] 緊急地震速報（警報）を受信。条件をチェックします..."
                    )
                    check_and_alert(data)

            except websockets.ConnectionClosed:
                print("接続が切断されました。再接続します...")
                await asyncio.sleep(5)
                return await monitor_production()
            except Exception as e:
                print(f"エラー発生: {e}")
                await asyncio.sleep(5)


if __name__ == "__main__":
    init_fixed_audio()

    try:
        asyncio.run(monitor_production())
    except KeyboardInterrupt:
        print("\nモニタリングを終了しました。")
