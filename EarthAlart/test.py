import asyncio
import json
import subprocess
import websockets

# サンドボックス用のエンドポイント
SANDBOX_URL = "wss://api-realtime-sandbox.p2pquake.net/v2/ws"
# 先ほどテストした音源のパス
ALERT_SOUND_PATH = "./test.mp3"


def play_alert_sound():
    print("【発火】緊急地震速報（警報）を検知！スピーカーからアラート音を再生します。")
    # バックグラウンドで音を鳴らす（スクリプトの処理を止めないため）
    subprocess.Popen(["mpg123", "-q", ALERT_SOUND_PATH])


async def monitor_sandbox():
    print(f"サンドボックス ({SANDBOX_URL}) に接続します...")

    async with websockets.connect(SANDBOX_URL) as websocket:
        print("接続成功！データの受信を待機しています（約30秒間隔）...")

        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)

                code = data.get("code")
                msg_time = data.get("time", "不明")

                print(f"[{msg_time}] データ受信 - Code: {code}")

                # 554: 緊急地震速報（警報）が来たら音を鳴らす
                if code in [551, 554]:
                    print("★対象のコードを検知しました！")
                    play_alert_sound()

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
