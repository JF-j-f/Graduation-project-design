/**
 * MusicWeb 统一音乐 API 服务 (Enhanced Edition)
 * 整合网易云音乐 + QQ音乐接口
 * 
 * 特性:
 * - 网易云 SVIP Cookie 共享
 * - 三级播放降级: Native -> Unblock -> QQ Fallback
 * - QQ VIP 标识注入
 * 
 * 启动命令: node server.js
 * 默认端口: 3000
 */

const fs = require('fs');
const path = require('path');

// 修正模块查找路径 (node_modules 在 ../MusicServer 下)
module.paths.push(path.join(__dirname, '../MusicServer/node_modules'));

const express = require('express');
const axios = require('axios');

// 导入增强版网易云 API
const NeteaseAPI = require('@neteasecloudmusicapienhanced/api');

const app = express();
const PORT = process.env.PORT || 3000;

// ============================================
//    全局配置
// ============================================

// Python QQ 音乐 API 地址；Docker 部署时通过服务名访问，避免容器内 localhost 指向自身
const PY_API_BASE = process.env.QQ_API_URL || 'http://127.0.0.1:8000';

// Unblock 解灰服务地址；本地开发保持默认值，Docker 部署由环境变量覆盖
const UNBLOCK_API_BASE = process.env.UNBLOCK_API_URL || 'http://127.0.0.1:8081';

// Cookie 文件路径
const COOKIE_FILE = process.env.MUSIC_API_COOKIE_FILE
    || path.join(__dirname, '../MusicServer/Cookie/api_credentials.json');

// 全局 Cookie 变量
let NETEASE_COOKIE = '';

// 启动时加载 Cookie
function loadCookie() {
    try {
        if (fs.existsSync(COOKIE_FILE)) {
            const content = fs.readFileSync(COOKIE_FILE, 'utf-8').trim();
            const json = JSON.parse(content);

            if (json.netease && json.netease.cookie) {
                NETEASE_COOKIE = json.netease.cookie;
                console.log('✅ [Cookie] 已从 api_credentials.json 加载网易云 Cookie');
                console.log(`   📝 Cookie 长度: ${NETEASE_COOKIE.length} 字符`);
            } else {
                console.warn('⚠️ [Cookie] api_credentials.json 中未找到 netease.cookie 字段');
            }
        } else {
            console.warn('⚠️ [Cookie] 未找到凭证文件:', COOKIE_FILE);
        }
    } catch (err) {
        console.error('❌ [Cookie] 加载失败:', err.message);
    }
}

// 立即加载
loadCookie();

// 每 10 分钟重新加载一次 Cookie (支持热更新)
setInterval(loadCookie, 10 * 60 * 1000);

// ============================================
//    中间件
// ============================================

// CORS
app.use((req, res, next) => {
    res.header('Access-Control-Allow-Origin', '*');
    res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
    next();
});

// JSON 解析
app.use(express.json());

// ============================================
//    网易云音乐 API
// ============================================

/**
 * 网易云音乐搜索
 * GET /netease/search?keywords=周杰伦&limit=30
 */
app.get('/netease/search', async (req, res) => {
    try {
        const { keywords, limit = 30, offset = 0 } = req.query;
        if (!keywords) {
            return res.status(400).json({ code: 400, message: '缺少搜索关键词' });
        }

        const result = await NeteaseAPI.search({
            keywords,
            limit: parseInt(limit),
            offset: parseInt(offset),
            cookie: NETEASE_COOKIE
        });

        res.json(result.body);
    } catch (error) {
        console.error('网易云搜索错误:', error.message);
        res.status(500).json({ code: 500, message: error.message });
    }
});

/**
 * 网易云音乐获取歌曲播放链接 (四级降级策略)
 * GET /netease/song/url?id=123456&title=歌曲名&artist=歌手名
 * 
 * Step 0: 匿名尝试 - 不带 Cookie，适用于非 VIP 歌曲
 * Step 1: SVIP Native - 使用 Cookie 获取原生高音质链接（仅 VIP 歌曲需要）
 * Step 2: Unblock - 调用解灰服务获取第三方源
 * Step 3: QQ Fallback - 搜索 QQ 音乐获取链接
 */
