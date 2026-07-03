import asyncio
import json
import os
import subprocess
import threading
import websockets

SANDBOX_URL = "wss://api-realtime-sandbox.p2pquake.net/v2/ws"

# パス設定
VOICE_PATH = "/usr/share/hts-voice/mei/mei_normal.htsvoice"
DIC_PATH = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
CHIME_PATH = "./test.mp3"
FIXED_ALERT_PATH = "./fixed_alert.wav"  # 起動時に自動生成される固定音声


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

    # 1. チャイムと固定音声を即座に連続再生（バックグラウンドで開始）
    cmd_fixed = f"mpg123 -q {CHIME_PATH} && aplay -q {FIXED_ALERT_PATH}"
    proc_fixed = subprocess.Popen(cmd_fixed, shell=True)

    # 2. 前半の音が鳴っている間に、裏で「地名とか」の動的テキストをWAVに変換（0.5秒ほどで終わる）
    tmp_wav = "/tmp/dynamic_alert.wav"
    cmd_gen = f'echo "{dynamic_text}" | open_jtalk -x {DIC_PATH} -m {VOICE_PATH} -ow {tmp_wav}'
    subprocess.run(cmd_gen, shell=True)

    # 3. チャイム＋固定音声の再生が終わるのをきっちり待つ
    proc_fixed.wait()

    # 4. 再生が終わったら、間髪入れずに生成した動的音声を再生
    if os.path.exists(tmp_wav):
        subprocess.run(f"aplay -q {tmp_wav}", shell=True)


def parse_and_speak(data, code):
    """受信データから地名や震度を抽出して、読み上げタスクを立ち上げる"""
    earthquake = data.get("earthquake", {})
    hypocenter = earthquake.get("hypocenter", {})

    place = hypocenter.get("name", "不明な震源")
    max_scale_code = earthquake.get("maxScale", 0)
    max_scale = scale_to_str(max_scale_code)

    # 動的に喋らせたいテキストを作成（地名とか）
    if code == 554:
        # 緊急地震速報（警報）用
        dynamic_text = f"震源地は、{place}付近。予想最大震度は、{max_scale}です。"
    else:
        # 地質情報（551）用（サンドボックスでのテスト用）
        dynamic_text = f"震源地は、{place}です。最大震度は、{max_scale}です。"

    # メインの受信ループを1ミリ秒も止めないように、再生処理は別スレッドに丸投げする
    threading.Thread(target=play_alert_sequence, args=(dynamic_text,)).start()


async def monitor_sandbox():
    print(f"サンドボックス ({SANDBOX_URL}) に接続します...")

    async with websockets.connect(SANDBOX_URL) as websocket:
        print("接続成功！データの受信を待機しています...")

        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)

                code = data.get("code")
                msg_time = data.get("time", "不明")

                print(f"[{msg_time}] データ受信 - Code: {code}")

                # テスト用に551（地震情報）と554（緊急地震速報）の両方に反応させる
                if code in [551, 554]:
                    print(f"★対象コード {code} を検知しました。処理を開始します。")
                    parse_and_speak(data, code)

            except websockets.ConnectionClosed:
                print("接続が切断されました。再接続します...")
                await asyncio.sleep(5)
                return await monitor_sandbox()
            except Exception as e:
                print(f"エラー発生: {e}")
                await asyncio.sleep(5)


if __name__ == "__main__":
    # 起動時に固定音声の存在チェック＆生成
    init_fixed_audio()

    try:
        asyncio.run(monitor_sandbox())
    except KeyboardInterrupt:
        print("\nモニタリングを終了しました。")
