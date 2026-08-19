# math-worksheet

数学問題プリントを作成・描画・印刷し、URLで共有できるツール。

- 問題はフォームまたはYAML直接編集で作成（分数・ルート・指数などの簡易数式表示、座標平面/図形/円/数直線の自動描画に対応）
- 「共有リンクを発行」でサーバーに保存し、`/p/:id` のURLを発行（ログイン不要、リンクを知っている人は誰でも閲覧・印刷可能）
- 発行済みリンクは元データを編集しても更新されない（immutable snapshot）。再共有すると新しいURLが発行される

## ローカルで動かす

```bash
cd math-worksheet
npm install
npm start
```

`http://localhost:3000` を開く。

## Dockerで動かす

```bash
cd math-worksheet
docker compose up --build
```

`http://localhost:3000` を開く。共有データは `./data`（ホスト側）にマウントされるので、コンテナを再作成してもデータは消えません。

`docker compose` を使わない場合:

```bash
cd math-worksheet
docker build -t math-worksheet .
docker run -p 3000:3000 -v "$(pwd)/data:/app/data" math-worksheet
```

## デプロイ（常時アクセスできるようにする場合）

Node.js (`npm start` で起動、`PORT` 環境変数を読む) が動く環境、またはDockerイメージが動く環境ならどこでも動作します。例:

- **Render / Railway / Fly.io（Node.js直接）**: リポジトリを接続し、Root Directory を `math-worksheet` に設定、Build Command は不要（`npm install` は自動）、Start Command は `npm start`
- **Render / Railway / Fly.io（Docker）**: 上記サービスは `math-worksheet/Dockerfile` を検出してDockerビルドでのデプロイも可能。Root Directory を `math-worksheet` に設定するだけでOK
- 共有データは `data/*.json` にファイルとして保存されます。永続ディスクがないPaaS（無料プランのRenderなど）ではデプロイ/再起動のたびに消える点に注意してください。永続化したい場合は永続ボリューム（Render Disksなど）を `math-worksheet/data` にマウントするか、外部ストレージ（S3等）に切り替える改修が必要です。

## API

- `POST /api/problems` `{ title, yaml }` → `{ id, url }`
- `GET /api/problems/:id` → `{ title, yaml, createdAt }`
- `GET /p/:id` → 共有ビューア（フロントエンドがIDを見て自動読み込み・自動表示）