app.get('/netease/song/url', async (req, res) => {
    const { id, br = 320000, title, artist } = req.query;

    if (!id) {
        return res.status(400).json({ code: 400, message: '缺少歌曲ID' });
    }

    console.log(`🎵 [播放请求] ID: ${id}, 标题: ${title || '未知'}, 歌手: ${artist || '未知'}`);

    // Step 0: 匿名尝试（不带 Cookie，节省 SVIP 配额）
    try {
        console.log('   📍 Step 0: 尝试匿名获取（非 VIP 歌曲）...');
        const anonymousResult = await NeteaseAPI.song_url({
            id,
            br: parseInt(br)
            // 不传 cookie，匿名访问
        });

        if (anonymousResult.body && anonymousResult.body.data && anonymousResult.body.data[0]) {
            const songData = anonymousResult.body.data[0];
            if (songData.url && songData.url !== '') {
                // 关键校验：通过 freeTrialInfo 字段判断是否为30秒试听残链
                // freeTrialInfo 仅在试听限制时出现，短曲（本身<=30s）不会有此字段
                if (songData.freeTrialInfo != null) {
                    console.log(`   ⚠️ Step 0: 检测到试听限制 (freeTrialInfo 存在, time=${songData.time}ms)，继续降级...`);
                } else {
                    console.log(`   ✅ Step 0 成功: 完整歌曲 (时长: ${songData.time ? (songData.time / 1000).toFixed(0) + 's' : '未知'})`);
                    return res.json(anonymousResult.body);
                }
            }
        }
        console.log('   ⚠️ Step 0 失败: 歌曲可能需要 VIP');
    } catch (error) {
        console.error('   ❌ Step 0 异常:', error.message);
    }

    // Step 1: SVIP Native 尝试（仅当匿名失败时）
    try {
        console.log('   📍 Step 1: 尝试 SVIP Native...');
        const result = await NeteaseAPI.song_url({
            id,
            br: parseInt(br),
            cookie: NETEASE_COOKIE
        });

        if (result.body && result.body.data && result.body.data[0]) {
            const songData = result.body.data[0];
            if (songData.url && songData.url !== '') {
                console.log('   ✅ Step 1 成功: 获取到 SVIP 链接');
                return res.json(result.body);
            }
        }
        console.log('   ⚠️ Step 1 失败: 无有效链接');
    } catch (error) {
        console.error('   ❌ Step 1 异常:', error.message);
    }

    // Step 2: Unblock 解灰尝试
    try {
        console.log('   📍 Step 2: 尝试 Unblock 解灰...');
        const unblockRes = await axios.get(`${UNBLOCK_API_BASE}/match`, {
            params: { id },
            timeout: 5000,
            validateStatus: () => true
        });

        if (unblockRes.status === 200 && unblockRes.data && unblockRes.data.url) {
            console.log('   ✅ Step 2 成功: 解灰获取到链接');
            // 构造兼容格式返回
            return res.json({
                code: 200,
                data: [{
                    id: parseInt(id),
                    url: unblockRes.data.url,
                    br: 128000,
                    type: 'mp3',
                    source: 'unblock'
                }]
            });
        }
        console.log('   ⚠️ Step 2 失败: Unblock 无结果');
    } catch (error) {
        console.error('   ❌ Step 2 异常:', error.message);
    }

    // Step 3: QQ Fallback
    if (title && artist) {
        try {
            console.log('   📍 Step 3: 尝试 QQ Fallback...');
            const searchKeyword = `${title} ${artist}`;

            // 搜索 QQ 音乐
            const searchRes = await axios.get(`${PY_API_BASE}/search`, {
                params: { keywords: searchKeyword, limit: 1 },
                timeout: 5000,
                validateStatus: () => true
            });

            if (searchRes.status === 200 && searchRes.data.code === 0 && searchRes.data.data && searchRes.data.data.length > 0) {
                const qqSong = searchRes.data.data[0];
                const mid = qqSong.songmid || qqSong.mid;
                const qqInterval = qqSong.interval || 0; // 歌曲完整时长（秒）

                // 获取 QQ 音乐播放链接
                const urlRes = await axios.get(`${PY_API_BASE}/song/url`, {
                    params: { mid },
                    timeout: 5000,
                    validateStatus: () => true
                });

                if (urlRes.status === 200 && urlRes.data.code === 0 && urlRes.data.data && urlRes.data.data.url) {
                    console.log(`   ✅ Step 3 成功: QQ Fallback 获取到链接 (歌曲完整时长: ${qqInterval}s)`);
                    return res.json({
                        code: 200,
                        data: [{
                            id: parseInt(id),
                            url: urlRes.data.data.url,
                            br: 128000,
                            type: 'm4a',
                            source: 'qq_fallback',
                            time: qqInterval * 1000 // 统一为毫秒，与网易云格式对齐
                        }]
                    });
                }
            }
            console.log('   ⚠️ Step 3 失败: QQ Fallback 无结果');
        } catch (error) {
            console.error('   ❌ Step 3 异常:', error.message);
        }
    } else {
        console.log('   ⏭️ Step 3 跳过: 缺少 title/artist 参数');
    }

    // 全部失败
    console.log('   ❌ 三级降级全部失败');
    res.json({
        code: 200,
        data: [{ id: parseInt(id), url: null, br: 0, type: '', source: 'failed' }]
    });
});

