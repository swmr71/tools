const express = require('express');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;
const DATA_DIR = path.join(__dirname, 'data');
const ID_RE = /^[a-f0-9]{10}$/;

if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

app.use(express.json({ limit: '256kb' }));
app.use(express.static(path.join(__dirname, 'public')));

// 問題セットを保存して共有IDを発行
app.post('/api/problems', (req, res) => {
    const { title, yaml } = req.body || {};
    if (typeof yaml !== 'string' || !yaml.trim()) {
        return res.status(400).json({ error: 'yaml is required' });
    }
    if (yaml.length > 200000) {
        return res.status(400).json({ error: 'yaml too large' });
    }
    const safeTitle = typeof title === 'string' ? title.slice(0, 200) : '';

    let id;
    do {
        id = crypto.randomBytes(5).toString('hex');
    } while (fs.existsSync(path.join(DATA_DIR, id + '.json')));

    const record = { title: safeTitle, yaml, createdAt: new Date().toISOString() };
    fs.writeFileSync(path.join(DATA_DIR, id + '.json'), JSON.stringify(record), 'utf8');

    res.json({ id, url: `/p/${id}` });
});

// 共有された問題セットを取得
app.get('/api/problems/:id', (req, res) => {
    const { id } = req.params;
    if (!ID_RE.test(id)) return res.status(400).json({ error: 'invalid id' });
    const file = path.join(DATA_DIR, id + '.json');
    if (!fs.existsSync(file)) return res.status(404).json({ error: 'not found' });
    const record = JSON.parse(fs.readFileSync(file, 'utf8'));
    res.json(record);
});

// 共有リンク（/p/:id）でも同じフロントエンドを返し、クライアント側でIDを読んで取得する
app.get('/p/:id', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
    console.log(`math-worksheet server listening on http://localhost:${PORT}`);
});
