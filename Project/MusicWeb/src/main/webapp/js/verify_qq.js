const http = require('http');

function get(url) {
    return new Promise((resolve, reject) => {
        http.get(url, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => resolve(JSON.parse(data)));
        }).on('error', reject);
    });
}

async function verify() {
    try {
        console.log('1. Searching for "凡人"...');
        const searchRes = await get('http://localhost:3000/qq/search?keywords=' + encodeURIComponent('凡人') + '&limit=1');

        if (!searchRes.data || !searchRes.data.list || searchRes.data.list.length === 0) {
            console.error('Search failed: No results found');
            return;
        }

        const song = searchRes.data.list[0];
        const songmid = song.songmid;
        console.log(`Found song: ${song.songname} (mid: ${songmid})`);

        console.log('2. Fetching playback URL...');
        const urlRes = await get(`http://localhost:3000/qq/song/url?id=${songmid}`);

        console.log('Result:', JSON.stringify(urlRes, null, 2));

        if (urlRes.code === 0 && urlRes.data && urlRes.data.url) {
            console.log('✅ VERIFICATION SUCCESS: Got valid playback URL!');
        } else {
            console.error('❌ VERIFICATION FAILED: ' + (urlRes.message || urlRes.errMsg || 'Unknown error'));
        }

    } catch (e) {
        console.error('Error:', e.message);
    }
}

verify();