/**
 * 网易云音乐获取歌曲详情
 * GET /netease/song/detail?ids=123456,789012
 */
app.get('/netease/song/detail', async (req, res) => {
    try {
        const { ids } = req.query;
        if (!ids) {
            return res.status(400).json({ code: 400, message: '缺少歌曲ID' });
        }

        const result = await NeteaseAPI.song_detail({
            ids,
            cookie: NETEASE_COOKIE
        });

        res.json(result.body);
    } catch (error) {
        console.error('获取歌曲详情错误:', error.message);
        res.status(500).json({ code: 500, message: error.message });
    }
});

/**
 * 网易云音乐获取歌曲完整详情 (含专辑信息)
 * GET /netease/song/detail/full?id=123456
 * 
 * 返回: {
 *   id, name, artists, album, duration, coverUrl,
 *   releaseYear, publishTime, company, genre, language
 * }
 */
app.get('/netease/song/detail/full', async (req, res) => {
    try {
        const { id } = req.query;
        if (!id) {
            return res.status(400).json({ code: 400, message: '缺少歌曲ID' });
        }

        console.log(`📋 [详情查询] 歌曲 ID: ${id}`);

        // Step 1: 获取歌曲基础详情
        const songResult = await NeteaseAPI.song_detail({
            ids: id,
            cookie: NETEASE_COOKIE
        });

        if (!songResult.body || !songResult.body.songs || songResult.body.songs.length === 0) {
            return res.status(404).json({ code: 404, message: '歌曲未找到' });
        }

        const song = songResult.body.songs[0];
        const albumId = song.al?.id;

        // 构建基础响应
        let enrichedData = {
            id: song.id,
            name: song.name,
            artists: song.ar?.map(a => a.name).join(' / ') || 'Unknown Artist',
            artistIds: song.ar?.map(a => a.id) || [],
            album: song.al?.name || 'Unknown Album',
            albumId: albumId,
            duration: song.dt || 0,
            coverUrl: song.al?.picUrl || '',
            // 这些字段需要进一步查询
            releaseYear: null,
            publishTime: null,
            company: null,
            genre: null,
            language: null
        };

        // Step 2: 查询专辑详情获取发行年份和公司
        if (albumId) {
            try {
                console.log(`   📀 查询专辑详情: ${albumId}`);
                const albumResult = await NeteaseAPI.album({
                    id: albumId,
                    cookie: NETEASE_COOKIE
                });

                if (albumResult.body && albumResult.body.album) {
                    const album = albumResult.body.album;

                    // 发行时间 (毫秒时间戳)
                    if (album.publishTime) {
                        const publishDate = new Date(album.publishTime);
                        enrichedData.publishTime = album.publishTime;
                        enrichedData.releaseYear = publishDate.getFullYear();
                    }

                    // 发行公司
                    if (album.company) {
                        enrichedData.company = album.company;
                    }

                    // 专辑类型/风格 (tags 或 description 可能包含)
                    if (album.subType) {
                        enrichedData.albumType = album.subType;
                    }

                    // 专辑封面 (优先级更高)
                    if (album.picUrl && !enrichedData.coverUrl) {
                        enrichedData.coverUrl = album.picUrl;
                    }
                }
            } catch (albumErr) {
                console.warn(`   ⚠️ 专辑详情查询失败: ${albumErr.message}`);
            }
        }

        // Step 3: 尝试获取歌曲风格/流派标签
        try {
            // 使用歌手信息查询流派 (歌手通常有关联的风格标签)
            if (enrichedData.artistIds && enrichedData.artistIds.length > 0) {
                const artistResult = await NeteaseAPI.artist_detail({
                    id: enrichedData.artistIds[0],
                    cookie: NETEASE_COOKIE
                });

                if (artistResult.body && artistResult.body.data && artistResult.body.data.artist) {
                    const artist = artistResult.body.data.artist;
                    // 艺术家简介中可能包含流派信息
                    if (artist.briefDesc) {
                        enrichedData.artistBrief = artist.briefDesc.substring(0, 200);
                    }
                    // 一些歌手有 identifyTag (华语/欧美等)
                    if (artist.identifyTag && artist.identifyTag.length > 0) {
                        enrichedData.artistTags = artist.identifyTag;
                    }
                }
            }
        } catch (artistErr) {
            // 不阻断主流程
            console.warn(`   ⚠️ 歌手详情查询失败: ${artistErr.message}`);
        }

        // Step 4: 根据歌手标签推断语言
        if (enrichedData.artistTags && enrichedData.artistTags.length > 0) {
            const tags = enrichedData.artistTags;
            if (tags.includes('华语') || tags.includes('内地') || tags.includes('港台')) {
                enrichedData.language = '国语';
            } else if (tags.includes('欧美')) {
                enrichedData.language = '英语';
            } else if (tags.includes('日本')) {
                enrichedData.language = '日语';
            } else if (tags.includes('韩国')) {
                enrichedData.language = '韩语';
            }
        }

        console.log(`   ✅ 完整详情获取成功: ${enrichedData.name}`);
        res.json({ code: 200, data: enrichedData });

    } catch (error) {
        console.error('获取完整歌曲详情错误:', error.message);
        res.status(500).json({ code: 500, message: error.message });
    }
});

