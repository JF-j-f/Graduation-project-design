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
        const searchRes = await get('http://localhost:3000/qq/search?keywords=' + encodeURIComponent('十年') + '&limit=5');

        if (!searchRes.data || !searchRes.data.list || searchRes.data.list.length === 0) {
            console.error('Search failed: No results found');
            return;
        }

        const songs = searchRes.data.list;
        console.log(`Found ${songs.length} songs. Testing URLs...`);

        let successCount = 0;

        for (const song of songs) {
            const songmid = song.songmid;
            console.log(`\nTesting: ${song.songname} - ${song.singer[0].name} (mid: ${songmid})`);

            // Check if it looks like VIP (pay_play)
            const isVip = (song.pay && song.pay.pay_play === 1);
            console.log(`VIP Flag: ${isVip}`);

            const urlRes = await get(`http://localhost:3000/qq/song/url?id=${songmid}`);

            if (urlRes.code === 0 && urlRes.data && urlRes.data.url) {
                console.log('✅ SUCCESS: Got URL!');
                // console.log('URL:', urlRes.data.url);
                successCount++;
            } else {
                console.log('❌ FAILED: ' + (urlRes.message || urlRes.errMsg || 'Unknown error'));
            }
        }

        console.log(`\nSummary: ${successCount} / ${songs.length} playable.`);

        if (successCount > 0) {
            console.log('Conclusion: API is WORKING (some songs are just VIP/Restricted).');
        } else {
            console.log('Conclusion: API might be BROKEN (0 success).');
        }

    } catch (e) {
        console.error('Error:', e.message);
    }
}

verify();
