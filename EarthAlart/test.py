import asyncio
import json
import subprocess
import websockets

SANDBOX_URL = "wss://api-realtime-sandbox.p2pquake.net/v2/ws"

# 音声モデルのパス
VOICE_PATH = "/usr/share/hts-voice/mei/mei_normal.htsvoice"


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


def speak_text(text):
    """受け取ったテキストをOpen JTalkで音声合成して再生する"""
    print(f"【読み上げ】 {text}")

    # 特殊文字を排除した正しいコマンド（open_jtalkのアンダースコア版）
    # パイプを使ってテキストを渡し、一時ファイルを作らずにaplayで直接鳴らす
    cmd = f'echo "{text}" | open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic -m {VOICE_PATH} -ow /dev/stdout | aplay -q'

    # シェル経由で実行
    subprocess.Popen(cmd, shell=True)


def parse_and_speak_551(data):
    """Code: 551 (地震情報) から読み上げ用テキストを生成する"""
    earthquake = data.get("earthquake", {})
    hypocenter = earthquake.get("hypocenter", {})

    # 必要な情報を抽出
    place = hypocenter.get("name", "不明な震源")
    max_scale_code = earthquake.get("maxScale", 0)
    max_scale = scale_to_str(max_scale_code)

    if max_scale == "不明":
        # 震度情報がない場合は処理スキップ
        return

    # 読み上げ文章の作成
    text = f"地震情報です。先ほど、{place}を震源とする地震がありました。最大震度は、{max_scale}です。"
    speak_text(text)


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

                # 551: 地震情報が来たらパースして読み上げる
                if code == 551:
                    print("★地震情報を検知しました。パースを開始します。")
                    parse_and_speak_551(data)

            except websockets.ConnectionClosed:
                print("接続が切断されました。再接続します...")
                await asyncio.sleep(5)
                return await monitor_sandbox()
            except Exception as e:
                print(f"エラー発生: {e}")
                await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(monitor_sandbox())
    except KeyboardInterrupt:
        print("\nモニタリングを終了しました。")