/**
 * 网易云音乐获取歌曲百科摘要 (流派/语种)
 * GET /netease/song/wiki/summary?id=123456
 * 
 * 返回: { genre: "流行；R&B", language: null }
 * 注意: 并非所有歌曲都有百科信息
 */
app.get('/netease/song/wiki/summary', async (req, res) => {
    try {
        const { id } = req.query;
        if (!id) {
            return res.status(400).json({ code: 400, message: '缺少歌曲ID' });
        }

        console.log(`📖 [Wiki] 查询歌曲百科: ${id}`);

        const result = await NeteaseAPI.song_wiki_summary({
            id,
            cookie: NETEASE_COOKIE
        });

        if (result.body && result.body.data) {
            const wikiData = result.body.data;

            // 解析 blocks 中的流派和语种信息
            let genre = null;
            let language = null;
            let genres = [];

            if (wikiData.blocks && Array.isArray(wikiData.blocks)) {
                for (const block of wikiData.blocks) {
                    // console.log(`[WikiDebug] Block: ${block.code} / ${block.showType}`);

                    // 1. 尝试解析 songTag (曲风) 和 language (语种) - 新版结构
                    if (block.creatives && Array.isArray(block.creatives)) {
                        for (const creative of block.creatives) {
                            // console.log(`[WikiDebug]   Creative: ${creative.creativeType}`);

                            // 解析曲风
                            if (creative.creativeType === 'songTag' && creative.resources) {
                                for (const res of creative.resources) {
                                    if (res.uiElement && res.uiElement.mainTitle && res.uiElement.mainTitle.title) {
                                        const title = res.uiElement.mainTitle.title;
                                        // console.log(`[WikiDebug]     Found Genre: ${title}`);
                                        genres.push(title);
                                    }
                                }
                            }
                            // 解析语种
                            if (creative.creativeType === 'language' && creative.uiElement && creative.uiElement.textLinks) {
                                for (const link of creative.uiElement.textLinks) {
                                    if (link.text) {
                                        const lang = link.text;
                                        // console.log(`[WikiDebug]     Found Language: ${lang}`);
                                        language = lang;
                                    }
                                }
                            }
                        }
                    }

                    // 2. 也是检查 key-value 类型 (旧版结构兼容)
                    if (block.kvList) {
                        for (const kv of block.kvList) {
                            const key = (kv.key || '').toLowerCase();
                            if (key.includes('流派') || key.includes('genre')) {
                                genres.push(kv.value);
                            }
                            if (key.includes('语种') || key.includes('language')) {
                                language = kv.value;
                            }
                        }
                    }
                }
            }

            // 组合流派
            if (genres.length > 0) {
                // 去重
                genre = [...new Set(genres)].slice(0, 3).join('；');
            }

            console.log(`   ✅ Wiki 获取成功: genre=${genre}, language=${language}`);
            res.json({
                code: 200,
                data: { genre, language, raw: wikiData }
            });
        } else {
            console.log(`   ⚠️ Wiki 无数据`);
            res.json({ code: 200, data: { genre: null, language: null } });
        }

    } catch (error) {
        console.error('获取歌曲百科错误:', error.message);
        res.status(500).json({ code: 500, message: error.message });
    }
});

