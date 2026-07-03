import asyncio
import json
import os
import subprocess
import sys
import threading
import websockets

SANDBOX_URL = "wss://api-realtime-sandbox.p2pquake.net/v2/ws"

# パス設定
VOICE_PATH = "/usr/share/hts-voice/mei/mei_normal.htsvoice"
DIC_PATH = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
CHIME_PATH = "./test.mp3"
FIXED_ALERT_PATH = "./fixed_alert.wav"

# ==========================================
# ★【分類テスト用】地域と最低震度の設定
# ==========================================
TARGET_AREA = "石川県能登"  # 分類テストで鳴らしたいターゲット地域
MIN_SCALE = 45  # 5弱以上

# モードを保持する変数（デフォルトは分類テスト）
MODE = "filter"


def select_mode():
    """起動時の引数または入力からモードを決定する"""
    global MODE
    # コマンドライン引数がある場合 (例: python test_modes.py receive)
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ["receive", "filter"]:
            MODE = arg
            return

    # 引数がない場合は、画面で選ばせる
    print("=" * 50)
    print(" 起動モードを選択してください")
    print("=" * 50)
    print(" 1 : 受信テストモード (条件を無視して、データが来たらすべて鳴らす)")
    print(" 2 : 分類テストモード (指定した地域・震度の時だけフィルターをかけて鳴らす)")
    print("=" * 50)

    choice = input("番号を入力してください (1 or 2): ").strip()
    if choice == "1":
        MODE = "receive"
    else:
        MODE = "filter"


def init_fixed_audio():
    if not os.path.exists(FIXED_ALERT_PATH):
        print("固定音声ファイルを生成します...")
        fixed_text = "緊急地震速報です。強い揺れに警戒してください。"
        cmd = f'echo "{fixed_text}" | open_jtalk -x {DIC_PATH} -m {VOICE_PATH} -ow {FIXED_ALERT_PATH}'
        subprocess.run(cmd, shell=True)


def scale_to_str(scale_int):
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
    print(f"【再生シーケンス開始】詳細: {dynamic_text}")
    cmd_fixed = f"mpg123 -q {CHIME_PATH} && aplay -q {FIXED_ALERT_PATH}"
    proc_fixed = subprocess.Popen(cmd_fixed, shell=True)

    tmp_wav = "/tmp/dynamic_alert.wav"
    cmd_gen = f'echo "{dynamic_text}" | open_jtalk -x {DIC_PATH} -m {VOICE_PATH} -ow {tmp_wav}'
    subprocess.run(cmd_gen, shell=True)

    proc_fixed.wait()
    if os.path.exists(tmp_wav):
        subprocess.run(f"aplay -q {tmp_wav}", shell=True)


def process_data(data, code):
    """データを解析し、現在のモード（受信/分類）に合わせて処理を分岐する"""
    earthquake = data.get("earthquake", {})
    place = earthquake.get("hypocenter", {}).get("name", "不明な震源")

    # セリフ用の最大震度をとりあえず取得
    max_scale_code = earthquake.get("maxScale", 0)
    display_scale = scale_to_str(max_scale_code)

    # ----------------------------------------------------
    # パターン1: 【受信テストモード】なら条件を見ずに即再生
    # ----------------------------------------------------
    if MODE == "receive":
        print(f" ➔ 【受信テスト】全てのデータを再生します。")
        dynamic_text = (
            f"震源地は、{place}付近。最大震度は、{display_scale}です。"
        )
        threading.Thread(target=play_alert_sequence, args=(dynamic_text,)).start()
        return

    # ----------------------------------------------------
    # パターン2: 【分類テストモード】なら地域と震度のフィルターをかける
    # ----------------------------------------------------
    is_target_hit = False
    matched_scale = 0

    if code == 554:  # 緊急地震速報
        areas = earthquake.get("areas", [])
        for area in areas:
            if area.get("name") == TARGET_AREA:
                scale = area.get("maxScale", 0)
                if scale >= MIN_SCALE:
                    is_target_hit = True
                    matched_scale = max(matched_scale, scale)

    elif code == 551:  # 地震情報
        points = data.get("points", [])
        for pt in points:
            if pt.get("addr") == TARGET_AREA or pt.get("pref") == TARGET_AREA:
                scale = pt.get("scale", 0)
                if scale >= MIN_SCALE:
                    is_target_hit = True
                    matched_scale = max(matched_scale, scale)

    if is_target_hit:
        print(
            f" ➔ 【分類一致】{TARGET_AREA} で震度 {scale_to_str(matched_scale)} 以上を検知！"
        )
        dynamic_text = (
            f"震源地は、{place}付近。最大震度は、{scale_to_str(matched_scale)}です。"
        )
        threading.Thread(target=play_alert_sequence, args=(dynamic_text,)).start()
    else:
        print(
            f" ➔ 【分類不一致】{TARGET_AREA} は対象外、または震度未満のためスルーします。"
        )


async def monitor_sandbox():
    print(f"サンドボックスに接続します...注意:APIの仕様により、テストは10分で自動終了します。")
    async with websockets.connect(SANDBOX_URL) as websocket:
        print(f"接続成功！ 現在のモード: 【{MODE.upper()}】")

        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                code = data.get("code")

                if code in [551, 554]:
                    msg_time = data.get("time", "不明")
                    print(
                        f"[{msg_time}] データ受信 - Code: {code}。処理を開始します..."
                    )
                    process_data(data, code)

            except websockets.ConnectionClosed:
                print("接続切断。再接続します...")
                await asyncio.sleep(5)
                return await monitor_sandbox()
            except Exception as e:
                print(f"エラー: {e}")
                await asyncio.sleep(5)


if __name__ == "__main__":
    # 1. まずモードを決定
    select_mode()
    # 2. 音声ファイルの準備
    init_fixed_audio()

    try:
        asyncio.run(monitor_sandbox())
    except KeyboardInterrupt:
        print("\nモニタリングを終了しました。")