/**
 * 网易云音乐获取歌词
 * GET /netease/lyric?id=123456
 */
app.get('/netease/lyric', async (req, res) => {
    try {
        const { id } = req.query;
        if (!id) {
            return res.status(400).json({ code: 400, message: '缺少歌曲ID' });
        }

        const result = await NeteaseAPI.lyric({
            id,
            cookie: NETEASE_COOKIE
        });

        res.json(result.body);
    } catch (error) {
        console.error('获取歌词错误:', error.message);
        res.status(500).json({ code: 500, message: error.message });
    }
});

// ============================================
//    QQ音乐 API (Python 代理)
// ============================================

/**
 * 通用代理函数
 */
async function proxyToPython(method, endpoint, params, res) {
    try {
        console.log(`[Proxy] Forwarding to Python: ${endpoint}`, params);
        const response = await axios({
            method: method,
            url: `${PY_API_BASE}${endpoint}`,
            params: method === 'GET' ? params : undefined,
            data: method === 'POST' ? params : undefined,
            validateStatus: () => true
        });

        res.status(response.status).json(response.data);
    } catch (error) {
        console.error(`[Proxy] Error forwarding to ${endpoint}:`, error.message);
        if (error.code === 'ECONNREFUSED') {
            return res.status(503).json({ code: 503, message: 'QQ音乐服务未启动 (Python Service Unavailable)' });
        }
        res.status(500).json({ code: 500, message: '代理请求失败: ' + error.message });
    }
}

/**
 * QQ音乐搜索 (增强版: 注入 VIP 标识)
 * GET /qq/search?keywords=周杰伦&limit=30
 */
app.get('/qq/search', async (req, res) => {
    const { keywords, limit = 30, page = 1 } = req.query;
    if (!keywords) {
        return res.status(400).json({ code: 400, message: '缺少搜索关键词' });
    }

    try {
        const response = await axios.get(`${PY_API_BASE}/search`, {
            params: { keywords, limit, page },
            validateStatus: () => true
        });

        // 注入 VIP 标识
        if (response.status === 200 && response.data.code === 0 && response.data.data) {
            const songs = response.data.data;
            for (const song of songs) {
                // 判断逻辑: pay.pay_play > 0 或 pay.payplay > 0
                if (song.pay) {
                    song.vip = (song.pay.pay_play > 0 || song.pay.payplay > 0);
                } else {
                    song.vip = false;
                }
            }
        }

        res.status(response.status).json(response.data);
    } catch (error) {
        console.error('QQ搜索错误:', error.message);
        res.status(500).json({ code: 500, message: error.message });
    }
});

/**
 * QQ音乐获取歌曲播放链接
 * GET /qq/song/url?id=001xxx
 */
app.get('/qq/song/url', async (req, res) => {
    const { id } = req.query;
    if (!id) {
        return res.status(400).json({ code: 400, message: '缺少歌曲ID' });
    }
    await proxyToPython('GET', '/song/url', { mid: id }, res);
});

/**
 * QQ音乐获取歌曲完整详情
 * GET /qq/song/detail?mid=xxx
 * 
 * 返回歌曲完整信息，包含 VIP 状态、发行时间等
 */
app.get('/qq/song/detail', async (req, res) => {
    const { mid } = req.query;
    if (!mid) {
        return res.status(400).json({ code: 400, message: '缺少歌曲 MID' });
    }
    await proxyToPython('GET', '/song/detail', { mid }, res);
});

/**
 * QQ音乐获取二维码
 */
app.get('/qq/login/qr', async (req, res) => {
    const { type = 'qq' } = req.query;
    await proxyToPython('GET', '/login/qr', { login_type: type }, res);
});

app.post('/qq/login/qr/check', async (req, res) => {
    await proxyToPython('POST', '/login/qr/check', {}, res);
});

app.post('/qq/login/phone/send', async (req, res) => {
    await proxyToPython('POST', '/login/phone/send', req.body, res);
});

app.post('/qq/login/phone/verify', async (req, res) => {
    await proxyToPython('POST', '/login/phone/verify', req.body, res);
});

app.get('/qq/credential', async (req, res) => {
    await proxyToPython('GET', '/credential', {}, res);
});

app.post('/qq/credential/logout', async (req, res) => {
    await proxyToPython('POST', '/credential/logout', {}, res);
});

// ============================================
//    统一搜索接口
// ============================================

app.get('/search', async (req, res) => {
    try {
        const { keywords, source = 'netease', limit = 30 } = req.query;
        if (!keywords) {
            return res.status(400).json({ code: 400, message: '缺少搜索关键词' });
        }

        let results = { netease: null, qq: null };

        // 网易云搜索
        if (source === 'netease' || source === 'all') {
            try {
                const neteaseResult = await NeteaseAPI.search({
                    keywords,
                    limit: parseInt(limit),
                    cookie: NETEASE_COOKIE
                });
                results.netease = neteaseResult.body;
            } catch (e) {
                console.error('网易云搜索失败:', e.message);
            }
        }

        // QQ音乐搜索
        if (source === 'qq' || source === 'all') {
            try {
                const response = await axios.get(`${PY_API_BASE}/search`, {
                    params: { keywords, limit, page: 1 },
                    validateStatus: () => true
                });
                if (response.status === 200 && response.data.code === 0) {
                    // 注入 VIP 标识
                    const songs = response.data.data || [];
                    for (const song of songs) {
                        song.vip = song.pay ? (song.pay.pay_play > 0 || song.pay.payplay > 0) : false;
                    }
                    results.qq = response.data.data;
                }
            } catch (e) {
                console.error('QQ音乐搜索失败:', e.message);
            }
        }

        res.json({ code: 200, source, results });
    } catch (error) {
        console.error('统一搜索错误:', error.message);
        res.status(500).json({ code: 500, message: error.message });
    }
});

// ============================================
//    健康检查
// ============================================

app.get('/health', async (req, res) => {
    let qqStatus = false;
    let unblockStatus = false;

    // 检查 QQ 服务
    try {
        const pyRes = await axios.get(`${PY_API_BASE}/health`, { timeout: 1000 });
        if (pyRes.status === 200) qqStatus = true;
    } catch (e) { }

    // 检查 Unblock 服务
    try {
        const ubRes = await axios.get(`${UNBLOCK_API_BASE}/`, { timeout: 1000 });
        if (ubRes.status === 200) unblockStatus = true;
    } catch (e) { }

    res.json({
        status: 'ok',
        timestamp: new Date().toISOString(),
        cookie_loaded: NETEASE_COOKIE.length > 0,
        services: {
            netease: true,
            qq: qqStatus,
            unblock: unblockStatus
        }
    });
});

// ============================================
//    API 首页
// ============================================

app.get('/', (req, res) => {
    res.json({
        name: 'MusicWeb API Server (Enhanced)',
        version: '3.0.0',
        description: '统一音乐 API 服务 (网易云 SVIP + Unblock 解灰 + QQ Fallback)',
        features: [
            '✅ 网易云 SVIP Cookie 共享',
            '✅ 三级播放降级策略',
            '✅ QQ VIP 标识注入'
        ],
        endpoints: {
            '健康检查': 'GET /health',
            '统一搜索': 'GET /search?keywords=xxx&source=netease|qq|all',
            '网易云': {
                '搜索': 'GET /netease/search?keywords=xxx',
                '播放链接': 'GET /netease/song/url?id=xxx&title=xxx&artist=xxx',
                '详情': 'GET /netease/song/detail?ids=xxx',
                '歌词': 'GET /netease/lyric?id=xxx'
            },
            'QQ音乐': {
                '搜索': 'GET /qq/search?keywords=xxx',
                '播放链接': 'GET /qq/song/url?id=xxx'
            }
        }
    });
});

// ============================================
//    启动服务
// ============================================

app.listen(PORT, () => {
    console.log('========================================');
    console.log('  MusicWeb API Server (Enhanced v3.0)');
    console.log('========================================');
    console.log(`  🚀 服务已启动: http://localhost:${PORT}`);
    console.log(`  🔗 Python QQ API: ${PY_API_BASE}`);
    console.log(`  🔧 Unblock 服务: ${UNBLOCK_API_BASE}`);
    console.log(`  🍪 Cookie 状态: ${NETEASE_COOKIE.length > 0 ? '已加载' : '未加载'}`);
    console.log('========================================');
});
